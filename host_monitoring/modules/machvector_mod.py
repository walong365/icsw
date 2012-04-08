#!/usr/bin/python-init
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2012 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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
""" machine vector stuff """

import Queue
import sys
import threading
import os
import os.path
import commands
import stat
import time
from host_monitoring import limits
import configfile
import logging_tools
import process_tools
import threading_tools
import net_tools
from host_monitoring import hm_classes
from lxml import etree
import server_command
import copy
try:
    import bz2
except:
    bz2 = None

MACHVECTOR_NAME = "machvector"
ALERT_NAME = "alert"
COLLECTOR_PORT = 8002
                            
MONITOR_OBJECT_INFO_LIST = ["load", "mem", "net", "vms", "num"]
MAX_MONITOR_OBJECTS = 10

class _general(hm_classes.hm_module):
    class Meta:
        priority = 5
    def __init__(self, *args, **kwargs):
        hm_classes.hm_module.__init__(self, *args, **kwargs)
    def init_module(self):
        if hasattr(self.process_pool, "register_vector_receiver"):
            self.process_pool.register_timer(self._update_machine_vector, 10, instant=True)
            self._init_machine_vector()
    def _init_machine_vector(self):
        self.machine_vector = machine_vector(self)
    def init_machine_vector(self, mvect):
        pass
    def _update_machine_vector(self):
        self.machine_vector.update()

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "machvector",
                                        "provides the framework for the machine_vector",
                                        **args)
        self.priority = -255
        self.has_own_thread = True
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.mvect = mach_vect(logger, module_dict=args.get("mc_dict", {}), module=self)
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            #print opt, arg
            if hmb.name in ["get_mvector_raw"]:
                if opt in ("-r", "--raw"):
                    my_lim.set_add_flags("R")
        return ok, why, [my_lim]
    def get_machvector_file_name(self):
        return "%s/%s" % (self.basedir_name, MACHVECTOR_NAME)
    def get_alert_file_name(self):
        return "%s/%s" % (self.basedir_name, ALERT_NAME)
    def process_server_args(self, glob_config, logger):
        self.basedir_name = glob_config["BASEDIR_NAME"]
        # check for config file in /etc/sysconfig/host-monitoring.d/machvector_mod
        full_name = self.get_machvector_file_name()
        if not os.path.isfile(full_name):
            try:
                file(full_name, "w").write("RRD_SERVER*=udp:localhost:8002\n")
            except:
                pass
        collector_host_dict, send_interval = ({}, 1)
        logger.info("  setting send-interval to %d iterations (conf)" % (send_interval))
        stat, c_dict = configfile.readconfig(full_name, 1)
        if stat:
            rrd_keys = [x for x in c_dict.keys() if x.startswith("RRD_SERVER")]
            collector_host_dict = {}
            for rrd_key in rrd_keys:
                # no more bz2 compression
                use_bz2 = False
                collector_hosts = c_dict[rrd_key].split(",")
                for col_host in collector_hosts:
                    act_dict = {"mode"    : "tcp",
                                "host"    : None,
                                "port"    : COLLECTOR_PORT,
                                "use_bz2" : use_bz2}
                    try:
                        chp = col_host.split(":")
                        act_part = chp.pop(0)
                        if act_part in ["tcp", "udp"]:
                            act_dict["mode"] = act_part
                            act_part = chp.pop(0)
                        act_dict["host"] = act_part
                        if chp:
                            act_dict["port"] = int(chp.pop(0))
                        if len(chp):
                            logger.error("*** ParseError: something left in %s after parsing" % (col_host))
                            act_dict = None
                    except ValueError:
                        logger.error("*** ValueError() while parsing %s" % (col_host))
                    else:
                        if act_dict:
                            collector_host_dict["%s%s%d" % (act_dict["host"], act_dict["mode"], act_dict["port"])] = act_dict
            for key, stuff in collector_host_dict.iteritems():
                logger.info("   connecting to host %20s via %4s, port %5d" % (stuff["host"],
                                                                              stuff["mode"],
                                                                              stuff["port"]))
            if c_dict.has_key("SEND_INTERVAL"):
                send_interval = int(c_dict["SEND_INTERVAL"])
                logger.info("  setting max. send-interval to %d iterations (conf)" % (send_interval))
        if not collector_host_dict:
            logger.info("  sending of MachVectors disabled (empty collector_host_dict)")
        self.send_interval = send_interval
        self.collector_host_dict = collector_host_dict
        ok, why = (1, "")
        return ok, why
    def start_thread(self, logger):
        self.__tc_lock = threading.Lock()
        self.__loc_queue = Queue.Queue(20)
        new_t = my_subthread(self, logger, self.__loc_queue, self.mvect)
        self.__t_queue = new_t.get_thread_queue()
        return new_t
    def send_thread(self, what):
        self.__tc_lock.acquire()
        self.__t_queue.put(what)
        res = self.__loc_queue.get()
        self.__tc_lock.release()
        return res

