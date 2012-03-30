#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 Andreas Lang-Nevyjel
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
""" cluster-server """

from __future__ import with_statement
import os
import os.path
import sys
import socket
import re
import time
import getopt
import net_tools
import Queue
import threading_tools
import mysql_tools
import MySQLdb
import commands
import pwd
import logging_tools
import process_tools
import configfile
import server_command
import pprint
import uuid_tools
import mail_tools
import difflib
import cs_base_class
import config_tools
import cProfile
import zmq

try:
    from cluster_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SERVER_PORT = 8004
SQL_ACCESS  = "cluster_full_access"

class call_params(object):
    def __init__(self, act_sc, **args):
        self.__glob_config, self.__loc_config = (args.get("g_config", None),
                                                 args.get("l_config", None))
        self.__server_idx = self.__loc_config["SERVER_IDX"]
        self.set_loc_ip()
        self.set_direct_call()
        self.set_server_command()
        self.set_option_dict_valid()
        self.set_nss_queue()
        self.set_dc()
        self.set_server_com_name(act_sc.get_name())
        self.set_src_host()
        self.set_ret_str()
        self.set_call_finished()
        self.set_thread_pool()
        self.set_server_idx()
        self.restart_hook_function = None
    def __del__(self):
        pass
    def close(self):
        if self.dc:
            self.dc.release()
            self.dc = None
    def install_restart_hook(self, func, add_data):
        self.restart_hook_function = func
        self.restart_hook_data = add_data
        self.restarted = 0
    def check_for_restart(self):
        if self.restart_hook_function:
            self.restarted = self.restart_hook_function(self.restart_hook_data)
            return self.restarted
        else:
            return 0
    def set_server_idx(self, s_idx=0):
        self.__server_idx = s_idx
    def get_server_idx(self):
        return self.__server_idx
    def set_thread_pool(self, tp=None):
        self.__thread_pool = tp
    def get_thread_pool(self):
        return self.__thread_pool
    def get_g_config(self):
        return self.__glob_config
    def get_l_config(self):
        return self.__loc_config
    def set_call_finished(self, cf=0):
        self.call_finished = cf
    def get_call_finished(self):
        return self.call_finished
    def set_ret_str(self, ret_str="not set"):
        if type(ret_str) == type(""):
            self.ret_str = ret_str
        else:
            self.ret_str = "%d: %s" % (ret_str.get_state(), ret_str.get_result())
    def set_src_host(self, src_host = "unknown", src_port=0):
        self.src_host = src_host
        self.src_port = src_port
    def set_server_com_name(self, sc_name):
        self.sc_name = sc_name
    def set_dc(self, dc=None):
        self.dc = dc
    def set_logger(self, logger):
        self.logger = logger
    def get_logger(self):
        return self.logger
    def set_nss_queue(self, nss_q = None):
        self.nss_queue = nss_q
    def set_loc_ip(self, loc_ip=None):
        self.loc_ip = loc_ip
    def set_direct_call(self, dc=0):
        self.direct_call = dc
    def get_direct_call(self):
        return self.direct_call
    def set_server_command(self, server_com=None):
        self.server_com = server_com
        self.set_option_dict_valid()
        if self.server_com:
            self.opt_str, self.opt_dict = (self.server_com.get_option_dict() and self.server_com.get_option_dict_info() or "<NONE>",
                                           self.server_com.get_option_dict())
        else:
            self.opt_str, self.opt_dict = ("<no server_com>", {})
    def link_with_command(self, s_com=None):
        if self.server_com:
            opts_found = [k for k in s_com.needed_option_keys if k in self.opt_dict.keys()]
            if len(opts_found) == len(s_com.needed_option_keys):
                self.set_option_dict_valid(1)
            else:
                self.missing_option_keys = [x for x in s_com.needed_option_keys if x not in opts_found]
    def set_option_dict_valid(self, valid=0):
        self.option_dict_valid = valid
    def get_option_dict_valid(self):
        return self.option_dict_valid
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.logger:
            self.logger.log(level, "%s: %s" % (self.sc_name, what))
        else:
            logging_tools.my_syslog("%s: %s" % (self.sc_name, what), level)
    def write_start_log(self, act_sc):
        if act_sc.get_write_log():
            self.log("Got command %s (options %s) from host %s (port %d) to %s, %s: %s" % (self.server_com.get_command(),
                                                                                           self.opt_str,
                                                                                           self.src_host,
                                                                                           self.src_port,
                                                                                           self.loc_ip,
                                                                                           logging_tools.get_plural("config", len(act_sc.get_config_list())),
                                                                                           act_sc.get_config()))
    def write_end_log(self, act_sc):
        if act_sc.get_write_log():
            ins_id = mysql_tools.device_log_entry(self.dc, self.__server_idx, self.__loc_config["LOG_SOURCE_IDX"], 0, self.__loc_config["LOG_STATUS"]["i"]["log_status_idx"], "command %s from %s, result: %s" % (self.server_com.get_command(), self.src_host, self.ret_str))
            mysql_tools.ext_device_log_entry(self.dc, ins_id, self.__loc_config["LOG_SOURCE_IDX"], 0, "cluster-server", "Cluster-Server entry", "\n".join(["From    : %s" % (self.src_host),
                                                                                                                                                           "Command : %s" % (self.server_com.get_command()),
                                                                                                                                                           "Options : %s" % (self.opt_str),
                                                                                                                                                           "Result  : %s" % (self.ret_str), ""]))
        
