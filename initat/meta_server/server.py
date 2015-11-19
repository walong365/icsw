# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2010-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of meta-server
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
""" meta-server, server process """

import os
import stat
import time

import zmq

from initat.client_version import VERSION_STRING
from initat.host_monitoring import hm_classes
from initat.icsw.service import container, transition, instance, service_parser, clusterid
from initat.tools import configfile, logging_tools, mail_tools, process_tools, server_command, \
    threading_tools, inotify_tools
from initat.tools.server_mixins import ICSWBasePoolClient
from .config import global_config
from .servicestate import ServiceState


class main_process(ICSWBasePoolClient):
    def __init__(self):
        self.__debug = global_config["DEBUG"]
        threading_tools.process_pool.__init__(self, "main")
        self.CC.init("meta-server", global_config)
        self.CC.check_config(client=True)
        self.CC.CS.copy_to_global_config(
            global_config, [
                ("meta.track.icsw.memory", "TRACK_CSW_MEMORY"),
                ("meta.check.time", "MIN_CHECK_TIME"),
                ("meta.check.memory.time", "MIN_MEMCHECK_TIME"),
            ]
        )
        global_config.add_config_entries(
            [
                ("STATE_DIR", configfile.str_c_var(os.path.join(self.CC.CS["meta.maindir"], ".srvstate"), source="dynamic")),
            ]
        )
        # check for correct rights
        self._check_dirs()
        self._init_msi_block()
        self._init_network_sockets()
        self._init_inotify()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        # init stuff for mailing
        self.__new_mail = mail_tools.mail(
            None,
            "{}@{}".format(
                self.CC.CS["meta.mail.from.name"],
                process_tools.get_fqdn()[0],
            ),
            self.CC.CS["mail.target.address"],
        )
        self.__new_mail.set_server(self.CC.CS["mail.server"], self.CC.CS["mail.server"])
        # msi dict
        self.__last_update_time = time.time() - 2 * global_config["MIN_CHECK_TIME"]
        self.__last_memcheck_time = time.time() - 2 * global_config["MIN_MEMCHECK_TIME"]
        self._init_meminfo()
        self._show_config()
        self._init_statemachine()
        self.__next_stop_is_restart = False
        # wait for transactions if necessary
        self.__exit_process = False
        self.__transition_timer = False
        self.register_timer(self._check, 30, instant=True)

    def _init_statemachine(self):
        self.__transitions = []
        self.def_ns = service_parser.Parser.get_default_ns()
        self.service_state = ServiceState(self.log)
        self.server_instance = instance.InstanceXML(self.log)
        self.container = container.ServiceContainer(self.log)
        self.service_state.sync_with_instance(self.server_instance)
        self.__watcher.add_watcher(
            "xml",
            self.server_instance.source_dir,
            inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE,
            self._instance_event,
        )

    def _init_inotify(self):
        self.__loopcount = 0
        self.__watcher = inotify_tools.InotifyWatcher(log_com=self.log)
        self.__watcher.add_watcher(
            "main",
            self.CC.CS["meta.maindir"],
            inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE,
            self._inotify_event,
        )
        # register watcher fd with 0MQ poller
        self.register_poller(self.__watcher._fd, zmq.POLLIN, self._inotify_check)

    def _inotify_check(self, *args, **kwargs):
        try:
            self.__watcher.process()
        except:
            self.log(
                "exception occured in watcher.process(): {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            pass

    def _instance_event(self, *args, **kwargs):
        self.log("instance directory changed")
        # check for pending changes ?
        self.server_instance.reread()
        self.service_state.sync_with_instance(self.server_instance)

    def _inotify_event(self, *args, **kwargs):
        _event = args[0]
        if _event.mask & inotify_tools.IN_DELETE:
            self._delete_msi_by_file_name(_event.pathname)
        elif _event.mask & inotify_tools.IN_CLOSE_WRITE:
            self._update_or_create_msi_by_file_name(_event.pathname)

    def _check_dirs(self):
        main_dir = self.CC.CS["meta.maindir"]
        if not os.path.isdir(main_dir):
            self.log("creating {}".format(main_dir))
            os.mkdir(main_dir)
        cur_stat = os.stat(main_dir)[stat.ST_MODE]
        new_stat = cur_stat | stat.S_IWGRP | stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IWOTH | stat.S_IROTH
        if cur_stat != new_stat:
            self.log(
                "modifying stat of {} from {:o} to {:o}".format(
                    main_dir,
                    cur_stat,
                    new_stat,
                )
            )
            os.chmod(main_dir, new_stat)

    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(self.__pid_name, mult=3)
        _spm = global_config.single_process_mode()
        if not _spm:
            process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("meta-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=7, process_name="main")
        if not _spm:
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2, process_name="manager")
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block

    def _sigint(self, err_cause):
        if self.__exit_process:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.__exit_process = True
            if not (self.__next_stop_is_restart or global_config["DEBUG"]):
                self.service_state.enable_shutdown_mode()
                _res_list = self.container.check_system(self.def_ns, self.server_instance.tree)
                trans_list = self.service_state.update(
                    _res_list,
                    throttle=[("uwsgi-init", 5)],
                    exclude=["logging-server", "meta-server"],
                )
                self._new_transitions(trans_list)
                if not self.__transitions:
                    self["exit_requested"] = True
            else:
                self["exit_requested"] = True

    def _enable_transition_timer(self):
        if not self.__transition_timer:
            self.__transition_timer = True
            self.register_timer(self._handle_transition, 5, instant=True)

    def _disable_transition_timer(self):
        if self.__transition_timer:
            self.__transition_timer = False
            self.unregister_timer(self._handle_transition)

    def _init_network_sockets(self):
        self.network_bind(
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            pollin=self._recv_command,
            client_type="meta-server",
        )
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        if hm_classes and global_config["TRACK_CSW_MEMORY"]:
            self.log("CSW memory tracking enabled, target is {}".format(conn_str))
            vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
            vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
            vector_socket.connect(conn_str)
        else:
            vector_socket = None
        self.vector_socket = vector_socket
        # memory info send dict
        self.mis_dict = {}

    def _recv_command(self, zmq_sock):
        trigger_sm = False
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)  # @UndefinedVariable
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)  # @UndefinedVariable
            srv_com = server_command.srv_command(source=data)
            self.log("got command '{}' from '{}'".format(
                srv_com["command"].text,
                srv_com["source"].attrib["host"]))
            srv_com.update_source()
            srv_com.set_result("ok")
            if srv_com["command"].text.startswith("state"):
                # trigger state machine when necessary
                trigger_sm = self.service_state.handle_command(srv_com)
            elif srv_com["command"].text == "version":
                srv_com.set_result("version is {}".format(VERSION_STRING))
            elif srv_com["command"].text == "next-stop-is-restart":
                self.log("next stop will be a restart")
                self.__next_stop_is_restart = True
            else:
                srv_com.set_result(
                    "unknown command '{}'".format(srv_com["command"].text),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            try:
                zmq_sock.send_unicode(src_id, zmq.SNDMORE | zmq.NOBLOCK)  # @UndefinedVariable
                zmq_sock.send_unicode(unicode(srv_com), zmq.NOBLOCK)  # @UndefinedVariable
            except:
                self.log(
                    "error sending reply to {}: {}".format(
                        src_id,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            self.log(
                "cannot receive more data, already got '{}'".format(
                    src_id
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        if trigger_sm:
            self._check_processes(force=True)

    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [{:d}] {}".format(log_level, log_line))
        except:
            self.log(
                "error showing configfile log, old configfile ? ({})".format(process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR
            )
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def _init_meminfo(self):
        self.__last_meminfo_keys, self.__act_meminfo_line = ([], 0)

    def _check(self):
        act_time = time.time()
        if abs(act_time - self.__last_update_time) < global_config["MIN_CHECK_TIME"]:
            self.log(
                "last check only {} ago ({:.2f} needed), skipping...".format(
                    logging_tools.get_diff_time_str(abs(act_time - self.__last_update_time)),
                    global_config["MIN_CHECK_TIME"],
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        else:
            self.__last_update_time = act_time
            self._check_processes()

    def _handle_transition(self):
        new_list = []
        for _trans in self.__transitions:
            if _trans.step(self.container):
                new_list.append(_trans)
            else:
                self.service_state.transition_finished(_trans)
        self.__transitions = new_list
        if not self.__transitions:
            self.log("all transitions finished")
            self._disable_transition_timer()
            if self.__exit_process:
                self["exit_requested"] = True

    def _new_transitions(self, trans_list):
        self._log_transaction(trans_list)
        for _trans in trans_list:
            _new_t = transition.ServiceTransition(
                _trans.action,
                [_trans.name],
                self.container,
                self.server_instance.tree,
                self.log,
                _trans.trans_id,
            )
            if _new_t.step(self.container):
                self.__transitions.append(_new_t)
            else:
                self.service_state.transition_finished(_new_t)
        if self.__transitions:
            self._enable_transition_timer()

    def _log_transaction(self, trans_list):
        if self.__debug:
            self.log(
                "handling {}: {}".format(
                    logging_tools.get_plural("transition", len(trans_list)),
                    ", ".join(["{} -> {}".format(_trans.name, _trans.action) for _trans in trans_list])
                )
            )
        else:
            self.log(
                "handling {}".format(
                    logging_tools.get_plural("transition", len(trans_list)),
                )
            )

    def _check_processes(self, service_list=None, force=False):
        self.__loopcount += 1
        act_time = time.time()
        # act_pid_dict = process_tools.get_proc_list()
        _check_mem = act_time > self.__last_memcheck_time + global_config["MIN_MEMCHECK_TIME"] and global_config["TRACK_CSW_MEMORY"]
        if _check_mem:
            self.__last_memcheck_time = act_time
        if service_list is not None:
            self.def_ns.service = service_list
        else:
            self.def_ns.service = []
        _res_list = self.container.check_system(self.def_ns, self.server_instance.tree)
        # always reset service to the empty list
        self.def_ns.service = []
        trans_list = self.service_state.update(
            _res_list,
            exclude=["meta-server", "logging-server"],
            throttle=[("uwsgi-init", 5)],
            # force first call
            force=(self.__loopcount == 1 or force),
        )
        if trans_list:
            self._new_transitions(trans_list)
            if self.__loopcount > 1 and not force:
                _cluster_id = clusterid.get_cluster_id() or "N/A"
                mail_subject, mail_text = self.service_state.get_mail_text(trans_list)
                self.__new_mail.init_text()
                self.__new_mail.set_subject(
                    "{} from {} ({})".format(
                        mail_subject,
                        process_tools.get_fqdn()[0],
                        _cluster_id,
                    )
                )
                self.__new_mail.append_text(mail_text)
                _sm_stat, log_lines = self.__new_mail.send_mail()
                for line in log_lines:
                    self.log(line)
        if _check_mem and _res_list:
            self._show_meminfo(_res_list)
        end_time = time.time()
        if end_time - act_time > 1:
            self.log(
                "update {:d} took {}".format(
                    self.__loopcount,
                    logging_tools.get_diff_time_str(end_time - act_time),
                )
            )

    def _read_msi_from_disk(self, file_name):
        new_meta_info = process_tools.meta_server_info(file_name, self.log)
        if new_meta_info.name:
            self.log(
                "read meta_info_block for {} (file {}, info: {})".format(
                    new_meta_info.name,
                    file_name,
                    new_meta_info.get_info()
                )
            )
        else:
            self.log(
                "error reading meta_info_block from {} (name returned None)".format(file_name),
                logging_tools.LOG_LEVEL_ERROR
            )
            new_meta_info = None
        return new_meta_info

    def _delete_msi_by_file_name(self, file_name):
        self.log("msi file {} has been removed, triggering check".format(file_name))
        self._check_processes()

    def _update_or_create_msi_by_file_name(self, file_name):
        self.log("file {} has been changed or created, triggering check".format(file_name))
        # changes in MSI-blocks are now handled in the state machine
        _service_list = self.container.filter_msi_file_name(self.container.apply_filter([], self.server_instance.tree), file_name)
        if len(_service_list):
            self._check_processes(service_list=[_entry.name for _entry in _service_list])
        else:
            self._check_processes()

    def _show_meminfo(self, res_list):
        act_time = time.time()
        self.__act_meminfo_line += 1
        valid_entries = [entry for entry in res_list if entry.entry.find(".//memory_info[@valid='1']") is not None]
        act_meminfo_keys = [entry.name for entry in valid_entries]
        if act_meminfo_keys != self.__last_meminfo_keys or self.__act_meminfo_line > 100:
            self.__act_meminfo_line = 0
            self.__last_meminfo_keys = act_meminfo_keys
            self.log(
                "Memory info mapping: {}".format(
                    ", ".join(
                        [
                            "{:d}: {}".format(
                                act_meminfo_keys.index(key) + 1,
                                key
                            ) for key in act_meminfo_keys
                        ]
                    )
                )
            )
        if hm_classes and self.vector_socket:
            drop_com = server_command.srv_command(command="set_vector")
            mv_valid = act_time + 2 * global_config["MIN_MEMCHECK_TIME"]
            my_vector = drop_com.builder("values")
            # handle removal of old keys, track pids, TODO, FIXME
            old_keys = set(self.mis_dict.keys())
            new_keys = set()
            for entry in valid_entries:
                key = entry.name
                tot_mem = 0
                mem_el = entry.entry.find(".//memory_info")
                tot_mem = int(mem_el.text.strip())
                if mem_el.find("details") is not None:
                    for _detail in mem_el.findall("details/mem"):
                        proc_name = _detail.get("name")
                        f_key = (key, proc_name)
                        info_str = "memory usage of {} ({})".format(key, proc_name)
                        if f_key not in self.mis_dict:
                            self.mis_dict[f_key] = hm_classes.mvect_entry(
                                "mem.icsw.{}.{}".format(key, proc_name),
                                info=info_str,
                                default=0,
                                unit="Byte",
                                base=1024
                            )
                        self.mis_dict[f_key].update(int(_detail.text))
                        self.mis_dict[f_key].info = info_str
                        self.mis_dict[f_key].valid_until = mv_valid
                        new_keys.add(f_key)
                        my_vector.append(self.mis_dict[f_key].build_xml(drop_com.builder))
                if key not in self.mis_dict:
                    self.mis_dict[key] = hm_classes.mvect_entry(
                        "mem.icsw.{}.total".format(key),
                        info="memory usage of {}".format(key),
                        default=0,
                        unit="Byte",
                        base=1024
                    )
                self.mis_dict[key].update(tot_mem)
                self.mis_dict[key].valid_until = mv_valid
                new_keys.add(key)
                my_vector.append(self.mis_dict[key].build_xml(drop_com.builder))
            drop_com["vector"] = my_vector
            drop_com["vector"].attrib["type"] = "vector"
            self.vector_socket.send_unicode(unicode(drop_com))
            del_keys = old_keys - new_keys
            if del_keys:
                self.log("removing {} from mis_dict".format(logging_tools.get_plural("key", len(del_keys))))
                for del_key in del_keys:
                    del self.mis_dict[del_key]
        self.log(
            "Memory info: {}".format(
                " / ".join(
                    [
                        process_tools.beautify_mem_info(
                            int(_el.entry.find(".//memory_info").text),
                            short=True
                        ) for _el in valid_entries
                    ]
                )
            )
        )

    def loop_post(self):
        self.network_unbind()
        # close vector socket if set
        if self.vector_socket:
            self.vector_socket.close()
        self.CC.close()