class simple_con(net_tools.buffer_object):
    def __init__(self, mode, host, port, s_str, d_queue):
        self.__mode = mode
        self.__host = host
        self.__port = port
        self.__send_str = s_str
        self.__d_queue = d_queue
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        if self.__mode == "udp":
            self.add_to_out_buffer(self.__send_str)
        else:
            self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
            if self.__mode == "udp":
                self.__d_queue.put(("send_ok", (self.__host, self.__port, self.__mode, "udp_send")))
                self.delete()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.__d_queue.put(("send_ok", (self.__host, self.__port, self.__mode, "got %s" % (what))))
        self.delete()
    def report_problem(self, flag, what):
        self.__d_queue.put(("send_error", (self.__host, self.__port, self.__mode, "%s: %s" % (net_tools.net_flag_to_str(flag),
                                                                                              what))))
        self.delete()

class my_subthread(threading_tools.thread_obj):
    def __init__(self, file_info, logger, loc_queue, mvect):
        self.__logger = logger
        self.__file_info = file_info
        self.__loc_queue = loc_queue
        threading_tools.thread_obj.__init__(self, "machvector", queue_size=100)
        self.__mvector = mvect
        self.register_func("register_call_queue", self._register_call_queue)
        self.register_func("update", self._update)
        self.register_func("get_mvector", self._get_mvector)
        self.register_func("get_mvector_raw", self._get_mvector_raw)
        self.register_func("get_mvector_stats", self._get_mvector_stats)
        self.register_func("start_monitor", self._start_monitor)
        self.register_func("stop_monitor", self._stop_monitor)
        self.register_func("monitor_info", self._monitor_info)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("send_error", self._send_error)
        self.register_func("send_ok", self._send_ok)
        # clear net_server
        self.__net_server = None
        self.__num_con, self.__num_ok, self.__num_fail = ({}, {}, {})
        for h_name in self.__file_info.collector_host_dict.keys():
            self.__num_con[h_name]        = 0
            self.__num_ok[h_name]         = 0
            self.__num_fail[h_name]       = 0
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        # update timestamps and stuff
        self.__first_update, self.__last_update, self.__num_update = (time.time(), None, 0)
        # init external machvector source dir
        self.__esd = "/tmp/.machvect_es"
        if not os.path.isdir(self.__esd):
            os.mkdir(self.__esd)
            self.log("external machvector_source_dir '%s' created" % (self.__esd))
        try:
            os.chmod(self.__esd, 0777)
        except:
            self.log("cannot chmod() %s to 0777" % (self.__esd),
                     logging_tools.LOG_LEVEL_ERROR)
        # monitor objects
        self.__mon_dict = {}
        # fetch net_server_object
        self.send_pool_message(("get_net_server", self.get_thread_queue()))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _set_net_server(self, ns):
        self.log("setting net_server")
        self.__net_server = ns
    def _register_call_queue(self, dest_q):
        #dest_q.put(("register_queue", ("flush_mv", self.get_thread_queue())))
        pass
    def _send_error(self, (s_host, s_port, mode, what)):
        self.log("send_error (%s, %s %d): %s" % (s_host, mode, s_port, what), logging_tools.LOG_LEVEL_ERROR)
        match = False
        for h_name, h_stuff in self.__file_info.collector_host_dict.iteritems():
            if h_stuff["host"] == s_host and h_stuff["port"] == s_port and h_stuff["mode"] == mode:
                match = True
                self.__num_fail[h_name] += 1
        if not match:
            self.log("Got unknown '%s'-message for host/port/mode %s/%d/%s" % (what, s_host, s_port, mode), logging_tools.LOG_LEVEL_WARN)
    def _send_ok(self, (s_host, s_port, mode, what)):
        # no logging of send_ok messages
        #self.log("send_ok (%s, %s %d): %s" % (s_host, mode, s_port, what))
        match = False
        for h_name, h_stuff in self.__file_info.collector_host_dict.iteritems():
            if h_stuff["host"] == s_host and h_stuff["port"] == s_port and h_stuff["mode"] == mode:
                match = True
                self.__num_ok[h_name] += 1
                #self.__mvector.flush_cache(h_name)
        if not match:
            self.log("Got unknown '%s'-message for host/port/mode %s/%d/%s" % (what, s_host, s_port, mode), logging_tools.LOG_LEVEL_WARN)
    def _update(self):
        act_update = time.time()
        if not self.__last_update:
            self.__last_update = act_update - 2 * min_update_step
        if act_update > self.__last_update:
            if self.__last_update + min_update_step > act_update or False:
                self.log("(machvector) too many update-requests (last was %s ago, minimum allowed step is %s)" % (logging_tools.get_diff_time_str(act_update - self.__last_update),
                                                                                                                  logging_tools.get_diff_time_str(min_update_step)),
                         logging_tools.LOG_LEVEL_WARN)
                do_update = False
            else:
                do_update = True
        else:
            self.log("(machvector) time skew detected, adjusting last_update timestemp from %.2f to %.2f" % (self.__last_update,
                                                                                                             act_update),
                     logging_tools.LOG_LEVEL_WARN)
            self.__last_update = act_update
            do_update = False
        if do_update:
            self.__latest_key = self.__mvector.get_actual_key()
            # check external sources
            self.__mvector.check_external_sources(self.__logger, self.__esd)
            self.__mvector.update_vector(self.__logger, self.__esd)
            # monitor threads
            for mon_id, mon_stuff in self.__mon_dict.iteritems():
                mon_stuff.update(self.__mvector)
            self.__num_update += 1
            send_str = hm_classes.sys_to_net(self.__mvector.get_send_mvector())
            send_str_compr, sok = (send_str, "ok")
            for h_name, h_stuff in self.__file_info.collector_host_dict.iteritems():
                # try connecting to collector_host
                # netserver set ?
                if not self.__net_server:
                    self.log("net_server not set, skipping send ...", logging_tools.LOG_LEVEL_WARN)
                else:
                    self.__num_con[h_name] += 1
                    if h_stuff["mode"] == "tcp":
                        self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                              target_host=h_stuff["host"],
                                                                              target_port=h_stuff["port"],
                                                                              bind_retries=1,
                                                                              rebind_wait_time=1,
                                                                              connect_state_call=self._udp_connect,
                                                                              add_data="ok %s" % (send_str)))
                    else:
                        self.__net_server.add_object(net_tools.udp_con_object(self._new_udp_con,
                                                                              target_host=h_stuff["host"],
                                                                              target_port=h_stuff["port"],
                                                                              bind_retries=1,
                                                                              rebind_wait_time=1,
                                                                              connect_state_call=self._udp_connect,
                                                                              add_data="ok %s" % (send_str)))

    def _udp_connect(self, **args):
        if args["state"] == "error":
            args["socket"].delete()
            self.get_thread_queue().put(("send_error", (args["host"], args["port"], args["type"], "connect error")))
    def _new_udp_con(self, sock):
        return simple_con("udp", sock.get_target_host(), sock.get_target_port(), sock.get_add_data(), self.get_thread_queue())
    def _new_tcp_con(self, sock):
        return simple_con("tcp", sock.get_target_host(), sock.get_target_port(), sock.get_add_data(), self.get_thread_queue())
    def _get_mvector(self):
        self.__loc_queue.put(self.__mvector.get_mvector())
    def _get_mvector_raw(self):
        self.__loc_queue.put(self.__mvector.get_mvector_raw())
    def _get_mvector_stats(self):
        ret_arg = {"num_updates"   : self.__num_update,
                   "send_interval" : self.__file_info.send_interval,
                   "hosts"         : {}}
        for h_name, h_stuff in self.__file_info.collector_host_dict.iteritems():
            loc_dict = {"host"        : h_stuff["host"],
                        "port"        : h_stuff["port"],
                        "mode"        : h_stuff["mode"],
                        "num_con"     : self.__num_con[h_name],
                        "num_ok"      : self.__num_ok[h_name],
                        "num_fail"    : self.__num_fail[h_name]}
            ret_arg["hosts"][h_name] = loc_dict
        self.__loc_queue.put(ret_arg)
    def _start_monitor(self, mon_id):
        if self.__mon_dict.has_key(mon_id):
            del self.__mon_dict[mon_id]
            self.log("Monitor_object with id '%s' already present, deleting ..." % (mon_id), logging_tools.LOG_LEVEL_WARN)
        self.__mon_dict[mon_id] = monitor_object(mon_id)
        self.__mon_dict[mon_id].update(self.__mvector)
        self.log("init monitor_object Monitor_object with id '%s' (now %d in list: %s)" % (mon_id,
                                                                                           len(self.__mon_dict.keys()),
                                                                                           ",".join(self.__mon_dict.keys())))
        if len(self.__mon_dict.keys()) > MAX_MONITOR_OBJECTS:
            del_id = None
            for key, value in self.__mon_dict.iteritems():
                if not del_id:
                    del_id, del_time = (key, value.get_start_time())
                else:
                    if value.get_start_time()  < del_time:
                        del_id, del_time = (key, value.get_start_time())
            del self.__mon_dict[del_id]
            self.log("too many monitor objects (%d), deleting oldest one (is '%s'), still in list: %s" % (len(self.__mon_dict.keys()) + 1,
                                                                                                          del_id,
                                                                                                          ",".join(self.__mon_dict.keys())),
                     logging_tools.LOG_LEVEL_ERROR)
        self.__loc_queue.put("ok started monitor with id %s" % (mon_id))
    def _stop_monitor(self, mon_id):
        if self.__mon_dict.has_key(mon_id):
            del self.__mon_dict[mon_id]
            self.log("Monitor_object with id '%s' deleted" % (mon_id))
            self.__loc_queue.put("ok stopped monitor with id %s" % (mon_id))
        else:
            self.log("no monitor_object with id '%s' found" % (mon_id), logging_tools.LOG_LEVEL_ERROR)
            self.__loc_queue.put("error not monitor with id %s" % (mon_id))
    def _monitor_info(self, mon_id):
        if self.__mon_dict.has_key(mon_id):
            send_str = hm_classes.sys_to_net(self.__mon_dict[mon_id].get_info())
            self.__loc_queue.put("ok %s" % (send_str))
        else:
            self.__loc_queue.put("error not monitor with id %s" % (mon_id))