def process_request(glob_config, loc_config, logger, db_con, server_com, src_host, src_port, direct_com, loc_ip, nss_queue, bg_queue, bg_commands, thread_pool):
    commands_queued = []
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except:
        ret_str = "error connecting to SQL-server"
    else:
        if loc_ip == "127.0.0.1":
            # map loc_ip to something meaningful
            stat, out = commands.getstatusoutput("/sbin/ifconfig")
            self_ips = []
            for line in [x for x in [y.strip() for y in out.strip().split("\n")] if x.startswith("inet")]:
                ip_re = re.match("^inet.*addr:(?P<ip>\S+)\s+.*$", line)
                if ip_re and ip_re.group("ip") != "127.0.0.1":
                    self_ips.append(ip_re.group("ip"))
            if self_ips:
                loc_ip = self_ips.pop(0)
        if server_com.get_command() in loc_config["COM_LIST"]:
            act_sc = loc_config["COM_DICT"][server_com.get_command()]
            act_call_params = call_params(act_sc,
                                          g_config=glob_config,
                                          l_config=loc_config)
            act_call_params.set_src_host(src_host, src_port)
            act_call_params.set_loc_ip(loc_ip)
            act_call_params.set_server_command(server_com)
            act_call_params.set_nss_queue(nss_queue)
            act_call_params.set_thread_pool(thread_pool)
            act_call_params.set_server_idx(loc_config["SERVER_IDX"])
            act_call_params.set_logger(logger)
            bg_command = False
            doit, srv_origin, err_str = act_sc.check_config(dc, loc_config, loc_config["FORCE"] or act_call_params.opt_dict.get("force", 0))
            if doit:
                act_call_params.link_with_command(act_sc)
                act_call_params.write_start_log(act_sc)
                if act_call_params.get_option_dict_valid():
                    if act_sc.get_blocking_mode() or direct_com:
                        act_call_params.set_dc(dc)
                        act_call_params.set_direct_call(direct_com)
                        if direct_com:
                            ret_str = act_sc(act_call_params)
                        else:
                            try:
                                ret_str = act_sc(act_call_params)
                            except:
                                exc_info = sys.exc_info()
                                long_exc_info = process_tools.exception_info()
                                ret_str = "error Something went badly wrong (%s) ..." % (process_tools.get_except_info())
                                act_call_params.log("*** INTERNAL ERROR: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                                for line in long_exc_info.log_lines:
                                    act_call_params.log("***: %s" % (line), logging_tools.LOG_LEVEL_CRITICAL)
                    else:
                        if act_sc.get_name() in bg_commands:
                            if act_sc.get_is_restartable():
                                logger.warning("command %s already running in the background, restarting ..." % (act_sc.get_name()))
                                #bg_queue.put(bg_restart_message((act_sc, act_call_params)))
                                bg_queue.put(("bg_task_restart", (act_sc, act_call_params)))
                                ret_str = "warn restarting %s in the background" % (server_com.get_command())
                            else:
                                logger.error("command %s already running in the background, ignoring request ..." % (act_sc.get_name()))
                                ret_str = "error %s already running in the background" % (server_com.get_command())
                        else:
                            #bg_queue.put(bg_start_message((act_sc, act_call_params)))
                            bg_queue.put(("start_bg_task", (act_sc, act_call_params)))
                            ret_str = "ok submitting %s to the background" % (server_com.get_command())
                            commands_queued.append(act_sc.get_name())
                        bg_command = True
                else:
                    act_call_params.set_dc(dc)
                    ret_str = "error missing keys in option_dict: %s" % (", ".join(act_call_params.missing_option_keys))
                if not bg_command:
                    act_call_params.set_ret_str(ret_str)
                    act_call_params.write_end_log(act_sc)
            else:
                act_call_params.set_dc(dc)
                ret_str = err_str
                act_call_params.set_ret_str(ret_str)
                ret_str = "error %s" % (err_str)
            if not bg_command:
                act_call_params.close()
                dc = None
                del act_call_params
                del act_sc
        else:
            guess_list = ", ".join(difflib.get_close_matches(server_com.get_command(), loc_config["COM_LIST"]))
            ret_str = server_command.server_reply(state=server_command.SRV_REPLY_STATE_WARN,
                                                  result="command %s not known (did you meant: %s)" % (server_com.get_command(),
                                                                                                       guess_list or "<none found>"))
        if dc:
            dc.release()
    logger.info(type(ret_str) == type("") and ret_str or "%d: %s" % (ret_str.get_state(), ret_str.get_result()))
    return ret_str, commands_queued

class bg_stuff(object):
    def __init__(self, name, logger, glob_config, loc_config):
        self.__name = name
        self.__logger = logger
        self.glob_config, self.loc_config = (glob_config, loc_config)
        self.set_creates_machvector(False)
        self.set_min_time_between_runs(0)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(level, "%s: %s" % (self.__name, what))
    def set_creates_machvector(self, cv):
        self.__cv = cv
    def get_creates_machvector(self):
        return self.__cv
    def set_min_time_between_runs(self, mt):
        # mt is in seconds
        self.__min_time_br = mt
        self.__last_wakeup = None
    def get_min_time_between_runs(self):
        return self.__min_time_br
    def check_for_wakeup(self, act_time):
        if self.__last_wakeup is None or abs(self.__last_wakeup - act_time) >= self.__min_time_br:
            self.__last_wakeup = act_time
            return True
        else:
            return False
    def send_mail(self, to_addr, subject, msg_body):
        new_mail = mail_tools.mail(subject, "%s@%s" % (self.glob_config["FROM_NAME"], self.glob_config["FROM_ADDR"]), to_addr, msg_body)
        new_mail.set_server(self.glob_config["MAILSERVER"], self.glob_config["MAILSERVER"])
        stat, log_lines = new_mail.send_mail()
        return log_lines

class usv_server_stuff(bg_stuff):
    def __init__(self, logger, glob_config, loc_config):
        bg_stuff.__init__(self, "usv", logger, glob_config, loc_config)
        self.set_creates_machvector(True)
    def do_apc_call(self):
        stat, out = commands.getstatusoutput("apcaccess")
        if stat:
            self.log("cannot execute apcaccess (stat=%d): %s" % (stat, str(out)),
                     logging_tools.LOG_LEVEL_ERROR)
            apc_dict = {}
        else:
            apc_dict = dict([(l_part[0].lower().strip(), l_part[1].strip()) for l_part in [line.strip().split(":", 1) for line in out.split("\n")] if len(l_part) == 2])
        return apc_dict
    def init_machvector(self):
        ret_list = []
        apc_dict = self.do_apc_call()
        if apc_dict:
            for key, value in apc_dict.iteritems():
                if key == "linev":
                    ret_list.append("usv.volt.line:0.:Line Voltage:Volt:1:1")
                elif key == "loadpct":
                    ret_list.append("usv.percent.load:0.:Percent Load Capacity:%:1:1")
                elif key == "bcharge":
                    ret_list.append("usv.percent.charge:0.:Battery Charge:%:1:1")
                elif key == "timeleft":
                    ret_list.append("usv.time.left:0.:Time Left in Minutes:1:1:1")
                elif key == "itemp":
                    ret_list.append("usv.temp.int:0.:Internal Temperature:C:1:1")
        return ret_list
    def get_machvector(self):
        ret_list = []
        apc_dict = self.do_apc_call()
        if apc_dict:
            for key, value in apc_dict.iteritems():
                if value.split():
                    first_v = value.split()[0]
                    if key == "linev":
                        ret_list.append("usv.volt.line:f:%.2f" % (float(first_v)))
                    elif key == "loadpct":
                        ret_list.append("usv.percent.load:f:%.2f" % (float(first_v)))
                    elif key == "bcharge":
                        ret_list.append("usv.percent.charge:f:%.2f" % (float(first_v)))
                    elif key == "timeleft":
                        ret_list.append("usv.time.left:f:%.2f" % (float(first_v)))
                    elif key == "itemp":
                        ret_list.append("usv.temp.int:f:%.2f" % (float(first_v)))
        return ret_list

class quota_line(object):
    def __init__(self, line_p):
        self.__uid = int(line_p.pop(0)[1:])
        self.__quota_flags = line_p.pop(0)
        # parse 3 blocks fields
        self.__blocks_used = int(line_p.pop(0))
        self.__blocks_soft = int(line_p.pop(0))
        self.__blocks_hard = int(line_p.pop(0))
        if line_p[0].isdigit():
            self.__blocks_grace = ""
        else:
            self.__blocks_grace = line_p.pop(0)
        # parse 3 files fields
        self.__files_used = int(line_p.pop(0))
        self.__files_soft = int(line_p.pop(0))
        self.__files_hard = int(line_p.pop(0))
        if not line_p:
            self.__files_grace = ""
        else:
            self.__files_frace = line_p.pop(0)
    def get_block_dict(self):
        return {"used"  : self.__blocks_used,
                "soft"  : self.__blocks_soft,
                "hard"  : self.__blocks_hard,
                "grace" : self.__blocks_grace}
    def get_file_dict(self):
        return {"used"  : self.__files_used,
                "soft"  : self.__files_soft,
                "hard"  : self.__files_hard,
                "grace" : self.__files_grace}
    def get_info_str(self, in_dict):
        return "%d / %d / %d%s" % (in_dict["used"],
                                   in_dict["soft"],
                                   in_dict["hard"],
                                   in_dict["grace"] and " / %s" % (in_dict["grace"]) or "")
    def quotas_defined(self):
        return self.__blocks_soft or self.__blocks_hard
    def get_uid(self):
        return self.__uid
    def __repr__(self):
        return "quota info, uid %d, flags %s, block_info: %s, file_info: %s" % (self.__uid,
                                                                                self.__quota_flags,
                                                                                self.get_info_str(self.get_block_dict()),
                                                                                self.get_info_str(self.get_file_dict()))
    def check_dict(self, in_dict):
        is_ok = True
        if in_dict["soft"] and in_dict["used"] >= in_dict["soft"]:
            is_ok = False
        if in_dict["hard"] and in_dict["used"] >= in_dict["hard"]:
            is_ok = False
        return is_ok
    def check_for_blocks(self):
        return self.check_dict(self.get_block_dict())
    def check_for_files(self):
        return self.check_dict(self.get_file_dict())
    def everything_ok(self):
        return self.check_for_blocks() and self.check_for_files()
    def create_prob_str(self, name, in_dict, block_s):
        p_f = []
        if in_dict["soft"] and in_dict["used"] >= in_dict["soft"]:
            p_f.append("soft quota (%s > %s)" % (logging_tools.get_size_str(in_dict["used"] * block_s, False, 1000),
                                                 logging_tools.get_size_str(in_dict["soft"] * block_s, False, 1000)))
        if in_dict["hard"] and in_dict["used"] >= in_dict["hard"]:
            p_f.append("hard quota (%s > %s)" % (logging_tools.get_size_str(in_dict["used"] * block_s, False, 1000),
                                                 logging_tools.get_size_str(in_dict["hard"] * block_s, False, 1000)))
        return "%s for %ss" % (" and ".join(p_f), name)
    def get_prob_str(self, block_s):
        p_f = []
        if not self.check_for_blocks():
            p_f.append(self.create_prob_str("block", self.get_block_dict(), block_s))
        if not self.check_for_files():
            p_f.append(self.create_prob_str("file", self.get_file_dict(), 1))
        return "; ".join(p_f)

class quota_stuff(bg_stuff):
    def __init__(self, logger, db_con, glob_config, loc_config):
        bg_stuff.__init__(self, "quota", logger, glob_config, loc_config)
        self.__db_con = db_con
        self.set_min_time_between_runs(self.glob_config["QUOTA_CHECK_TIME_SECS"])
        self.set_creates_machvector(self.glob_config["MONITOR_QUOTA_USAGE"])
        # user cache
        self.__user_dict = {}
        # quota cache, (device, uid, stuff)
        self.__quota_cache = []
        # last mail sent to admins
        self.__admin_mail_sent = None
    def _resolve_uids(self, dc, uid_list):
        if uid_list:
            dc.execute("SELECT u.uid, u.login, u.uservname, u.usernname, u.useremail FROM user u WHERE %s" % (" OR ".join(["u.uid=%d" % (x) for x in uid_list])))
            for db_rec in dc.fetchall():
                if self.__user_dict.has_key(db_rec["uid"]):
                    # check for new settings
                    for key, value in [("source"    , "SQL"              ),
                                       ("uid"       , db_rec["uid"]      ),
                                       ("login"     , db_rec["login"]    ),
                                       ("email"     , db_rec["useremail"]),
                                       ("firstname" , db_rec["uservname"]),
                                       ("lastname"  , db_rec["usernname"])]:
                        self.__user_dict[db_rec["uid"]][key] = value
                else:
                    # new record
                    self.__user_dict[db_rec["uid"]] = {"source"    : "SQL",
                                                       "uid"       : db_rec["uid"],
                                                       "login"     : db_rec["login"],
                                                       "email"     : db_rec["useremail"],
                                                       "firstname" : db_rec["uservname"],
                                                       "lastname"  : db_rec["usernname"]}
                act_dict = self.__user_dict[db_rec["uid"]]
                act_dict["info"] = "uid %d, login %s (from SQL), (%s %s, %s)" % (act_dict["uid"],
                                                                                 act_dict["login"],
                                                                                 act_dict["firstname"] or "<vname not set>",
                                                                                 act_dict["lastname"] or "<nname not set>",
                                                                                 act_dict["email"] or "<email not set>")
        missing_uids = [key for key in uid_list if not self.__user_dict.has_key(key)]
        for missing_uid in missing_uids:
            try:
                pw_stuff = pwd.getpwuid(missing_uid)
            except:
                self.log("Cannot get information for uid %d" % (missing_uid),
                         logging_tools.LOG_LEVEL_ERROR)
                self.__user_dict[missing_uid] = {"info" : "user not found in SQL or pwd"}
            else:
                self.__user_dict[missing_uid] = {"source" : "pwd",
                                                 "login"  : pw_stuff[0],
                                                 "info"   : "uid %d, login %s (from pwd)" % (missing_uid, pw_stuff[0])}
        # add missing keys
        for uid, u_stuff in self.__user_dict.iteritems():
            u_stuff.setdefault("last_mail_sent", None)
    def _get_uid_info(self, uid, default=None):
        return self.__user_dict.get(uid, None)
    def init_machvector(self):
        self.wakeup()
        ret_list = []
        for dev_name, uid, u_stuff in self.__quota_cache:
            u_name = self._get_uid_info(uid, {}).get("login", "unknown")
            ret_list.extend(["quota.%s.%s.soft:0:Soft Limit for user $3 on $2:B:1000:1000" % (dev_name, u_name),
                             "quota.%s.%s.hard:0:Hard Limit for user $3 on $2:B:1000:1000" % (dev_name, u_name),
                             "quota.%s.%s.used:0:Used quota for user $3 on $2:B:1000:1000" % (dev_name, u_name)])
        return ret_list
    def get_machvector(self):
        ret_list = []
        for dev_name, uid, u_stuff in self.__quota_cache:
            u_name = self._get_uid_info(uid, {}).get("login", "unknown")
            block_dict = u_stuff.get_block_dict()
            ret_list.extend(["quota.%s.%s.soft:i:%d" % (dev_name, u_name, block_dict["soft"]),
                             "quota.%s.%s.hard:i:%d" % (dev_name, u_name, block_dict["hard"]),
                             "quota.%s.%s.used:i:%d" % (dev_name, u_name, block_dict["used"])])
        return ret_list
    def wakeup(self):
        qc_stime = time.time()
        sep_str = "-" * 64
        dc = self.__db_con.get_connection(SQL_ACCESS)
        self.log(sep_str)
        self.log("starting quotacheck")
        q_cmd = "repquota -aniu"
        stat, out = commands.getstatusoutput(q_cmd)
        if stat:
            self.log("Cannot call '%s' (stat=%d): %s" % (q_cmd, stat, str(out)),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            q_dict = {}
            act_dev = None
            for line in [x.strip() for x in out.split("\n") if x.strip()]:
                if line.startswith("***"):
                    act_dev = line.split()[-1]
                elif line.startswith("#"):
                    line_p = line.split()
                    try:
                        q_line = quota_line(line_p)
                    except:
                        self.log("cannot parse quota_line '%s': %s" % (line,
                                                                       process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        if act_dev:
                            q_dict.setdefault(act_dev, {})[q_line.get_uid()] = q_line
                        else:
                            self.log("No device known for line '%s'" % (q_line),
                                     logging_tools.LOG_LEVEL_WARN)
            prob_users, prob_devs = ({}, {})
            mtab_dict = dict([(k, (a, b, c)) for k, a, b, c in [x.strip().split()[:4] for x in file("/etc/mtab", "r").read().split("\n") if x.startswith("/") and len(x.split()) > 3]])
            if self.glob_config["MONITOR_QUOTA_USAGE"]:
                self.__quota_cache = []
            missing_uids = set()
            for dev, u_dict in q_dict.iteritems():
                try:
                    osres = os.statvfs(dev)
                except:
                    self.log("cannot do an statvfs() on %s: %s" % (dev,
                                                                   process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    #f_frsize = osres[statvfs.F_FRSIZE]
                    f_frsize = 1024
                    for uid, u_stuff in u_dict.iteritems():
                        if self.glob_config["MONITOR_QUOTA_USAGE"]:
                            if u_stuff.quotas_defined():
                                missing_uids.add(uid)
                                self.__quota_cache.append((dev, uid, u_stuff))
                        if not u_stuff.everything_ok():
                            prob_users.setdefault(uid, {})[dev] = u_stuff.get_prob_str(f_frsize)
                            prob_devs.setdefault(dev, mtab_dict.get(dev, ("unknown mountpoint",
                                                                          "unknown fstype",
                                                                          "unknown flags")))
            self._resolve_uids(dc, list(set(prob_users.keys() + list(missing_uids))))
            if prob_devs:
                mail_lines, email_users = ({"admins" : []},
                                           ["admins"])
                log_line = "%s violated the quota policies on %s" % (logging_tools.get_plural("user", len(prob_users.keys())),
                                                                     logging_tools.get_plural("device", len(prob_devs.keys())))
                self.log(log_line)
                mail_lines["admins"].extend(["Servername: %s" % (self.loc_config["SERVER_FULL_NAME"]),
                                             log_line,
                                             "",
                                             "device info:",
                                             ""])
                # device overview
                for prob_dev, pd_info in prob_devs.iteritems():
                    log_line = "%s: mounted on %s (flags %s), fstype is %s" % (prob_dev,
                                                                               pd_info[0],
                                                                               pd_info[2],
                                                                               pd_info[1])
                    self.log(log_line)
                    mail_lines["admins"].append(log_line)
                if not self.__admin_mail_sent or abs(self.__admin_mail_sent - time.time()) > self.glob_config["USER_MAIL_SEND_TIME"]:
                    self.__admin_mail_sent = time.time()
                else:
                    email_users.remove("admins")
                mail_lines["admins"].extend(["", "user info:", ""])
                for uid, u_stuff in prob_users.iteritems():
                    user_info = self._get_uid_info(uid)
                    mail_lines[uid] = ["This is an informal mail to notify you that",
                                       "you have violated one or more quota-policies",
                                       "on %s, user info: %s" % (self.loc_config["SERVER_FULL_NAME"], user_info["info"]),
                                       ""]
                    if user_info.get("email", ""):
                        if uid not in email_users:
                            # only send mail if at least USER_MAIL_SEND_TIME seconds
                            if not user_info["last_mail_sent"] or abs(user_info["last_mail_sent"] - time.time()) > self.glob_config["USER_MAIL_SEND_TIME"]:
                                email_users.append(uid)
                                user_info["last_mail_sent"] = time.time()
                        mail_lines["admins"].append("%s (send mail to %s)" % (user_info["info"],
                                                                              user_info["email"]))
                    else:
                        mail_lines["admins"].append("%s (no email-address set)" % (user_info["info"]))
                    self.log(user_info["info"])
                    for dev, d_stuff in u_stuff.iteritems():
                        log_line = " --- violated %s on %s" % (d_stuff, dev)
                        mail_lines["admins"].append(log_line)
                        mail_lines[uid].append(log_line)
                        self.log(log_line)
                    mail_lines[uid].extend(["",
                                            "please delete some of your data from the respective devices.",
                                            "",
                                            "Thank you in advance,",
                                            "regards"])
                self.log("Sending %s" % (logging_tools.get_plural("mail", len([u_name for u_name in email_users if u_name != "admins"]))))
                for email_user in email_users:
                    if email_user == "admins":
                        to_addrs = self.glob_config["QUOTA_ADMINS"].split(",")
                    else:
                        to_addrs = [self._get_uid_info(email_user)["email"]]
                    for to_addr in to_addrs:
                        log_lines = self.send_mail(to_addr,
                                                   "quota warning from %s@%s" % (self.loc_config["SERVER_FULL_NAME"],
                                                                                 process_tools.get_cluster_name()),
                                                   mail_lines[email_user])
                        for log_line in log_lines:
                            self.log(log_line)
        dc.release()
        qc_etime = time.time()
        self.log("quotacheck took %s" % (logging_tools.get_diff_time_str(qc_etime - qc_stime)))
        self.log(sep_str)

def server_code(db_con, glob_config, loc_config, server_com=None):
    logger = logging_tools.get_logger(glob_config["LOG_NAME"],
                                      glob_config["LOG_DESTINATION"],
                                      init_logger=True)
    thread_pool = server_thread_pool(logger, db_con, glob_config, loc_config, server_com)
    if server_com:
        if loc_config["CONTACT"]:
            thread_pool.set_target("localhost", SERVER_PORT)
        thread_pool.thread_loop()
        was_error, ret_str = thread_pool.get_client_ret_state()
        if was_error:
            ret_state = 1
        else:
            ret_state = 0
        if type(ret_str) == type(""):
            print "%d: %s" % (ret_state, ret_str)
        else:
            print "%d: %s" % (ret_str.get_state(), ret_str.get_result())
            my_pp = pprint.PrettyPrinter(indent=0)
            if ret_str.get_option_dict():
                opt_dict = ret_str.get_option_dict()
                opt_keys = sorted(opt_dict.keys())
                print "option dict found with %s:" % (logging_tools.get_plural("key", len(opt_keys)))
                for key in opt_keys:
                    print " - %s :\n%s" % (key, my_pp.pformat(opt_dict[key]))
    else:
        thread_pool.thread_loop()
    logger.info("CLOSE")
    return 0

class background_thread(threading_tools.thread_obj):
    def __init__(self, db_con, ss_queue, glob_config, loc_config, logger):
        self.__db_con = db_con
        self.__socket_server_queue = ss_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__logger = logger
        threading_tools.thread_obj.__init__(self, "background", queue_size=50)
        self.register_func("start_bg_task", self._start_bg_task)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__socket_server_queue.put(("set_bg_queue", self.get_thread_queue()))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _get_bg_queue(self, ret_queue):
        ret_queue.put(("bg_queue", self.get_thread_queue()))
    def _check_for_restart(self, in_data):
        in_queue, com_name = in_data
        add_messages = []
        it, restart = (True, False)
        while it:
            try:
                in_mes = in_queue.get_nowait()
            except Queue.Empty:
                break
            else:
                if type(in_mes) == type(()):
                    m_type, m_stuff = in_mes
                    if m_type == "bg_task_restart" and m_stuff[0].get_name() == com_name:
                        restart = True
                        in_mes = None
                if in_mes:
                    add_messages.append(in_mes)
        # re-insert messages
        for add_mes in add_messages:
            in_queue.put(add_mes)
        return restart
    def _start_bg_task(self, (act_sc, act_call)):
        act_call.set_logger(self.__logger)
        self.log("receivce START_BG request for command %s" % (act_sc.get_name()))
        dc = self.__db_con.get_connection(SQL_ACCESS)
        act_call.set_dc(dc)
        runs = 0
        while True:
            runs += 1
            if act_sc.get_is_restartable():
                act_call.install_restart_hook(self._check_for_restart, [self.get_thread_queue(), act_sc.get_name()])
            try:
                ret_str = act_sc(act_call)
            except:
                exc_info = sys.exc_info()
                ret_str = "error Something went badly wrong (%s) ..." % (process_tools.get_except_info())
                act_call.log("*** INTERNAL ERROR: %s" % (process_tools.get_except_info()))
            self.log(ret_str)
            if act_sc.get_is_restartable():
                if act_call.restarted:
                    self.log("restarting command...")
                else:
                    break
        act_call.close()
        self.log("command %s finished after %s" % (act_sc.get_name(),
                                                   logging_tools.get_plural("run", runs)))
        self.__socket_server_queue.put(("bg_task_finish", (act_sc.get_name(), act_call)))

class socket_server_thread(threading_tools.thread_obj):
    def __init__(self, db_con, glob_config, loc_config, ns, logger):
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__net_server = ns
        self.__logger = logger
        threading_tools.thread_obj.__init__(self, "socket_server", queue_size=50)
        self.register_func("bg_task_finish", self._bg_task_finish)
        self.register_func("in_tcp_bytes", self._tcp_in)
        self.register_func("in_udp_bytes", self._udp_in)
        self.register_func("set_bg_queue", self._set_bg_queue)
        self.register_func("send_broadcast", self._send_broadcast)
        self.register_func("send_error", self._send_error)
        self.register_func("send_ok", self._send_ok)
        self.register_func("contact_server", self._contact_server)
        # background commands
        self.__bg_commands = []
        # unique key list
        self.__ukey_list = []
        # wait dict
        self.__wait_dict = {}
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _set_bg_queue(self, bg_queue):
        self.__bg_queue = bg_queue
    def _bg_task_finish(self, (sc_name, call_params)):
        if sc_name not in self.__bg_commands:
            self.log("*** error, command %s not in bg_command_list (%s)" % (sc_name,
                                                                            ", ".join(self.__bg_commands)),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("removing %s from bg_command_list" % (sc_name))
            self.__bg_commands.remove(sc_name)
            if self.__bg_commands:
                self.log("%s queued: %s" % (logging_tools.get_plural("command", len(self.__bg_commands)),
                                            ", ".join(self.__bg_commands)))
            else:
                self.log("no commands running in the background")
    def _udp_in(self, (in_data, frm)):
        src_host, src_port = frm
        try:
            u_key, command = in_data.split(None, 1)
        except:
            self.log("error decoding udp_data '%s' from %s: %s" % (in_data, str(frm), process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("got udp_command %s (key %s) from %s" % (command, u_key, str(frm)))
            if u_key in self.__ukey_list:
                self.log("key %s already in list, ignoring request ..." % (u_key))
            else:
                server_com = server_command.server_command(command = command)
                server_com.set_compat(1)
                ret_str, coms_queued = process_request(self.__glob_config, self.__loc_config, self.__logger, self.__db_con, server_com, src_host, src_port, 0, "0.0.0.0", self.get_thread_queue(), self.__bg_queue, self.__bg_commands, self.get_thread_pool())
                self.__ukey_list.append(u_key)
                self._do_server_broadcast(u_key, command)
    def _tcp_in(self, tcp_stuff):
        in_data = tcp_stuff.get_decoded_in_str()
        try:
            server_com = server_command.server_command(in_data)
        except:
            com_split = in_data.split()
            server_com = server_command.server_command(command = com_split.pop(0))
            server_com.set_option_dict(dict([(k, v) for k, v in [z for z in [x.split(":", 1) for x in com_split] if len(z) == 2]]))
            server_com.set_compat(1)
        tcp_stuff.set_command(server_com.get_command())
        ret_str, coms_queued = process_request(self.__glob_config, self.__loc_config, self.__logger, self.__db_con, server_com, tcp_stuff.get_src_host(), tcp_stuff.get_src_port(), 0, tcp_stuff.get_loc_host(), self.get_thread_queue(), self.__bg_queue, self.__bg_commands, self.get_thread_pool())
        for com_queued in coms_queued:
            self.__bg_commands.append(com_queued)
        if self.__bg_commands:
            self.log("%s queued: %s" % (logging_tools.get_plural("command", len(self.__bg_commands)),
                                        ", ".join(self.__bg_commands)))
        if type(ret_str) == type(""):
            server_reply = server_command.server_reply()
            server_reply.set_ok_result(ret_str)
        else:
            server_reply = ret_str
        tcp_stuff.add_to_out_buffer(server_reply)
    def _send_broadcast(self, bc_com):
        unique_key = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time()))
        self._do_server_broadcast(unique_key, bc_com)
    def _contact_server(self, (srv_name, srv_ip, srv_port, srv_com)):
        self.log("Sending %s to device '%s' (IP %s, port %d)" % (srv_com, srv_name, srv_ip, srv_port))
        self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con, target_host=srv_ip, target_port=srv_port, bind_retries=1, rebind_wait_time=1, connect_state_call=self._udp_connect, connect_timeout_call=self._connect_timeout, timeout=10, add_data=srv_com))
    def _connect_timeout(self, sock):
        self.log("connect timeout", logging_tools.LOG_LEVEL_ERROR)
        sock.close()
    def _new_tcp_con(self, sock):
        return simple_con("tcp", sock.get_target_host(), sock.get_target_port(), sock.get_add_data(), self.get_thread_queue())
    def _do_server_broadcast(self, u_key, bc_com):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        send_str = "%s %s" % (u_key, bc_com)
        self.log("Initiating server-broadcast command '%s', key %s" % (bc_com, u_key))
        dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE n.device=%d" % (self.__loc_config["SERVER_IDX"]))
        my_netdev_idxs = [x["netdevice_idx"] for x in dc.fetchall()]
        if my_netdev_idxs:
            # start sending of nscd_reload commands
            dc.execute("SELECT d.name, i.ip, h.value FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg INNER JOIN device_type dt INNER JOIN " + \
                       "hopcount h INNER JOIN netdevice n INNER JOIN netip i LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND dg.device_group_idx=d.device_group AND " + \
                       "dc.new_config=c.new_config_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND c.name='server' AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND " + \
                       "h.s_netdevice=n.netdevice_idx AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in my_netdev_idxs])))
            serv_ip_dict = dict([(db_rec["name"], db_rec["ip"]) for db_rec in dc.fetchall()])
            for serv_name, serv_ip in serv_ip_dict.iteritems():
                self.log(" - Sending %s to %s (%s) ..." % (send_str, serv_name, serv_ip))
                self.__net_server.add_object(net_tools.udp_con_object(self._new_udp_con, target_host=serv_ip, target_port=SERVER_PORT, bind_retries=1, rebind_wait_time=1, connect_state_call=self._udp_connect, add_data=send_str))
        dc.release()
    def _new_udp_con(self, sock):
        return simple_con("udp", sock.get_target_host(), sock.get_target_port(), sock.get_add_data(), self.get_thread_queue())
    def _udp_connect(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("send_error", (args["host"], args["port"], args["type"], "connect error")))
    def _send_error(self, (s_host, s_port, mode, what)):
        self.log("send_error (%s, %s %d): %s" % (s_host, mode, s_port, what), logging_tools.LOG_LEVEL_ERROR)
    def _send_ok(self, (s_host, s_port, mode, what)):
        self.log("send_ok (%s, %s %d): %s" % (s_host, mode, s_port, what))
        
class monitor_thread(threading_tools.thread_obj):
    def __init__(self, db_con, glob_config, loc_config, logger):
        self.__db_con = db_con
        self.__logger = logger
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "monitor", queue_size=50)
        self.__esd, self.__nvn = ("/tmp/.machvect_es", "cluster_div")
        self.__ext_keys = {}
        self.register_func("update", self._update)
        self.__server_cap_dict = {"usv_server" : usv_server_stuff(self.__logger, self.__glob_config, self.__loc_config),
                                  "quota"      : quota_stuff(self.__logger, self.__db_con, self.__glob_config, self.__loc_config)}
        self._init_cap_list()
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _init_cap_list(self):
        # init value
        self.__init_ext_ok = False
        self.__cap_list = []
        dc =  self.__db_con.get_connection(SQL_ACCESS)
        for what in self.__server_cap_dict.keys():
            sql_info = config_tools.server_check(dc=dc, server_type=what)
            if sql_info.num_servers:
                self.__cap_list.append(what)
        dc.release()
        self.__any_capabilities = len(self.__cap_list)
        if self.__any_capabilities:
            self.log("Found %s: %s" % (logging_tools.get_plural("capability", len(self.__cap_list)),
                                       ", ".join(self.__cap_list)))
        else:
            self.log("Found no capabilities")
        self.__mv_caps, self.__other_caps = ([], [])
        if self.__any_capabilities:
            init_list, act_list = (self._init_machvector(),
                                   self._get_machvector())
            self.__act_init_list = init_list
            self.__init_ext_ok = self._write_ext(init_list, True)
            if self.__init_ext_ok:
                self._write_ext(act_list)
        self.__last_update = None
    def _init_machvector(self):
        init_list = []
        self.__mv_caps, self.__other_caps = ([], [])
        for cap in self.__cap_list:
            if self.__server_cap_dict[cap].get_creates_machvector():
                self.__mv_caps.append(cap)
                init_list.extend(self.__server_cap_dict[cap].init_machvector())
            else:
                self.__other_caps.append(cap)
        return init_list
    def _get_machvector(self):
        act_list = []
        for cap in self.__cap_list:
            if self.__server_cap_dict[cap].get_creates_machvector():
                act_list.extend(self.__server_cap_dict[cap].get_machvector())
        return act_list
    def _write_ext(self, out_list, init=False):
        if init:
            out_file = "%s/%s.mvd" % (self.__esd, self.__nvn)
        else:
            out_file = "%s/%s.mvv" % (self.__esd, self.__nvn)
        ret_state = False
        if os.path.isdir(self.__esd):
            try:
                file(out_file, "w").write("\n".join(out_list + [""]))
            except:
                self.log("cannot create file %s: %s" % (out_file, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                ret_state = True
        else:
            self.log("directory %s not found" % (self.__esd), logging_tools.LOG_LEVEL_WARN)
        return ret_state
    def _update(self):
        min_wakeup_time = 10.
        act_time = time.time()
        if not self.__last_update or abs(act_time - self.__last_update) > min_wakeup_time:
            self.__last_update = act_time
            if self.__any_capabilities and self.__init_ext_ok:
                act_init_list = self._init_machvector()
                if act_init_list != self.__act_init_list:
                    self.__act_init_list = act_init_list
                    self.__init_ext_ok = self._write_ext(act_init_list, True)
                if self.__init_ext_ok:
                    act_list = self._get_machvector()
                    self._write_ext(act_list)
            for cap in self.__other_caps:
                if self.__server_cap_dict[cap].check_for_wakeup(act_time):
                    self.__server_cap_dict[cap].wakeup()
        else:
            self.log("Too many update requests...", logging_tools.LOG_LEVEL_WARN)
        
# --------- connection objects ------------------------------------

class new_tcp_con(net_tools.buffer_object):
    # connection object for cluster-server
    def __init__(self, sock, src, pm_queue, logger):
        self.__loc_host, self.__loc_port = sock.get_sock_name()
        self.__src_host, self.__src_port = src
        self.__pm_queue = pm_queue
        self.__logger = logger
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
        self.__command = "<not set>"
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(level, what)
    def set_command(self, com):
        self.__command = com
    def get_loc_host(self):
        return self.__loc_host
    def get_loc_port(self):
        return self.__loc_port
    def get_src_host(self):
        return self.__src_host
    def get_src_port(self):
        return self.__src_port
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            self.__decoded = what
            self.__pm_queue.put(("in_tcp_bytes", self))
    def add_to_out_buffer(self, what):
        self.lock()
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection")
        self.unlock()
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__pm_queue = None
            d_time = abs(time.time() - self.__init_time)
            self.log("command %s from %s (port %d) took %s" % (self.__command,
                                                               self.__src_host,
                                                               self.__src_port,
                                                               logging_tools.get_diff_time_str(d_time)))
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
            #self.socket.ready_to_send()
    def get_decoded_in_str(self):
        return self.__decoded
    def report_problem(self, flag, what):
        self.close()

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

# --------- connection objects ------------------------------------

class server_process(threading_tools.process_pool):
    def __init__(self, db_con):
        self.__log_cache, self.__log_template = ([], None)
        self.__db_con = db_con
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self._log_config()
        self._check_uuid()
        #self.__is_server = not self.__server_com
        self._load_modules()#self.__loc_config, self.log, self.__is_server)
        self._init_network_sockets()
        self.register_timer(self._update, 30, instant=True)
##        self.__ns = None
##        if not self.__server_com:
##            self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=False)
##            self.__tcp_bo = net_tools.tcp_bind(self._new_tcp_con, port=self.__glob_config["COM_PORT"], bind_retries=self.__loc_config["N_RETRY"], bind_state_call=self._bind_state_call, timeout=120)
##            self.__udp_bo = net_tools.udp_bind(self._new_udp_con, port=self.__glob_config["COM_PORT"], bind_retries=self.__loc_config["N_RETRY"], bind_state_call=self._bind_state_call, timeout=120)
##            self.__ns.add_object(self.__tcp_bo)
##            self.__ns.add_object(self.__udp_bo)
##            self.__ss_thread_queue = self.add_thread(socket_server_thread(self.__db_con, self.__glob_config, self.__loc_config, self.__ns, self.__logger), start_thread=True).get_thread_queue()
##            self.__bg_thread_queue = self.add_thread(background_thread(self.__db_con, self.__ss_thread_queue, self.__glob_config, self.__loc_config, self.__logger), start_thread=True).get_thread_queue()
##            self.__mon_thread_queue = self.add_thread(monitor_thread(self.__db_con, self.__glob_config, self.__loc_config, self.__logger), start_thread=True).get_thread_queue()
##        else:
##            self.__target_host, self.__target_port = (None, None)
##            self.__client_ret_str = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def set_target(self, t_host, t_port):
        self.__target_host, self.__target_port = (t_host, t_port)
        self.__ns = net_tools.network_send(timeout=10, log_hook=self.log, verbose=False)
        self.__ns.add_object(net_tools.tcp_con_object(self._new_client_tcp_con, connect_state_call=self._client_connect_state_call, connect_timeout_call=self._client_connect_timeout, target_host=self.__target_host, target_port=self.__target_port, timeout=10, bind_retries=1, rebind_wait_time=2))
        self.log("Contacting cluster-server on %s (port %d) for command: %s" % (self.__target_host,
                                                                                self.__target_port,
                                                                                self.__server_com.get_command()))
        self.__first_step = True
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            if not self.__is_server and self.__client_ret_str is None:
                self.set_error("interrupted")
            self["exit_requested"] = True
            if self.__ns:
                self.__ns.set_timeout(0.1)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        self.log("re-insert config")
        # FIXME, AL, 20120330, not needed ?
##        dc = self.__db_con.get_connection(SQL_ACCESS)
##        configfile.write_config(dc, "server", self.__glob_config)
##        dc.release()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if global_config["DEBUG"] or True:#AEMON"]: and not self.__server_com:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("cluster-server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/cluster-server start"
            msi_block.stop_command = "/etc/init.d/cluster-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _check_uuid(self):
        self.log("uuid checking")
        dc = self.__db_con.get_connection(SQL_ACCESS)
        self.log(" - cluster_device_uuid is '%s'" % (uuid_tools.get_uuid().get_urn()))
        uuid_var = configfile.device_variable(dc, global_config["SERVER_IDX"], "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
        # recognize for which devices i am responsible
        dev_r = process_tools.device_recognition(dc)
        if dev_r.device_dict:
            self.log(" - i am also host for %s: %s" % (logging_tools.get_plural("virtual device", len(dev_r.device_dict.keys())),
                                                       ", ".join(dev_r.device_dict.values())))
            for dev_idx in dev_r.device_dict.keys():
                configfile.device_variable(dc, dev_idx, "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
                configfile.device_variable(dc, dev_idx, "is_virtual", description="Flag set for Virtual Machines", value=1)
        dc.release()
    def thread_loop_post(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, "cluster-server:%s" % (global_config["SERVER_SHORT_NAME"]))
        client.setsockopt(zmq.HWM, 256)
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
    def _recv_command(self, sock):
        print "*"
##    def _new_client_tcp_con(self, sock):
##        return cs_base_class.simple_tcp_obj(self, self.__server_com)
##    def _new_tcp_con(self, sock, src):
##        return new_tcp_con(sock, src, self.__ss_thread_queue, self.__logger)
##    def _new_udp_con(self, data, frm):
##        self.__ss_thread_queue.put(("in_udp_bytes", (data, frm)))
    def _client_connect_timeout(self, sock):
        self.log("connect timeout", logging_tools.LOG_LEVEL_ERROR)
        self.set_error("error connect timeout")
        self._int_error("timeout")
        sock.close()
    def _update(self):
        self.log("update")
    def loop_function(self):
        if self.__is_server:
            self.__mon_thread_queue.put("update")
            self.__ns.step()
        elif self.__target_host:
            if self.__first_step:
                self.__first_step = False
                self.__ns.step()
            if not self.__ns.exit_requested() and self.__ns.get_num_objects():
                self.__ns.step()
            else:
                self._int_error("done")
        else:
            self.log("Direct command: %s" % (self.__server_com.get_command()))
            try:
                self.__client_ret_str, coms_queued = process_request(self.__glob_config, self.__loc_config, self.__logger, self.__db_con, self.__server_com, "127.0.0.1", 0, 1, "127.0.0.1", None, None, [], None)
            except:
                exc_info = process_tools.exception_info()
                for line in exc_info.log_lines:
                    self.log(" :: %s" % (line), logging_tools.LOG_LEVEL_CRITICAL)
                self.__client_error, self.__client_ret_str = (True, "exception: %s" % (process_tools.get_except_info()))
            else:
                self.__client_error = False
            self._int_error("request_done")
    def set_result(self, in_data):
        try:
            srv_reply = server_command.server_reply(in_data)
        except ValueError:
            self.__client_error, self.__client_ret_str = (True, "Error: got no valid server_reply (got: '%s')" % (in_data))
        else:
            self.__client_error, self.__client_ret_str = (False, srv_reply)
    def set_error(self, in_data):
        self.__client_error, self.__client_ret_str = (True, in_data)
    def get_client_ret_state(self):
        return self.__client_error, self.__client_ret_str
    def _load_modules(self):
        self.log("loading modules from cluster_server")
        num_coms = 0
        for com_file_name in loc_config["COM_FILE_LIST"]:
            new_mod = __import__("%s_mod" % (com_file_name), globals(), [], [])
            loc_config["COM_DICT"]["%s_module" % (com_file_name)] = new_mod
            func_names = [name for (name, ett) in [(ett_name, getattr(new_mod, ett_name)) for ett_name in dir(new_mod)] if type(ett) == type(dummy_class) and issubclass(ett, cs_base_class.server_com)]
            for func_name in func_names:
                if func_name in loc_config["COM_LIST"]:
                    log_hook("Error, function %s already in list" % (func_name),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    loc_config["COM_LIST"].append(func_name)
                    loc_config["COM_LIST"].sort()
                    loc_config["COM_DICT"][func_name] = getattr(new_mod, func_name)()
                    act_sc = loc_config["COM_DICT"][func_name]
                    act_sc.file_name = "%s_mod.py" % (com_file_name)
                    num_coms += 1
                    if detail_log:
                        log("   com %-30s, %s%s, %s, needed option_keys(s) %s, %s" % (act_sc.get_name(),
                                                                                      logging_tools.get_plural("config", len(act_sc.get_config_list())),
                                                                                      " (%s)" % (act_sc.get_config()) if act_sc.get_config_list() else "",
                                                                                      act_sc.get_blocking_mode() and "blocking" or "not blocking",
                                                                                      act_sc.get_needed_option_keys(),
                                                                                      act_sc.get_is_restartable() and "restartable" or "not restartable"))
        log("Found %s" % (logging_tools.get_plural("command", num_coms)))

        
def scan_module_path(mod_path):
    com_file_list = []
    if not os.path.isdir(mod_path):
        print "No module_path %s found" % (mod_path)
        sys.exit(1)
    else:
        com_file_list = sorted([x[:-7] for x in os.listdir(mod_path) if x.endswith("_mod.py")])
    return com_file_list

class dummy_class(object):
    def __init__(self):
        pass

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var("%s" % (prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("PID_NAME"            , configfile.str_c_var("%s" % (prog_name))),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("CONTACT"             , configfile.bool_c_var(False, only_commandline=True, help_string="directly connect cluster-server on localhost [%(default)s]")),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    db_con = mysql_tools.dbcon_container()
    try:
        dc = db_con.get_connection("cluster_full_access")
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    sql_info = config_tools.server_check(dc=dc, server_type="server")
    global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.server_device_idx))])
    ret_state = 256
    if not global_config["SERVER_IDX"]:
        sys.stderr.write(" %s is no cluster-server, exiting..." % (long_host_name))
        sys.exit(5)
    if sql_info.num_servers > 1:
        print "Database error for host %s (nagios_config): too many entries found (%d)" % (long_host_name, sql_info.num_servers)
        dc.release()
        sys.exit(5)
    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(process_tools.create_log_source_entry(dc, global_config["SERVER_IDX"], "cluster-server", "Cluster Server")))])
    if not global_config["LOG_SOURCE_IDX"]:
        print "Too many log_source with my id present, exiting..."
        dc.release()
        sys.exit(5)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    configfile.read_config_from_db(global_config, dc, "server", [
        ("COM_PORT"              , configfile.int_c_var(SERVER_PORT)),
        ("LOG_DESTINATION"       , configfile.str_c_var("uds:/var/lib/logging-server/py_log")),
        ("LOG_NAME"              , configfile.str_c_var("cluster-server")),
        ("IMAGE_SOURCE_DIR"      , configfile.str_c_var("/usr/local/share/images")),
        ("UPDATE_SITE"           , configfile.str_c_var("http://www.initat.org/cluster/RPMs/")),
        ("RPM_TARGET_DIR"        , configfile.str_c_var("/root/RPMs")),
        ("MAILSERVER"            , configfile.str_c_var("localhost")),
        ("FROM_NAME"             , configfile.str_c_var("quotawarning")),
        ("FROM_ADDR"             , configfile.str_c_var(long_host_name)),
        ("QUOTA_ADMINS"          , configfile.str_c_var("lang-nevyjel@init.at")),
        ("LDAP_SCHEMATA_VERSION" , configfile.int_c_var(1)),
        ("MONITOR_QUOTA_USAGE"   , configfile.bool_c_var(False)),
        ("QUOTA_CHECK_TIME_SECS" , configfile.int_c_var(3600)),
        ("USER_MAIL_SEND_TIME"   , configfile.int_c_var(3600, info="time in seconds between to mails")),
        ("SERVER_SHORT_NAME"     , configfile.str_c_var(mach_name)),
    ])
    dc.release()
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "cluster-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging cluster-server on %s" % (long_host_name)
    ret_state = server_process(db_con).loop()
    sys.exit(ret_state)
    
##    try:
##        opts, args = getopt.getopt(sys.argv[1:], "dVvr:p:c:hCkD:", ["help", "force", "contact", "sql-fail"])
##    except getopt.GetoptError, bla:
##        print "Commandline error!", bla
##        sys.exit(2)
##    server_full_name = socket.getfqdn(socket.gethostname())
##    server_short_name = server_full_name.split(".")[0]
##    loc_config = configfile.configuration("local_config", {"PID_NAME"          : configfile.str_c_var("cluster-server"),
##                                                           "SERVER_IDX"        : configfile.int_c_var(0),
##                                                           "VERBOSE"           : configfile.bool_c_var(False),
##                                                           "FORCE"             : configfile.bool_c_var(False),
##                                                           "CONTACT"           : configfile.bool_c_var(False),
##                                                           "N_RETRY"           : configfile.int_c_var(5),
##                                                           "DAEMON"            : configfile.bool_c_var(True),
##                                                           "MODULE_PATH"       : configfile.str_c_var("/usr/local/sbin/cs_modules"),
##                                                           "VERSION_STRING"    : configfile.str_c_var(VERSION_STRING),
##                                                           "COM_FILE_LIST"     : configfile.array_c_var([]),
##                                                           "COM_LIST"          : configfile.array_c_var([]),
##                                                           "COM_DICT"          : configfile.dict_c_var({}),
##                                                           "LOG_STATUS"        : configfile.dict_c_var({}),
##                                                           "LOG_SOURCE_IDX"    : configfile.int_c_var(0)})
##    if os.getcwd() == "/usr/local/share/home/local/development/cluster-server":
##        loc_config["MODULE_PATH"] = "/usr/local/share/home/local/development/cluster-server/cs_modules"
##    loc_config["COM_FILE_LIST"] = scan_module_path(loc_config["MODULE_PATH"])
##    check, kill_running, sql_fail = (0, True, False)
##    g_port = SERVER_PORT
##    pid_name = "cluster-server"
##    server_com = None
##    pname = os.path.basename(sys.argv[0])
##    ov_dict = {}
##    for opt, arg in opts:
##        if opt in ("-h", "--help"):
##            print "Usage: %s [OPTIONS] {[KEY:VALUE]}" % (pname)
##            print "where OPTIONS are:"
##            print " -h,--help        this help"
##            print " -C               check if this host is a cluster-server (returns 5 on error and 0 on ok)"
##            print " -d               run in debug mode (no forking)"
##            print " -v               be verbose"
##            print " -V               show version"
##            print " -p port          connect to given port, default is %d" % (g_port)
##            print " -k               do not kill running %s" % (pname)
##            print " --force          force calling of command even if no config is found (only for direct calls)"
##            print " --contact        contact running clusterserver, default is to run the command directly"
##            print " -D [key:value,]  override predefined values"
##            print " --sql-fail       fail immediately if no SQL-server is reachable"
##            print " -c command       call command directly where command is one of:"
##            out_list = logging_tools.form_list()
##            out_list.set_header_string(0, ["Idx", "Command", "file", "public", "config(s)", "source", "Needed keys", "Used config keys"])
##            db_con = mysql_tools.dbcon_container(with_logging=socket.getfqdn() == "nagios.init.at")
##            with db_con.db_transaction() as dc:
###             try:
###                 dc = db_con.get_connection(SQL_ACCESS)
###             except:
###                 dc = None
##                out_list.set_format_string("Idx", "d", "")
##                load_modules(loc_config, None)
##                idx = 0
##                for com in loc_config["COM_LIST"]:
##                    idx += 1
##                    cdk_s = loc_config["COM_DICT"][com]
##                    is_ok, srv_origin, why_not = cdk_s.check_config(dc, loc_config)
##                    out_list.add_line((idx,
##                                       com,
##                                       cdk_s.file_name,
##                                       {True  : "yes",
##                                        False : "no"}[cdk_s.get_public_via_net()],
##                                       cdk_s.get_config(),
##                                       srv_origin,
##                                       cdk_s.get_needed_option_keys(),
##                                       cdk_s.get_used_config_keys()))
##                #if dc:
##                #    dc.release()
##            if out_list:
##                print out_list
##            else:
##                print "No modules found, strange..."
##            sys.exit(0)
##        if opt == "--sql-fail":
##            sql_fail = True
##        if opt == "-D":
##            try:
##                ov_dict = dict([(k, v) for k, v in [x.split(":", 1) for x in arg.split(",")]])
##            except:
##                print "error parsing option dict"
##                sys.exit(-1)
##        if opt == "--contact":
##            loc_config["CONTACT"] = True
##        if opt == "--force":
##            loc_config["FORCE"] = True
##        if opt == "-k":
##            kill_running = False
##        if opt == "-C":
##            check = 1
##        if opt == "-d":
##            loc_config["DAEMON"] = False
##        if opt == "-c":
##            server_com = server_command.server_command(command=arg)
##            server_com.set_option_dict(dict([(k, v) for k, v in [z for z in [x.split(":", 1) for x in args] if len(z) == 2]]))
##        if opt == "-V":
##            print "Version %s" % (loc_config["VERSION_STRING"])
##            sys.exit(0)
##        if opt == "-p":
##            g_port = int(arg)
##        if opt == "-v":
##            loc_config["VERBOSE"] = True
##        if opt == "-r":
##            try:
##                loc_config["N_RETRY"] = int(arg)
##            except:
##                print "Error parsing n_retry"
##                sys.exit(2)
##    if server_com:
##        kill_running = False
##        pid_name = "%s-direct-%s-%d" % (pid_name, "%04d%02d%02d-%02d:%02d" % tuple(time.localtime()[0:5]), os.getpid())
##    process_tools.renice()
##    if server_com:
##        loc_config["DAEMON"] = False
##    # do we have to change stdin / stdout, have we changed them ?
##    change_stds, stds_changed = (False, False)
##    if loc_config["DAEMON"]:
##        process_tools.become_daemon()
##        changed_stds = True
##    else:
##        if not server_com:
##            print "Debugging cluster-server on %s" % (loc_config["SERVER_FULL_NAME"])
##    db_con = mysql_tools.dbcon_container(with_logging=loc_config["VERBOSE"])
##    wait_iter = 0
##    while True:
##        try:
##            dc = db_con.get_connection(SQL_ACCESS)
##        except MySQLdb.OperationalError:
##            db_con.release()
##            if sql_fail:
##                sys.stderr.write(" Cannot connect to SQL-Server ")
##                sys.exit(1)
##            else:
##                if not wait_iter:
##                    if change_stds and not stds_changed:
##                        stds_changed = True
##                        process_tools.set_handles({"out" : (1, "cluster-server.out"),
##                                                   "err" : (0, "/var/lib/logging-server/py_err")})
##                    sys.stderr.write(" Cannot connect to SQL-Server, waiting...")
##                wait_iter += 1
##                logging_tools.my_syslog("cannot connect to SQL-Server, waiting for 30 seconds")
##                time.sleep(30)
##        except:
##            err_str = "unable to create a DB-cursor: %s" % (process_tools.get_except_info())
##            sys.stderr.write("%s\n" % (err_str))
##            logging_tools.my_syslog(err_str)
##            sys.exit(1)
##        else:
##            break
##    if wait_iter:
##        logging_tools.my_syslog("successfully connected to SQL-Server after %s" % (logging_tools.get_plural("retry", wait_iter)))
##    sql_info = config_tools.server_check(dc=dc, server_type="server")
##    loc_config["SERVER_IDX"] = sql_info.server_device_idx
##    if not loc_config["SERVER_IDX"] and not loc_config["FORCE"]:
##        sys.stderr.write(" %s is no cluster-server, exiting..." % (loc_config["SERVER_FULL_NAME"]))
##        sys.exit(5)
##    if change_stds and not stds_changed:
##        stds_changed = True
##        process_tools.set_handles({"out" : (1, "cluster-server.out"),
##                                   "err" : (0, "/var/lib/logging-server/py_err")})
##    if check:
##        sys.exit(0)
##    if kill_running:
##        kill_dict = process_tools.build_kill_dict(pname)
##        for key, value in kill_dict.iteritems():
##            log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (key, value)
##            try:
##                os.kill(key, 9)
##            except:
##                log_str = "%s error (%s)" % (log_str, process_tools.get_except_info())
##            else:
##                log_str = "%s ok" % (log_str)
##            logging_tools.my_syslog(log_str)
##    loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, loc_config["SERVER_IDX"], "cluster-server", "Cluster Server")
##    glob_config = configfile.read_global_config(dc, "server", {"COM_PORT"              : configfile.int_c_var(g_port),
##                                                               "LOG_DESTINATION"       : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
##                                                               "LOG_NAME"              : configfile.str_c_var("cluster-server"),
##                                                               "IMAGE_SOURCE_DIR"      : configfile.str_c_var("/usr/local/share/images"),
##                                                               "UPDATE_SITE"           : configfile.str_c_var("http://www.initat.org/cluster/RPMs/"),
##                                                               "RPM_TARGET_DIR"        : configfile.str_c_var("/root/RPMs"),
##                                                               "MAILSERVER"            : configfile.str_c_var("localhost"),
##                                                               "FROM_NAME"             : configfile.str_c_var("quotawarning"),
##                                                               "FROM_ADDR"             : configfile.str_c_var(loc_config["SERVER_FULL_NAME"]),
##                                                               "QUOTA_ADMINS"          : configfile.str_c_var("lang-nevyjel@init.at"),
##                                                               "LDAP_SCHEMATA_VERSION" : configfile.int_c_var(1),
##                                                               "MONITOR_QUOTA_USAGE"   : configfile.bool_c_var(False),
##                                                               "QUOTA_CHECK_TIME_SECS" : configfile.int_c_var(3600),
##                                                               "USER_MAIL_SEND_TIME"   : configfile.int_c_var(3600, info="time in seconds between to mails")})
##    loc_config["LOG_STATUS"] = process_tools.get_all_log_status(dc)
##    dc.release()
##    for key, value in ov_dict.iteritems():
##        if glob_config.has_key(key):
##            print "Overriding value '%s' for key '%s' to '%s'" % (glob_config[key], key, value)
##            glob_config[key] = value
##        else:
##            print "Setting value for new key '%s' to '%s'" % (key, value)
##            glob_config.add_config_dict({key : configfile.str_c_var(value)})
##    if server_com:
##        glob_config["LOG_NAME"] = "%s-direct" % (glob_config["LOG_NAME"])
##        loc_config["PID_NAME"] = "%s-direct-%s-%d" % (loc_config["PID_NAME"], "%04d%02d%02d-%02d:%02d" % tuple(time.localtime()[0:5]), os.getpid())
##    server_code(db_con, glob_config, loc_config, server_com)
##    db_con.close()
##    del db_con
##    sys.exit(0)

if __name__ == "__main__":
    main()
