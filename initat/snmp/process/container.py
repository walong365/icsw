# Copyright (C) 2009-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" SNMP process container """

from .config import DEFAULT_RETURN_NAME
from .process import snmp_process
import logging_tools
import os
import pprint  # @UnusedImport
import time
import zmq


class snmp_process_container(object):
    def __init__(self, mq_name, log_com, max_procs, max_snmp_jobs, conf_dict, event_dict):
        # name of return queue
        self.mq_name = mq_name
        self.log_com = log_com
        self.max_procs = max_procs
        self.max_snmp_jobs = max_snmp_jobs
        self.conf_dict = conf_dict
        self.__event_dict = event_dict
        self.pid = os.getpid()
        self.__run_flag = True
        self.__snmp_dict = {}
        self.__used_proc_ids = set()
        self._socket = None
        self.log("init with a maximum of {:d} processes ({:d} jobs per process)".format(self.max_procs, self.max_snmp_jobs))
        self.log("{} in default config dict:".format(logging_tools.get_plural("key", len(self.conf_dict))))
        for _key in sorted(self.conf_dict):
            self.log("  {}={}".format(_key, self.conf_dict[_key]))

    def create_ipc_socket(self, zmq_context, socket_addr, socket_name=DEFAULT_RETURN_NAME):
        self._socket = zmq_context.socket(zmq.ROUTER)  # @UndefinedVariable
        self._socket.setsockopt(zmq.IDENTITY, socket_name)  # @UndefinedVariable
        self._socket.setsockopt(zmq.IMMEDIATE, True)  # @UndefinedVariable
        self._socket.setsockopt(zmq.ROUTER_MANDATORY, True)  # @UndefinedVariable
        self._socket.bind(socket_addr)
        return self._socket

    def close(self):
        self._socket.close()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com(u"[spc] {}".format(what), log_level)

    def check(self):
        cur_running = self.__snmp_dict.keys()
        to_start = self.max_procs - len(cur_running)
        if to_start:
            min_idx = 1 if not self.__snmp_dict else max(self.__snmp_dict.keys()) + 1
            self.log(
                "starting {} (starting at {:d})".format(
                    logging_tools.get_plural("SNMP process", to_start),
                    min_idx,
                )
            )
            _npid = 1
            for new_idx in xrange(min_idx, min_idx + to_start):
                while _npid in self.__used_proc_ids:
                    _npid += 1
                self.__used_proc_ids.add(_npid)
                cur_struct = {
                    "npid": _npid,
                    "name": "snmp_{:d}".format(new_idx),
                    "msi_name": "snmp_{:d}".format(_npid),
                    "proc": snmp_process("snmp_{:d}".format(new_idx), self.conf_dict, ignore_signals=True),
                    "running": False,
                    "stopping": False,
                    "stopped": False,
                    "jobs": 0,
                    "pending": 0,
                    "done": 0,
                }
                cur_struct["proc"].main_queue_name = self.mq_name
                cur_struct["proc"].start()
                self.__snmp_dict[new_idx] = cur_struct

    def get_free_snmp_id(self):
        # code from old snmp-relay:
        # free_processes = sorted([(value["calls_init"], key) for key, value in self.__process_dict.iteritems() if value["state"] == "running"])
        idle_procs = sorted(
            [
                (value["jobs"], key) for key, value in self.__snmp_dict.iteritems() if not value["stopped"] and not value["pending"] and not value["stopping"]
            ]
        )
        running_procs = sorted(
            [
                (value["jobs"], key) for key, value in self.__snmp_dict.iteritems() if not value["stopped"] and value["pending"] and not value["stopping"]
            ]
        )
        if idle_procs:
            proc_id = idle_procs[0][1]
        else:
            proc_id = running_procs[0][1]
        return proc_id

    def stop(self):
        # stop all snmp process and stop spawning new ones
        self.__run_flag = False
        for _key, value in self.__snmp_dict.iteritems():
            if value["running"] and not value["stopped"]:
                self.send(value["name"], "exit")
        if not self.__snmp_dict:
            self._event("all_stopped")

    def get_usage(self):
        return "process usage (init/done): {}".format(
            ", ".join(
                [
                    "{:d}/{:d}".format(
                        self.__snmp_dict[key]["jobs"],
                        self.__snmp_dict[key]["done"],
                    ) for key in sorted(self.__snmp_dict.iterkeys())
                ]
            )
        )

    def start_batch(self, vers, ip, com, batch_id, single_key_transform, timeout, *oid_list, **kwargs):
        # see proc_data in snmp_relay_schemes
        snmp_id = self.get_free_snmp_id()
        self.__snmp_dict[snmp_id]["jobs"] += 1
        self.__snmp_dict[snmp_id]["pending"] += 1
        self.send("snmp_{:d}".format(snmp_id), "fetch_snmp", vers, ip, com, batch_id, single_key_transform, timeout, *oid_list, VERBOSE=0, **kwargs)

    def send(self, target, m_type, *args, **kwargs):
        _iter = 0
        while True:
            _iter += 1
            try:
                self._socket.send_unicode(target, zmq.SNDMORE)  # @UndefinedVariable
                self._socket.send_pyobj({
                    "pid": self.pid,
                    "type": m_type,
                    "args": args,
                    "kwargs": kwargs,
                })
            except zmq.error.ZMQError:
                _iter += 1
                time.sleep(0.1)
                if _iter > 10:
                    logging_tools.my_syslog("unable to send to {}".format(target))
            else:
                break

    def _event(self, ev_name, *args, **kwargs):
        if ev_name in self.__event_dict:
            self.__event_dict[ev_name](*args, **kwargs)
        else:
            self.log("no event with name {}".format(ev_name), logging_tools.LOG_LEVEL_ERROR)

    def handle_with_socket(self, _sock):
        self.handle()

    def handle(self):
        # handle results
        src_proc = self._socket.recv_unicode()
        snmp_idx = int(src_proc.split("_")[1])
        data = self._socket.recv_pyobj()
        if data["type"] == "process_start":
            self.__snmp_dict[snmp_idx]["running"] = True
            self._event(
                "process_start",
                pid=data["pid"],
                mult=3,
                process_name=self.__snmp_dict[snmp_idx]["msi_name"],
                fuzzy_ceiling=3
            )
        elif data["type"] == "process_exit":
            self.log("SNMP process {:d} stopped (PID={:d})".format(snmp_idx, data["pid"]), logging_tools.LOG_LEVEL_WARN)
            self.__snmp_dict[snmp_idx]["stopped"] = True
            self.__used_proc_ids.remove(self.__snmp_dict[snmp_idx]["npid"])
            # self.log(str(self.__used_proc_ids))
            self.__snmp_dict[snmp_idx]["proc"].join()
            del self.__snmp_dict[snmp_idx]
            self._event(
                "process_exit",
                pid=data["pid"],
                mult=3,
            )
            if self.__run_flag:
                # spawn new processes
                self.check()
            else:
                if not self.__snmp_dict:
                    self.log("all SNMP processes stopped")
                    self._event("all_stopped")
        elif data["type"] == "snmp_finished":
            self.__snmp_dict[snmp_idx]["pending"] -= 1
            self.__snmp_dict[snmp_idx]["done"] += 1
            self._event("finished", data)
            if self.__snmp_dict[snmp_idx]["jobs"] > self.max_snmp_jobs:
                if self.__snmp_dict[snmp_idx]["stopping"]:
                    self.log("SNMP process {:d} already stopped".format(snmp_idx), logging_tools.LOG_LEVEL_WARN)
                else:
                    self.__snmp_dict[snmp_idx]["stopping"] = True
                    self.log(
                        "stopping SNMP process {:d} ({:d} > {:d})".format(
                            snmp_idx,
                            self.__snmp_dict[snmp_idx]["jobs"],
                            self.max_snmp_jobs,
                        )
                    )
                    self.send("snmp_{:d}".format(snmp_idx), "exit")
        else:
            self.log("unknown type {} from {}".format(data["type"], src_proc), logging_tools.LOG_LEVEL_ERROR)