class get_mvector_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
    def __call__(self, srv_com, cur_ns):
        self.module.machine_vector.store_xml(srv_com)
    def interpret(self, srv_com, cur_ns):
        cur_vector = srv_com["data:machine_vector"]
        vector_keys = sorted(srv_com.xpath(cur_vector, ".//ns:mve/@name"))
        ret_array = ["Machinevector id %s, %s:" % (cur_vector.attrib["version"],
                                                   logging_tools.get_plural("key", len(vector_keys)))]
        out_list = logging_tools.new_form_list()
        for mv_num, mv_key in enumerate(vector_keys):
            cur_xml = srv_com.xpath(cur_vector, "//ns:mve[@name='%s']" % (mv_key))[0]
            out_list.append(hm_classes.mvect_entry(cur_xml.attrib.pop("name"), **cur_xml.attrib).get_form_entry(mv_num))
        ret_array.extend(unicode(out_list).split("\n"))
        return limits.nag_STATE_OK, "\n".join(ret_array)

class get_mvector_raw_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "get_mvector_raw", **args)
        self.help_str = "returns the raw machine vector"
        self.short_client_info = "-r, --raw"
        self.long_client_info = "sets raw-output (for scripts)"
        self.short_client_opts = "r"
        self.long_client_opts = ["raw"]
        self.net_only = True
    def server_call(self, cm):
        try:
            return "ok %s" % (hm_classes.sys_to_net(self.module_info.send_thread("get_mvector_raw")))
        except:
            return "error %s" % (process_tools.get_except_info())
    def client_call(self, result, parsed_coms):
        #print cm
        ret_state = limits.nag_STATE_OK
        raw_output = parsed_coms[0].get_add_flag("R")
        if raw_output:
            return ret_state, result[3:]
        else:
            # not really usefull
            return ret_state, str(hm_classes.net_to_sys(result[3:]))

