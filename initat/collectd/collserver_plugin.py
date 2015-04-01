#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

from initat.collectd.collectd_types import * # @UnusedWildImport
from initat.collectd.config import IPC_SOCK, log_base
from initat.collectd.net_receiver import net_receiver
from initat.collectd.background import background
import collectd # @UnresolvedImport
import os
import time
import process_tools
import logging_tools
import signal
import threading
import zmq

class receiver(log_base):
    def __init__(self):
        self.recv_sock = None
        self.__last_sent = {}
        self.lock = threading.Lock()
    def start_sub_processes(self):
        self.log("start sub-processes")
        self.net_receiver_proc = net_receiver()
        self.net_receiver_proc.start()
        self.log("adding receiver pid {:d}".format(self.net_receiver_proc.pid))
        self.background_proc = background(self.main_pid)
        self.background_proc.start()
        self.log("adding background pid {:d}".format(self.background_proc.pid))
        self.__msi_block.add_actual_pid(self.net_receiver_proc.pid, mult=3, process_name="receiver", fuzzy_ceiling=3)
        self.__msi_block.add_actual_pid(self.background_proc.pid, mult=3, process_name="background", fuzzy_ceiling=3)
        # save msi block, then signal background
        self.__msi_block.save_block()
        self.send_to_slave("bg", "read_msi_block")
    # def config(self, *args, **kwargs):
    #    print "c", args, kwargs
    def init_receiver(self, main_pid):
        self.pid = os.getpid()
        self.name = "main"
        self.zmq_context = zmq.Context()
        log_base.__init__(self)
        self.main_pid = main_pid
        self.log("init receiver")
        self._init_msi_block()
        self.log("init 0MQ IPC receiver, socket at {}".format(
            IPC_SOCK,
            )
        )
        self.recv_sock = self.zmq_context.socket(zmq.ROUTER)
        self.recv_sock.setsockopt(zmq.ROUTER_MANDATORY, True)
        self.recv_sock.setsockopt(zmq.IDENTITY, "main")
        sock_dir = os.path.dirname(IPC_SOCK[6:])
        if not os.path.isdir(sock_dir):
            self.log("creating directory {}".format(sock_dir))
            os.mkdir(sock_dir)
        self.recv_sock.bind(IPC_SOCK)
        self.start_sub_processes()
    def _init_msi_block(self):
        self.log("init meta-server-info block")
        msi_block = process_tools.meta_server_info("collectd")
        msi_block.add_actual_pid(mult=10, fuzzy_ceiling=10, process_name="main")
        msi_block.start_command = "/etc/init.d/collectd start"
        msi_block.stop_command = "/etc/init.d/collectd force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block
    def recv(self):
        self.lock.acquire()
        if self.recv_sock:
            while True:
                try:
                    sender = self.recv_sock.recv_unicode(zmq.DONTWAIT)
                except:
                    break
                else:
                    data = self.recv_sock.recv_pyobj()
                    _com = data[0]
                    if _com == "mvector":
                        self._handle_tree(data[1:])
                    elif _com == "pdata":
                        self._handle_perfdata(data[1])
                    elif _com.startswith("to_"):
                        self.send_to_slave(_com[3:], data[1])
                    else:
                        self.log("unknown data from {} : {}".format(sender, _com), logging_tools.LOG_LEVEL_ERROR)
        self.lock.release()
    def send_to_slave(self, slave_name, snd, **kwargs):
        _ign = kwargs.get("ignore_error", False)
        _iter = 0
        while True:
            try:
                self.recv_sock.send_unicode(slave_name, zmq.SNDMORE)
                self.recv_sock.send_pyobj(snd)
            except zmq.error.ZMQError:
                if _ign:
                    break
                _iter += 1
                if _iter > 10:
                    raise
                time.sleep(0.1)
            else:
                break
    def shutdown(self):
        self.log("shutdown received")
        self.send_to_slave("bg", "exit", ignore_error=True)
        self.send_to_slave("net", "exit", ignore_error=True)
        self.net_receiver_proc.join()
        self.background_proc.join()
        if self.recv_sock:
            self.recv_sock.close()
        self.log("exiting...")
        self.close_log()
        self.zmq_context.term()
        self.background_proc.join()
        self.net_receiver_proc.join()
        self.recv_sock = None
        self.__msi_block.remove_meta_block()
    def get_time(self, h_tuple, cur_time):
        cur_time = int(cur_time)
        if h_tuple in self.__last_sent:
            if cur_time <= self.__last_sent[h_tuple]:
                diff_time = self.__last_sent[h_tuple] + 1 - cur_time
                cur_time += diff_time
                self.log("correcting time for {} (+{:d}s to {:d})".format(str(h_tuple), diff_time, int(cur_time)))
        self.__last_sent[h_tuple] = cur_time
        return self.__last_sent[h_tuple]
    def _handle_perfdata(self, data):
        # print "***", data
        _type, type_instance, host_name, time_recv, rsi, v_list = data
        s_time = self.get_time((host_name, "ipd_{}".format(_type)), time_recv)
        collectd.Values(plugin="perfdata", type_instance=type_instance, host=host_name, time=s_time, type="ipd_{}".format(_type), interval=5 * 60).dispatch(values=v_list[rsi:])
    def _handle_tree(self, data):
        host_name, time_recv, values = data
        # print host_name, time_recv
        s_time = self.get_time((host_name, "icval"), time_recv)
        for name, value in values:
            # name can be none for values with transform problems
            if name:
                collectd.Values(plugin="collserver", host=host_name, time=s_time, type="icval", type_instance=name).dispatch(values=[value])

# our own functions go here
def configer(ObjConfiguration):
    # print ObjConfiguration, dir(ObjConfiguration)
    pass

def initer(my_recv):
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    my_recv.init_receiver(os.getpid())

my_recv = receiver()

# print "c", collectd.register_config(configer) # my_recv.config)
collectd.register_init(initer, my_recv)
# call every 15 seconds
collectd.register_read(my_recv.recv, 15.0)
collectd.register_shutdown(my_recv.shutdown)