class get_mvector_stats_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "get_mvector_stats", **args)
        self.help_str = "returns machine vector transferinformations"
        self.net_only = True
    def server_call(self, cm):
        try:
            return "ok %s" % (hm_classes.sys_to_net(self.module_info.send_thread("get_mvector_stats")))
        except:
            return "error %s" % (process_tools.get_except_info())
    def client_call(self, result, parsed_coms):
        ret_state = limits.nag_STATE_CRITICAL
        if result.startswith("ok "):
            cmp_s = hm_classes.net_to_sys(result[3:])
            if cmp_s.has_key("num_con"):
                # old client
                num_con = cmp_s["num_con"]
                num_fail = cmp_s["num_fail"]
                num_ok = cmp_s["num_ok"]
                dhost = cmp_s["host"]
                dport = cmp_s["port"]
                if num_con:
                    if num_fail == 0:
                        ret_state = limits.nag_STATE_OK
                        ret_str = "OK: all %d connections to host %s (port %d) successful" % (num_con, dhost, dport)
                    elif num_ok == 0:
                        ret_state = limits.nag_STATE_CRITICAL
                        ret_str = "Error: all %d connections to host %s (port %d) failed" % (num_con, dhost, dport)
                    else:
                        ret_state = limits.nag_STATE_WARNING
                        ret_str = "Warning: of %d connections to host %s (port %d) %d were ok, %d failed" % (num_con, dhost, dport, num_ok, num_fail)
                else:
                    ret_state = limits.nag_STATE_OK
                    if dhost == "None":
                        ret_str = "No destination host given"
                    else:
                        ret_str = "Destination host is %s (port %d)" % (dhost, dport)
                ret_str += ", %d updates, send interval is %d, update timestep is %.2f" % (cmp_s["num_updates"],
                                                                                           cmp_s["send_iv"],
                                                                                           cmp_s["up_step"])
            else:
                head_str = "# of iterations is %d, max. send_interval is %d, connecting to %d servers" % (cmp_s["num_updates"], cmp_s["send_interval"], len(cmp_s["hosts"].keys()))
                h_array = ["to host %-20s, %3s port %5d, connections/ok/fail : %d / %d / %d" % (host_stuff["host"],
                                                                                                host_stuff["mode"],
                                                                                                host_stuff["port"],
                                                                                                host_stuff["num_con"],
                                                                                                host_stuff["num_ok"],
                                                                                                host_stuff["num_fail"]) for h, host_stuff in cmp_s["hosts"].iteritems()]
                ret_state = limits.nag_STATE_OK
                ret_str = "\n".join([head_str] + [" - %s" % (x) for x in h_array])
        else:
            ret_str = "error : %s" % (result)
        return ret_state, ret_str

class start_monitor_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "start_monitor", **args)
        self.help_str = "starts a monitor thread of device parameters"
        self.net_only = True
    def server_call(self, cm):
        if not cm:
            return "error need monitor_id"
        else:
            return self.module_info.send_thread(("start_monitor", cm[0]))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok"):
            return limits.nag_STATE_OK, result
        else:
            return limits.nag_STATE_CRITICAL, result

class stop_monitor_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "stop_monitor", **args)
        self.help_str = "stops a monitor thread of device parameters"
        self.net_only = True
    def server_call(self, cm):
        if not cm:
            return "error need monitor_id"
        else:
            return self.module_info.send_thread(("stop_monitor", cm[0]))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok"):
            return limits.nag_STATE_OK, result
        else:
            return limits.nag_STATE_CRITICAL, result

class monitor_info_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "monitor_info", **args)
        self.help_str = "returns info about a given monitor thread"
        self.net_only = True
    def server_call(self, cm):
        if not cm:
            return "error need monitor_id"
        else:
            return self.module_info.send_thread(("monitor_info", cm[0]))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok") or result.startswith("cok"):
            if result.startswith("ok"):
                in_dict = hm_classes.net_to_sys(result[3:])
            else:
                if bz2:
                    in_dict = hm_classes.net_to_sys(bz2.decompress(result[4:]))
                else:
                    return limits.nag_STATE_CRITICAL, "error cannot decompress bz2-encoded info"
            data_dict = in_dict["cache"]
            in_keys = sorted(data_dict.keys())
            # check for old or new-style monitor_info
            if in_dict.has_key("cache") and type(in_dict["cache"].values()[0]) == type({}):
                # old style
                ret_f = ["ok got %s, collecting data since %s" % (logging_tools.get_plural("parameter", len(in_keys)), time.ctime(in_dict["start_time"]))]
                ret_f.append("%-45s %6s %s" % ("Key", "count", " ".join(["%21s" % ("%s value" % (x.title())) for x in ["min", "mean", "max"]])))
                for in_key in in_keys:
                    in_val = data_dict[in_key]
                    if in_val.get("num", 0):
                        in_val["mean"] = in_val["tot"] / in_val["num"]
                    else:
                        in_val["mean"] = 0
                    loc_f = []
                    for v_t in ["min", "mean", "max"]:
                        in_val["v"] = in_val[v_t]
                        loc_f.append("%s %1s%-6s" % pretty_print2(in_val))
                    ret_f.append("%-45s %6d %s" % (".".join(["%-10s" % (x) for x in in_key.split(".")]), in_val["num"], " ".join(loc_f)))
                return limits.nag_STATE_OK, "\n".join(ret_f)
            else:
                # new style
                ret_f = ["ok got %s, collecting data since %s" % (logging_tools.get_plural("parameter", len(in_keys)), time.ctime(in_dict["start_time"]))]
                out_list = logging_tools.new_form_list()
                for mv_key in in_keys:
                    out_list.append(data_dict[mv_key].get_monitor_form_entry())
                return limits.nag_STATE_OK, "\n".join(ret_f + str(out_list).split("\n"))
        else:
            return limits.nag_STATE_CRITICAL, result

min_update_step = 5

class alert_object(object):
    def __init__(self, key, logger, num_dp, th_class, th, command):
        self.__key = key
        self.__logger = logger
        self.__th_class = th_class
        self.__th = th
        self.__command = command
        self.init_buffer(num_dp)
    def init_buffer(self, num_dp):
        self.__val_buffer = []
        self.__num_dp = num_dp
        self.log("init val_buffer, max_size is %d" % (num_dp))
    def add_value(self, val):
        self.__val_buffer.append(val)
        if len(self.__val_buffer) > self.__num_dp:
            self.__val_buffer.pop(0)
        if len(self.__val_buffer) == self.__num_dp:
            # check for alert
            if self.__th_class == "U":
                alert = len([1 for x in self.__val_buffer if x > self.__th]) == self.__num_dp
            else:
                alert = len([1 for x in self.__val_buffer if x < self.__th]) == self.__num_dp
            if alert:
                self.log("*** alert, threshold %.2f, %s: %s" % (self.__th, logging_tools.get_plural("value", self.__num_dp), ", ".join(["%.2f" % (x) for x in self.__val_buffer])))
                act_com = self.__command
                for src, dst in [("%k", self.__key),
                                 ("%v", ", ".join(["%.2f" % (x) for x in self.__val_buffer])),
                                 ("%t", "%.2f" % (self.__th)),
                                 ("%c" , self.__th_class)]:
                    act_com = act_com.replace(src, dst)
                stat, out = commands.getstatusoutput(act_com)
                lines = [x.rstrip() for x in out.split("\n") if x.rstrip()]
                self.log("*** calling command '%s' returned %d (%s):" % (act_com, stat, logging_tools.get_plural("line", len(lines))))
                for line in lines:
                    self.log("*** - %s" %(line))
        #print self.__key, self.__val_buffer
    def log(self, what):
        self.__logger.info("[mvect / ao %s, cl %s] %s" % (self.__key, self.__th_class, what))

class machine_vector(object):
    def __init__(self, module):
        self.module = module
        # actual dictionary, including full-length dictionary keys
        self.__act_dict = {}
        # actual keys, last keys
        self.__act_keys = set()
        # init external_sources
        #self.init_ext_src()
        #self.__alert_dict, self.__alert_dict_time = ({}, time.time())
        # key is in fact the timestamp
        self.__act_key, self.__changed = (0, True)
        self.__verbosity = module.process_pool.global_config["VERBOSE"]
        module.process_pool.register_vector_receiver(self._recv_vector)
        #self.__module_dict = module_dict
        for module in module.process_pool.module_list:
            if hasattr(module, "init_machine_vector"):
                if self.__verbosity:
                    self.log("calling init_machine_vector for module '%s'" % (module.name))
                try:
                    module.init_machine_vector(self)
                except:
                    self.log("error: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                    raise
        # delete external directories
        old_dir = "/tmp/.machvect_es"
        if os.path.isdir(old_dir):
            try:
                os.removedirs(old_dir)
            except:
                self.log("error removing old external directory %s: %s" % (old_dir,
                                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("removed old external directory %s" % (old_dir))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.module.process_pool.log("[mvect] %s" % (what), log_level)
    def _recv_vector(self, zmq_sock):
        try:
            rcv_com = server_command.srv_command(source=zmq_sock.recv_unicode())
        except:
            self.log("error interpreting data as srv_command: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            for in_vector in rcv_com.xpath(None, ".//*[@type='vector']"):
                for values_list in in_vector:
                    for cur_value in values_list:
                        self.set_from_external(hm_classes.mvect_entry(**cur_value.attrib))
            self.check_timeout()
            self.check_changed()
    def set_from_external(self, mvec):
        if mvec.name not in self:
            # register entry
            self.__act_dict[mvec.name] = mvec
            self.__changed = True
        else:
            # only update value
            self[mvec.name] = mvec.value
##    def check_for_alert_file_change(self, log_t):
##        if self.__module:
##            alert_file = self.__module.get_alert_file_name()
##            if os.path.isfile(alert_file):
##                last_time, file_time, act_time = (self.__alert_dict_time, os.stat(alert_file)[stat.ST_MTIME], time.time())
##                if not self.__alert_dict or file_time > last_time:
##                    self.__alert_dict_time, alert_dict = (act_time, {})
##                    try:
##                        a_lines = [[z.strip() for z in y.split(":")] for y in [x.strip() for x in file(alert_file, "r").read().split("\n")] if y]
##                    except:
##                        alert_dict = {}
##                    else:
##                        alert_dict = {}
##                        # format of alert lines:
##                        # key:number_of_datapoints:U|L(upper or lower threshold):threshold:command to execute#
##                        for line in a_lines:
##                            if len(line) == 5:
##                                key, num_dp, th_class, th, command = line
##                                log_t.info("Trying to parse alert_line '%s' ... " % (":".join(line)))
##                                try:
##                                    th_class = th_class.upper()
##                                    num_dp = int(num_dp)
##                                    if th_class not in ["U", "L"]:
##                                        raise ValueError, "threshold_class not U(pper) or L(ower)"
##                                    th = float(th)
##                                except:
##                                    log_t.error(" +++ Cannot parse line : %s" % (process_tools.get_except_info()))
##                                else:
##                                    log_t.info(" ... key '%s', %s, threshold_class %s, threshold %.2f, command to execute: '%s'" % (key, logging_tools.get_plural("datapoint", num_dp), {"U" : "Upper", "L" : "Lower"}[th_class], th, command))
##                                    alert_dict[key] = alert_object(key, log_t, num_dp, th_class, th, command)
##                            else:
##                                log_t.error("Cannot parse line %s: %d != 5" % (":".join(line), len(line)))
##                    self.__alert_dict = alert_dict
##                    #print "*", last_time,file_time,act_time, self.__alert_dict
##    def check_for_alerts(self, logger):
##        for alert_key in [key for key in self.__alert_dict.keys() if key in self.__act_dict.keys()]:
##            self.__alert_dict[alert_key].add_value(self.__act_dict[alert_key].value)
    def register_entry(self, name, default, info, unit="1", base=1, factor=1, **kwargs):
        # name is the key (first.second.third.fourth)
        # default is a default value
        # info is a description of the entry
        # unit is the (SI ;-))-symbol for the entry
        # base is the divider to derive the k/M/G-Values (1, 1000 or 1024)
        # factor is a number the values have to be multipilicated with in order to lead to a meaningful number (for example memory or df)
        self.__changed = True
        self.__act_dict[name] = hm_classes.mvect_entry(name, default=default, info=info, unit=unit, base=base, factor=factor)
    def get(self, name, default_value=None):
        return self.__act_dict.get(name, default_value)
    def __getitem__(self, key):
        return self.__act_dict[key]
    def has_key(self, key):
        return self.__act_dict.has_key(key)
    def __contains__(self, key):
        return key in self.__act_dict
    def unregister_entry(self, name):
        self.__changed = True
        if self.__act_dict.has_key(name):
            #print "Unregister "+name
            del self.__act_dict[name]
        else:
            self.log("Error: entry %s not defined" % (name), logging_tools.LOG_LEVEL_ERROR)
    def __setitem__(self, name, value):
        self.__act_dict[name].update(value)
    def _reg_update(self, log_t, name, value):
        if self.__act_dict.has_key(name):
            self.__act_dict[name].update(value)
        else:
            log_t.error("Error: unknown machvector-name '%s'" % (name))
#         if self.__act_dict.has_key(name):
#             if type(value) == type(self.__act_dict[name]["d"]):
#                 self.__act_dict[name]["v"] = value
#             else:
#                 if type(value) in [type(0), type(0L)] and type(self.__act_dict[name]["d"]) in [type(0), type(0L)]:
#                     self.__act_dict[name]["v"] = value
#                 else:
#                     log_t.log("reg_update, key %s: type of default (%s) and value (%s) differ, using float..." % (name, str(type(self.__act_dict[name]["d"])), str(type(value))))
#                     self.__act_dict[name]["v"] = float(value)
#         else:
#             log_t.log("Error: unknown machvector-name '%s'" % (name), logging_tools.LOG_LEVEL_ERROR)
#         #print "updates %s with value" % (name), value
#         return
    def check_changed(self):
        if self.__changed:
            # attention ! dict.keys() != copy.deppcopy(dict).keys()
            last_keys = copy.deepcopy(self.__act_keys)
            self.__act_keys = set(self.__act_dict.keys())
            self.__changed = False
            new_key = int(time.time())
            if new_key == self.__act_key:
                new_key += 1
            self.__act_key = new_key
            new_keys  = self.__act_keys - last_keys
            lost_keys = last_keys - self.__act_keys
            if new_keys:
                self.log("%s:" % (logging_tools.get_plural("new key", len(new_keys))))
                #for key_num, key in enumerate(sorted(new_keys)):
                #    self.log(" %3d : %s" % (key_num, key))
            if lost_keys:
                self.log("%s:" % (logging_tools.get_plural("lost key", len(lost_keys))))
                #for key_num, key in enumerate(sorted(lost_keys)):
                #    self.log(" %3d : %s" % (key_num, key))
            self.log("Machine_vector has changed, setting actual key to %d (%d keys)" % (self.__act_key, len(self.__act_dict)))
    def check_timeout(self):
        cur_time = time.time()
        rem_keys = [key for key, value in self.__act_dict.iteritems() if value.check_timeout(cur_time)]
        if rem_keys:
            self.log("removing %s because of timeout: %s" % (logging_tools.get_plural("key", len(rem_keys)),
                                                             ", ".join(sorted(rem_keys))))
            for rem_key in rem_keys:
                self.unregister_entry(rem_key)
            self.__changed = True
    def store_xml(self, srv_com):
        el_builder = srv_com.builder
        mach_vect = el_builder("machine_vector", version="%d" % (self.__act_key))
        mach_vect.extend([cur_mve.build_xml(el_builder) for cur_mve in self.__act_dict.itervalues()])
        srv_com["data"] = mach_vect
    def get_mvector(self):
        return (self.__act_key, [(key, self.__act_dict[key]) for key in self.__act_keys])
    def get_mvector_raw(self):
        return (self.__act_key, [self.__act_dict[key].value for key in self.__act_keys])
    def get_send_mvector(self):
        return (time.time(), self.__act_key, [self.__act_dict[key].value for key in self.__act_keys])
    #def flush_cache(self, name):
    #    self.__dict_list[name] = []
    def get_actual_key(self):
        return self.__act_key
    def get_act_dict(self):
        return self.__act_dict
    def update(self):#, esd=""):
        self.check_changed()
        # copy ref_dict to act_dict
        [value.update_default() for value in self.__act_dict.itervalues()]
        self.check_timeout()
        #if esd:
        #    self.check_external_sources(log_t, esd)
        #self.check_for_alert_file_change(log_t)
        for module in self.module.process_pool.module_list:
            if hasattr(module, "update_machine_vector"):
                module.update_machine_vector(self)
        self.check_changed()
        #self.check_for_alerts(log_t)
    def init_ext_src(self):
        self.ext_src = {}
        self.ext_src_dt = {}
    def set_ext_src(self, src):
        self.ext_src[src] = []
        self.set_ext_src_dt(src)
    def set_ext_src_dt(self, src):
        self.ext_src_dt[src] = time.time()
    def get_ext_src_dt(self, src):
        return self.ext_src_dt[src]
    def has_ext_src(self, src):
        return self.ext_src.has_key(src)
    def get_last_update(self, src):
        return self.ext_src[src]
##    def check_external_sources(self, log_t, esd):
##        act_time = time.time()
##        mvns_found = []
##        if os.path.isdir(esd):
##            try:
##                esd_files = os.listdir(esd)
##            except:
##                log_t.error("error reading entries from directory %s: %s" % (esd,
##                                                                             process_tools.get_except_info()))
##                esd_files = []
##            for fn in esd_files:
##                ffn = "%s/%s" % (esd, fn)
##                if fn.endswith(".mvd"):
##                    # machine vector definition
##                    mvn = fn.split(".")[0]
##                    mvns_found.append(mvn)
##                    if not self.has_ext_src(mvn):
##                        self.set_ext_src(mvn)
##                        log_t.info("Registering external mv-source '%s'" % (mvn))
##                        mvn_lines = [line_p for line_p in [line_s.split(":") for line_s in [line.strip() for line in file(ffn, "r").readlines()] if line_s] if len(line_p) >= 6]
##                        for line_p in mvn_lines:
##                            # mvv_timeout should in fact be a emv-local setting
##                            if len(line_p) == 6:
##                                name, default, info, unit, base, factor = line_p
##                                mvv_timeout = 300
##                            else:
##                                name, default, info, unit, base, factor, mvv_timeout = line_p
##                            try:
##                                mvv_timeout = int(mvv_timeout)
##                                if default.isdigit():
##                                    default_n = int(default)
##                                    base = int(base)
##                                    factor = int(factor)
##                                else:
##                                    default_n = float(default)
##                                    base = float(base)
##                                    factor = float(factor)
##                            except:
##                                log_t.error("Error adding mvector %s: %s" % (name, process_tools.get_except_info()))
##                            else:
##                                log_t.info("Adding mvector %s with default %s, info %s, unit %s, base %s and factor %s (mvv_timeout is %d)" % (name, default, info, unit, base, factor, mvv_timeout))
##                                self.reg_entry(name, default_n, info, unit, base, factor, mvv_timeout=mvv_timeout)
##                                self.ext_src[mvn].append(name)
##                    elif self.get_ext_src_dt(mvn) < os.stat(ffn)[stat.ST_MTIME]:
##                        self.set_ext_src_dt(mvn)
##                        log_t.info("Checking already registered external mv-source '%s'" % (mvn))
##                        mvn_lines = [line_p for line_p in [line_s.split(":") for line_s in [line.strip() for line in file(ffn, "r").readlines()] if line_s] if len(line_p) >= 6]
##                        for line_p in mvn_lines:
##                            # mvv_timeout should in fact be a emv-local setting
##                            if len(line_p) == 6:
##                                name, default, info, unit, base, factor = line_p
##                                mvv_timeout = 300
##                            else:
##                                name, default, info, unit, base, factor, mvv_timeout = line_p
##                            try:
##                                mvv_timeout = int(mvv_timeout)
##                                if default.isdigit():
##                                    default_n = int(default)
##                                    base = int(base)
##                                    factor = int(factor)
##                                else:
##                                    default_n = float(default)
##                                    base = float(base)
##                                    factor = float(factor)
##                            except:
##                                log_t.error("Error checking mvector %s: %s" % (name, process_tools.get_except_info()))
##                            else:
##                                if name in self.ext_src[mvn]:
##                                    log_t.info("  key %s already present")
##                                else:
##                                    log_t.info("Adding mvector %s with default %s, info %s, unit %s, base %s and factor %s (mvv_timeout is %d)" % (name, default, info, unit, base, factor, mvv_timeout))
##                                    self.reg_entry(name, default_n, info, unit, base, factor, mvv_timeout=mvv_timeout)
##                                    self.ext_src[mvn].append(name)
##                elif fn.endswith(".mvv"):
##                    act_mtime = os.path.getmtime(ffn)
##                    mvn = fn.split(".")[0]
##                    mvv_timeout = 300
##                    if mvn in self.ext_src:
##                        if self.ext_src[mvn]:
##                            mv_entry = self.get_entry(self.ext_src[mvn][0], None)
##                            if mv_entry:
##                                mvv_timeout = mv_entry.get_mvv_timeout()
##                    if abs(act_mtime - act_time) < mvv_timeout:
##                        if self.has_ext_src(mvn):
##                            mvv_lines = [z for z in [y.split(":") for y in [x.strip() for x in file(ffn, "r").readlines()] if y] if len(z) == 3]
##                            for name, tp, value in mvv_lines:
##                                if tp == "i":
##                                    value = int(value)
##                                else:
##                                    value = float(value)
##                                try:
##                                    self.reg_update(log_t, name, value)
##                                except:
##                                    log_t.error("Error calling reg_update(): %s" % (process_tools.get_except_info()))
##                        else:
##                            log_t.info("Found .mvv file for unknown emv '%s'" % (mvn))
##                    else:
##                        log_t.warning(".mvv file for emv '%s' is too old, removing" % (mvn))
##                        try:
##                            os.unlink(ffn)
##                        except:
##                            log_t.error("cannot remove '%s': %s" % (ffn,
##                                                                    process_tools.get_except_info()))
##                            
##        del_ext_s = []
##        for ext_s, ext_keys in self.ext_src.iteritems():
##            if ext_s not in mvns_found:
##                del_ext_s.append(ext_s)
##                log_t.info("External mv-source %s no more existent, removing %s (%s)" % (ext_s,
##                                                                                         logging_tools.get_plural("key", len(ext_keys)),
##                                                                                         ", ".join(ext_keys)))
##                for k in ext_keys:
##                    self.unreg_entry(k)
##        for del_ext in del_ext_s:
##            del self.ext_src[del_ext]
##        # delete 

class monitor_object(object):
    def __init__(self, name):
        self.__name = name
        self.__start_time, self.__counter = (time.time(), 0)
        self.__cache = {}
    def update(self, mv):
        self.__counter += 1
        for key, value in mv.get_act_dict().iteritems():
            if [True for item in MONITOR_OBJECT_INFO_LIST if key.startswith(item)]:
                if not self.__cache.has_key(key):
                    self.__cache[key] = hm_classes.mvect_entry(key,
                                                               default=value.default,
                                                               info=value.info,
                                                               base=value.base,
                                                               factor=value.factor,
                                                               unit=value.unit,
                                                               value=value.value,
                                                               monitor_value=True)
                else:
                    self.__cache[key].update(value.value)
    def get_start_time(self):
        return self.__start_time
    def get_info(self):
        return {"start_time" : self.__start_time,
                "cache"      : self.__cache}

def pretty_print(val, base):
    pf_idx = 0
    if base != 1:
        while val > base * 4:
            pf_idx += 1
            val = float(val) / base
    return val, ["", "k", "M", "G", "T", "E", "P"][pf_idx]

def pretty_print2(value):
    if value.has_key("u"):
        act_v, p_str = pretty_print(value["v"] * value["f"], value["b"])
        unit = value["u"]
    else:
        act_v, p_str = (value["v"], "")
        unit = "???"
    if type(act_v) in [type(0), type(0L)]:
        val = "%10d   " % (act_v)
    else:
        val = "%13.2f" % (act_v)
    return va, p_str, unit
    
def build_info_string(ref, info):
    ret_str = info
    refp = ref.split(".")
    for idx in range(len(refp)):
        ret_str = ret_str.replace("$%d" % (idx + 1), refp[idx])
    return ret_str
    
if __name__ == "__main__":
    print "Not an executable python script, exiting..."
    sys.exit(-2)
