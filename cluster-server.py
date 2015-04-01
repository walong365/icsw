#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012,2013 Andreas Lang-Nevyjel
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

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.conf import settings
import time
import net_tools
import threading_tools
import commands
import pwd
import logging_tools
import process_tools
import configfile
import server_command
import pprint
import datetime
import uuid_tools
import mail_tools
import config_tools
import cluster_location
import zmq
import stat
import initat.cluster_server
import bz2
from django.db.models import Q
from django.db import connection
from initat.host_monitoring import hm_classes
from initat.cluster.backbone.models import device, device_variable, log_source
from initat.cluster_server.config import global_config
from initat.core.management.commands import dumpdatafast, dumpdataslow
from optparse import OptionParser

try:
    from cluster_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SERVER_PORT = 8004

class dummy_file(file):
    ending = None
    
class backup_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        connection.close()
        self.register_func("start_backup", self._start_backup)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _start_backup(self, *args, **kwargs):
        self.log("starting backup")
        bu_dir = global_config["DATABASE_DUMP_DIR"]
        if not os.path.isdir(bu_dir):
            self.log("creating bu_dir %s" % (bu_dir))
            os.mkdir(bu_dir)
        # delete old files
        for entry in os.listdir(bu_dir):
            if entry.count(".") and entry.split(".")[-1] in ["zip", "bz2"]:
                f_name = os.path.join(bu_dir, entry)
                diff_dt = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.stat(f_name)[stat.ST_CTIME])
                if diff_dt.days > global_config["DATABASE_KEEP_DAYS"]:
                    self.log("removing backup %s" % (f_name))
                    os.unlink(f_name)
        self._fast_backup(bu_dir)
        self._normal_backup(bu_dir)
        self._exit_process()
    def _fast_backup(self, bu_dir):
        # start 'fast' django backup
        s_time = time.time()
        bu_name = datetime.datetime.now().strftime("db_bu_fast_%Y%m%d_%H:%M:%S")
        self.log("storing backup in %s" % (os.path.join(
            bu_dir,
            bu_name)))
        # set BASE_OBJECT 
        dumpdatafast.BASE_OBJECT = self
        buf_com = dumpdatafast.Command()
        opts, args = OptionParser(option_list=buf_com.option_list).parse_args([
            "-d",
            bu_dir,
            "-b",
            "--one-file",
            bu_name])
        buf_com._handle(*args, **vars(opts))
        # clear base object
        dumpdatafast.BASE_OBJECT = None
        e_time = time.time()
        self.log("fast backup finished in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
    def _normal_backup(self, bu_dir):
        # start 'normal' django backup
        s_time = time.time()
        bu_name = datetime.datetime.now().strftime("db_bu_django_%Y%m%d_%H:%M:%S")
        full_path = os.path.join(
            bu_dir,
            bu_name)
        self.log("storing backup in %s" % (full_path))
        buf_com = dumpdataslow.Command()
        buf_com.stdout = dummy_file(full_path, "wb")
        opts, args = OptionParser(option_list=buf_com.option_list).parse_args([
            "-a",
            "--format",
            "xml",
            "--traceback",
            "auth",
            "contenttypes",
            "sessions",
            "sites",
            "messages",
            "admin",
            "backbone",
        ])
        buf_com.handle(*args, **vars(opts))
        buf_com.stdout.close()
        file("%s.bz2" % (full_path), "wb").write(bz2.compress(file(full_path, "r").read()))
        os.unlink(full_path)
        e_time = time.time()
        self.log("normal backup finished in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
    def loop_post(self):
        self.__log_template.close()

class bg_stuff(object):
    class Meta:
        min_time_between_runs = 30
        creates_machvector = False
    def __init__(self, srv_process):
        # copy Meta keys
        for key in dir(bg_stuff.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(bg_stuff.Meta, key))
        #self.__name = name
        self.server_process = srv_process
        self.init_bg_stuff()
        self.__last_call = None
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.server_process.log("[bg %s] %s" % (self.Meta.name, what), level)
    def init_bg_stuff(self):
        pass
    def __call__(self, cur_time, drop_com):
        if self.__last_call and abs(self.__last_call - cur_time) < self.Meta.min_time_between_runs:
            #self.log("last call only %d seconds ago, skipping" % (abs(self.__last_call - cur_time)),
            #         logging_tools.LOG_LEVEL_WARN)
            pass
        else:
            self.__last_call = cur_time
            add_obj = self._call(cur_time, drop_com.builder)
            if add_obj is not None:
                drop_com["vector_%s" % (self.Meta.name)] = add_obj
                drop_com["vector_%s" % (self.Meta.name)].attrib["type"] = "vector"
    def _call(self, cur_time, drop_com):
        self.log("dummy __call__()")
    def send_mail(self, to_addr, subject, msg_body):
        new_mail = mail_tools.mail(subject, "%s@%s" % (global_config["FROM_NAME"], global_config["FROM_ADDR"]), to_addr, msg_body)
        new_mail.set_server(global_config["MAILSERVER"], global_config["MAILSERVER"])
        stat, log_lines = new_mail.send_mail()
        return log_lines

class dummy_stuff(bg_stuff):
    class Meta:
        name = "dummy"
    def init_bg_stuff(self):
        self.load_value = hm_classes.mvect_entry("sys.load1", info="test entry", default=0.0)
    def _call(self, cur_time, builder):
        self.load_value.update(float(file("/proc/loadavg", "r").read().split()[0]))
        self.load_value.valid_until = time.time() + 10
        my_vector = builder("values")
        my_vector.append(self.load_value.build_xml(builder))
        return my_vector

class usv_server_stuff(bg_stuff):
    class Meta:
        creates_machvector = True
        name = "usv_server"
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
    class Meta:
        name = "quota"
    def init_bg_stuff(self):
        self.Meta.min_time_between_runs = global_config["QUOTA_CHECK_TIME_SECS"]
        self.Meta.creates_machvector = global_config["MONITOR_QUOTA_USAGE"]
        # user cache
        self.__user_dict = {}
        # last mail sent to admins
        self.__admin_mail_sent = None
        # load value cache
        self.__load_values = {}
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
    def _call(self, cur_time, builder):
        dc = self.server_process.get_dc()
        sep_str = "-" * 64
        # vector to report
        my_vector = None
        self.log(sep_str)
        self.log("starting quotacheck")
        q_cmd = "repquota -aniu"
        q_stat, q_out = commands.getstatusoutput(q_cmd)
        if q_stat:
            self.log("Cannot call '%s' (stat=%d): %s" % (q_cmd, q_stat, str(q_out)),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            q_dict = {}
            act_dev = None
            for line in [c_line.strip() for c_line in q_out.split("\n") if c_line.strip()]:
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
            mtab_dict = {}
            for cur_line in file("/etc/mtab", "r").read().split("\n"):
                if cur_line.startswith("/") and len(cur_line.split()) > 3:
                    key, v0, v1, v2 = cur_line.strip().split()[:4]
                    if key not in mtab_dict:
                        mtab_dict[key] = (v0, v1, v2)
            quota_cache = []
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
                        if self.Meta.creates_machvector:
                            if u_stuff.quotas_defined():
                                missing_uids.add(uid)
                                quota_cache.append((dev, uid, u_stuff))
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
                mail_lines["admins"].extend([
                    "Servername: %s" % (global_config["SERVER_FULL_NAME"]),
                    log_line,
                    "",
                    "device info:",
                    ""])
                # device overview
                for prob_dev, pd_info in prob_devs.iteritems():
                    log_line = "%s: mounted on %s (flags %s), fstype is %s" % (
                        prob_dev,
                        pd_info[0],
                        pd_info[2],
                        pd_info[1])
                    self.log(log_line)
                    mail_lines["admins"].append(log_line)
                if not self.__admin_mail_sent or abs(self.__admin_mail_sent - time.time()) > global_config["USER_MAIL_SEND_TIME"]:
                    self.__admin_mail_sent = time.time()
                else:
                    email_users.remove("admins")
                mail_lines["admins"].extend(["", "user info:", ""])
                for uid, u_stuff in prob_users.iteritems():
                    user_info = self._get_uid_info(uid)
                    mail_lines[uid] = [
                        "This is an informal mail to notify you that",
                        "you have violated one or more quota-policies",
                        "on %s, user info: %s" % (global_config["SERVER_FULL_NAME"], user_info["info"]),
                        ""]
                    if user_info.get("email", ""):
                        if uid not in email_users:
                            # only send mail if at least USER_MAIL_SEND_TIME seconds
                            if not user_info["last_mail_sent"] or abs(user_info["last_mail_sent"] - time.time()) > global_config["USER_MAIL_SEND_TIME"]:
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
                        to_addrs = sum([q_admin.strip().split() for q_admin in global_config["QUOTA_ADMINS"].split(",")], [])
                    else:
                        to_addrs = [self._get_uid_info(email_user)["email"]]
                    for to_addr in to_addrs:
                        log_lines = self.send_mail(to_addr,
                                                   "quota warning from %s@%s" % (global_config["SERVER_FULL_NAME"],
                                                                                 process_tools.get_cluster_name()),
                                                   mail_lines[email_user])
                        for log_line in log_lines:
                            self.log(log_line)
            if self.Meta.creates_machvector:
                my_vector = builder("values")
                # 10 minutes valid
                valid_until = cur_time + self.Meta.min_time_between_runs * 2
                for dev_name, uid, u_stuff in quota_cache:
                    u_name = self._get_uid_info(uid, {}).get("login", "unknown")
                    block_dict = u_stuff.get_block_dict()
                    my_vector.append(hm_classes.mvect_entry(
                        "quota.%s.%s.soft" % (dev_name, u_name),
                        info="Soft Limit for user $3 on $2",
                        default=0,
                        value=block_dict["soft"],
                        factor=1000,
                        base=1000,
                        valid_until=valid_until,
                        unit="B").build_xml(builder))
                    my_vector.append(hm_classes.mvect_entry(
                        "quota.%s.%s.hard" % (dev_name, u_name),
                        info="Hard Limit for user $3 on $2",
                        default=0,
                        value=block_dict["hard"],
                        factor=1000,
                        base=1000,
                        valid_until=valid_until,
                        unit="B").build_xml(builder))
                    my_vector.append(hm_classes.mvect_entry(
                        "quota.%s.%s.used" % (dev_name, u_name),
                        info="Used quota for user $3 on $2",
                        default=0,
                        value=block_dict["used"],
                        factor=1000,
                        base=1000,
                        valid_until=valid_until,
                        unit="B").build_xml(builder))
        qc_etime = time.time()
        self.log("quotacheck took %s" % (logging_tools.get_diff_time_str(qc_etime - cur_time)))
        self.log(sep_str)
        dc.release()
        return my_vector

# --------- connection objects ------------------------------------

class server_process(threading_tools.process_pool):
    def __init__(self, options):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__run_command = True if global_config["COMMAND"].strip() else False
        if self.__run_command:
            # rewrite LOG_NAME and PID_NAME
            global_config["PID_NAME"] = "%s-direct-%s-%d" % (
                global_config["PID_NAME"],
                "%04d%02d%02d-%02d:%02d" % tuple(time.localtime()[0:5]),
                os.getpid())
            global_config["LOG_NAME"] = "%s-direct-%s" % (
                global_config["LOG_NAME"],
                global_config["COMMAND"])
        self.__pid_name = global_config["PID_NAME"]
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("bg_finished", self._bg_finished)
        self._log_config()
        self._check_uuid()
        self._load_modules()
        self._init_capabilities()
        self.__options = options
        self._set_next_backup_time(True)
        connection.close()
        if self.__run_command:
            self.register_timer(self._run_command, 3600, instant=True)
        else:
            self._init_network_sockets()
            self.register_timer(self._update, 2 if global_config["DEBUG"] else 30, instant=True)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _set_next_backup_time(self, first=False):
        self.__next_backup_dt = datetime.datetime.now().replace(microsecond=0)
        if global_config["BACKUP_DATABASE"] and first:
            self.log("initiate immediate backup run")
            self.__next_backup_dt = (self.__next_backup_dt + datetime.timedelta(seconds=2))
        else:
            self.__next_backup_dt = (self.__next_backup_dt + datetime.timedelta(days=0)).replace(hour=2, minute=0, second=0)
        while self.__next_backup_dt < datetime.datetime.now():
            self.__next_backup_dt += datetime.timedelta(days=1)
        self.log("setting %s backup-time to %s" % (
            "first" if first else "next",
            self.__next_backup_dt))
    def set_target(self, t_host, t_port):
        # not needed, fixme
        self.__target_host, self.__target_port = (t_host, t_port)
        self.__ns = net_tools.network_send(timeout=10, log_hook=self.log, verbose=False)
        self.__ns.add_object(net_tools.tcp_con_object(self._new_client_tcp_con, connect_state_call=self._client_connect_state_call, connect_timeout_call=self._client_connect_timeout, target_host=self.__target_host, target_port=self.__target_port, timeout=10, bind_retries=1, rebind_wait_time=2))
        self.log("Contacting cluster-server on %s (port %d) for command: %s" % (self.__target_host,
                                                                                self.__target_port,
                                                                                self.__server_com.get_command()))
        self.__first_step = True
    def _bg_finished(self, *args, **kwargs):
        func_name = args[2]
        self.log("background task for '%s' finished" % (func_name))
        initat.cluster_server.command_dict[func_name].Meta.cur_running -= 1
    def _init_capabilities(self):
        self.log("init server capabilities")
        self.__server_cap_dict = {
            "usv_server" : usv_server_stuff(self),
            "quota"      : quota_stuff(self),
            "dummy"      : dummy_stuff(self)}
        self.__cap_list = []
        for key, value in self.__server_cap_dict.iteritems():
            sql_info = config_tools.server_check(server_type=key)
            if key == "dummy":
                self.__cap_list.append(key)
            self.log("capability %s: %s" % (key, "enabled" if key in self.__cap_list else "disabled"))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        if self.__run_command:
            self.log("running command, skipping re-insert of config", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("re-insert config")
            cluster_location.write_config("server", global_config)
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=1)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.add_actual_pid(configfile.get_manager_pid(), mult=1)
            self.__msi_block.save_block()
    def process_exit(self, src_process, src_pid):
        process_tools.remove_pids(self.__pid_name, src_pid)
        process_tools.remove_pids(self.__pid_name, configfile.get_manager_pid(), mult=1)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(src_pid)
            self.__msi_block.remove_actual_pid(configfile.get_manager_pid(), mult=1)
            self.__msi_block.save_block()
        if src_process == "backup_process" and global_config["BACKUP_DATABASE"]:
            self.log("backup process finished, exiting")
            self["exit_requested"] = True
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        if not global_config["COMMAND"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info(self.__pid_name)
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
            msi_block.start_command = "/etc/init.d/cluster-server start"
            msi_block.stop_command = "/etc/init.d/cluster-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _check_uuid(self):
        self.log("uuid checking")
        self.log(" - cluster_device_uuid is '%s'" % (uuid_tools.get_uuid().get_urn()))
        my_dev = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        file_uuid = uuid_tools.get_uuid().get_urn().split(":")[2]
        if file_uuid != my_dev.uuid:
            self.log("UUID differs from DB entry (%s [file] != %s [DB]), correcting DB entry" % (
                file_uuid,
                my_dev.uuid), logging_tools.LOG_LEVEL_ERROR)
            my_dev.uuid = file_uuid
            my_dev.save()
        # uuid is also stored as device variable
        uuid_var = cluster_location.db_device_variable(global_config["SERVER_IDX"], "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
        # recognize for which devices i am responsible
        dev_r = cluster_location.device_recognition()
        if dev_r.device_dict:
            self.log(" - i am also host for %s: %s" % (logging_tools.get_plural("virtual device", len(dev_r.device_dict.keys())),
                                                       ", ".join(sorted([cur_dev.name for cur_dev in dev_r.device_dict.itervalues()]))))
            for cur_dev in dev_r.device_dict.itervalues():
                cluster_location.db_device_variable(cur_dev, "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
                cluster_location.db_device_variable(cur_dev, "is_virtual", description="Flag set for Virtual Machines", value=1)
    def loop_end(self):
        if not self.__run_command:
            if self.com_socket:
                self.log("closing socket")
                self.com_socket.close()
            if self.vector_socket:
                self.vector_socket.close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.__log_template.close()
    def _init_network_sockets(self):
        self.__connection_dict = {}
        self.__discovery_dict = {}
        if self.__run_command:
            client = None
        else:
            client = self.zmq_context.socket(zmq.ROUTER)
            client.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
            client.setsockopt(zmq.SNDHWM, 256)
            client.setsockopt(zmq.RCVHWM, 256)
            try:
                client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
            except zmq.core.error.ZMQError:
                self.log("error binding to %d: %s" % (
                    global_config["COM_PORT"],
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                self.register_poller(client, zmq.POLLIN, self._recv_command)
        self.com_socket = client
        # connection to local collserver socket
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket
        self.log("connected vector_socket to %s" % (conn_str))
    def _recv_command(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(data) == 2:
            srv_com = server_command.srv_command(source=data[1])
            self._process_command(srv_com)
            zmq_sock.send_unicode(data[0], zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
        else:
            self.log("data stream has wrong length (%d) != 2" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _client_connect_timeout(self, sock):
        self.log("connect timeout", logging_tools.LOG_LEVEL_ERROR)
        self.set_error("error connect timeout")
        self._int_error("timeout")
        sock.close()
    def _run_command(self):
        self.log("direct command %s" % (global_config["COMMAND"]))
        cur_com = server_command.srv_command(command=global_config["COMMAND"])
        cur_com["command"].attrib["via_comline"] = "1"
        for keyval in self.__options.OPTION_KEYS:
            try:
                key, value = keyval.split(":", 1)
            except:
                self.log("error parsing option_key from '%s': %s" % (
                    keyval,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_com["server_key:%s" % (key)] = value
        self._process_command(cur_com)
        self["return_value"] = int(cur_com["result"].attrib["state"])
        self["exit_requested"] = True
        # show result
        print cur_com["result"].attrib["reply"]
    def _process_command(self, srv_com):
        com_name = srv_com["command"].text
        self.log("executing command %s" % (com_name))
        srv_com["result"] = None
        srv_com["result"].attrib.update({
            "reply" : "no reply set",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)})
        if com_name in initat.cluster_server.command_dict:
            com_obj = initat.cluster_server.command_dict[com_name]
            # check config status
            do_it, srv_origin, err_str = com_obj.check_config(global_config, global_config["FORCE"])
            self.log("checking the config gave: %s (%s) %s" % (str(do_it),
                                                               srv_origin,
                                                               err_str))
            #print srv_com.pretty_print()
            if do_it:
                try:
                    found_keys = [key for key in com_obj.Meta.needed_option_keys if "server_key:%s" % (key) in srv_com]
                except:
                    srv_com["result"].attrib.update({
                        "reply" : "error parsing options_keys: %s" % (process_tools.get_except_info()),
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                        })
                else:
                    if set(found_keys) != set(com_obj.Meta.needed_option_keys):
                        srv_com["result"].attrib.update({
                            "reply" : "error option keys found (%s) != needed (%s)" % (
                                ", ".join(sorted(list(set(found_keys)))) or "none",
                                ", ".join(sorted(list(set(com_obj.Meta.needed_option_keys))))),
                            "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                            })
                    else:
                        # salt com_obj with some settings
                        option_dict = dict([(key, srv_com["*server_key:%s" % (key)]) for key in com_obj.Meta.needed_option_keys])
                        cur_inst = com_obj(srv_com, option_dict)
                        cur_inst.write_start_log()
                        cur_inst()
                        cur_inst.write_end_log()
            else:
                srv_com["result"].attrib.update({
                    "reply" : "error %s" % (err_str),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                    })
        else:
            srv_com["result"].attrib.update({
                "reply" : "command %s not known" % (com_name),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                })
        self.log("result for %s was (%d) %s" % (com_name,
                                                int(srv_com["result"].attrib["state"]),
                                                srv_com["result"].attrib["reply"]))
    def _update(self):
        cur_time = time.time()
        cur_dt = datetime.datetime.now().replace(microsecond=0)
        if not global_config["DEBUG"]:
            cur_dt = cur_dt.replace(minute=0, second=0)
        if cur_dt == self.__next_backup_dt:
            self._set_next_backup_time()
            self.log("start DB-backup")
            self.add_process(backup_process("backup_process"), start=True)
            self.send_to_process(
                "backup_process",
                "start_backup",
            )
            connection.close()
        drop_com = server_command.srv_command(command="set_vector")
        for cap_name in self.__cap_list:
            self.__server_cap_dict[cap_name](cur_time, drop_com)
        self.vector_socket.send_unicode(unicode(drop_com))
    def send_broadcast(self, bc_com):
        self.log("init broadcast command '%s'" % (bc_com))
        # FIXME
        return
        dc = self.__db_con.get_connection(SQL_ACCESS)
        dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE n.device=%d" % (global_config["SERVER_IDX"]))
        my_netdev_idxs = [db_rec["netdevice_idx"] for db_rec in dc.fetchall()]
        if my_netdev_idxs:
            dc.execute("SELECT d.name, i.ip, h.value FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg INNER JOIN device_type dt INNER JOIN " + \
                       "hopcount h INNER JOIN netdevice n INNER JOIN netip i LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND dg.device_group_idx=d.device_group AND " + \
                       "dc.new_config=c.new_config_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND c.name='server' AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND " + \
                       "h.s_netdevice=n.netdevice_idx AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (db_rec) for db_rec in my_netdev_idxs])))
            serv_ip_dict = dict([(db_rec["name"], db_rec["ip"]) for db_rec in dc.fetchall()])
            to_send_ids = []
            for srv_name, ip_addr in serv_ip_dict.iteritems():
                conn_str = "tcp://%s:%d" % (ip_addr, global_config["COM_PORT"])
                if conn_str not in self.__connection_dict:
                    # discovery
                    discovery_id = "%s_%s_%d" % (process_tools.get_machine_name(),
                                                 ip_addr,
                                                 global_config["COM_PORT"])
                    if discovery_id not in self.__discovery_dict:
                        self.log("init discovery socket for %s (id is %s)" % (conn_str,
                                                                              discovery_id))
                        new_sock = self.zmq_context.socket(zmq.DEALER)
                        new_sock.setsockopt(zmq.IDENTITY, discovery_id)
                        new_sock.setsockopt(zmq.LINGER, 0)
                        self.__discovery_dict[discovery_id] = new_sock
                        new_sock.connect(conn_str)
                        self.register_poller(new_sock, zmq.POLLIN, self._recv_discovery)
                        discovery_cmd = server_command.srv_command(command="get_0mq_id")
                        discovery_cmd["discovery_id"] = discovery_id
                        discovery_cmd["conn_str"] = conn_str
                        discovery_cmd["broadcast_command"] = bc_com
                        new_sock.send_unicode(unicode(discovery_cmd))
                        # set connection_dict entry to None
                        self.__connection_dict[conn_str] = None
                    else:
                        self.log("discovery already in progress for %s" % (conn_str),
                                 logging_tools.LOG_LEVEL_WARN)
                elif self.__connection_dict[conn_str] is None:
                    self.log("0mq discovery still in progress for %s" % (conn_str))
                else:
                    self.log("send to %s (%s)" % (conn_str,
                                                  self.__connection_dict[conn_str]))
                    to_send_ids.append(self.__connection_dict[conn_str])
            if to_send_ids:
                my_uuid = uuid_tools.get_uuid().get_urn()
                self.log("sending to %s: %s" % (logging_tools.get_plural("target", len(to_send_ids)),
                                                ", ".join(to_send_ids)))
                srv_com = server_command.srv_command(command=bc_com)
                srv_com["servers_visited"] = None
                srv_com["command"].attrib["broadcast"] = "1"
                srv_com["src_uuid"] = my_uuid
                srv_com["servers_visited"].append(srv_com.builder("server", my_uuid))
                for send_id in to_send_ids:
                    if send_id == my_uuid:
                        self._process_command(srv_com)
                    else:
                        # FIXME, send_broadcast not fully implemented, need 2nd server to test, AL 20120401
                        self.com_socket.send_unicode(send_id, zmq.SNDMORE)
                        self.com_socket.send_unicode(unicode(srv_com))
                #pprint.pprint(serv_ip_dict)
                #print unicode(srv_com)
        else:
            self.log("no local netdevices found", logging_tools.LOG_LEVEL_ERROR)
        dc.release()
    def _recv_discovery(self, sock):
        result = server_command.srv_command(source=sock.recv_unicode())
        discovery_id = result["discovery_id"].text
        t_0mq_id = result["zmq_id"].text
        conn_str = result["conn_str"].text
        bc_com = result["broadcast_command"].text
        self.log("got 0MQ_id '%s' for discovery_id '%s' (connection string %s, bc_command %s)" % (
            t_0mq_id,
            discovery_id,
            conn_str,
            bc_com))
        self.__connection_dict[conn_str] = t_0mq_id
        self.log("closing discovery socket for %s" % (conn_str))
        self.unregister_poller(self.__discovery_dict[discovery_id], zmq.POLLIN)
        self.__discovery_dict[discovery_id].close()
        del self.__discovery_dict[discovery_id]
        try:
            if self.__connection_dict[conn_str] != uuid_tools.get_uuid().get_urn():
                self.com_socket.connect(conn_str)
            else:
                self.log("no connection to self", logging_tools.LOG_LEVEL_WARN)
        except:
            self.log("error connecting to %s: %s" % (conn_str,
                                                     process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("connected to %s" % (conn_str))
        self.send_broadcast(bc_com)
    def get_client_ret_state(self):
        return self.__client_error, self.__client_ret_str
    def _load_modules(self):
        self.log("init modules from cluster_server")
        if initat.cluster_server.error_log:
            self.log("%s while loading:" % (logging_tools.get_plural("error", len(initat.cluster_server.error_log))),
                     logging_tools.LOG_LEVEL_ERROR)
            for line_num, err_line in enumerate(initat.cluster_server.error_log):
                self.log("%2d : %s" % (line_num + 1,
                                       err_line),
                         logging_tools.LOG_LEVEL_ERROR)
        del_names = []
        for com_name in initat.cluster_server.command_names:
            act_sc = initat.cluster_server.command_dict[com_name]
            if not act_sc.Meta.disabled:
                if hasattr(act_sc, "_call"):
                    act_sc.link(self)
                    self.log(
                        "   com %-30s, %s%s, %s, %s, %s, %s" % (
                            act_sc.name,
                            logging_tools.get_plural("config", len(act_sc.Meta.needed_configs)),
                            " (%s)" % (
                                ", ".join(act_sc.Meta.needed_configs)) if act_sc.Meta.needed_configs else "",
                            "blocking" if act_sc.Meta.blocking else "not blocking",
                            "%s: %s" % (
                                logging_tools.get_plural("option key", len(act_sc.Meta.needed_option_keys)),
                                ", ".join(act_sc.Meta.needed_option_keys)) if act_sc.Meta.needed_option_keys else "no option keys",
                            "%s: %s" % (
                                logging_tools.get_plural("config key", len(act_sc.Meta.needed_config_keys)),
                                ", ".join(act_sc.Meta.needed_config_keys)) if act_sc.Meta.needed_config_keys else "no config keys",
                            "background" if act_sc.Meta.background else "foreground",
                        )
                    )
                else:
                    self.log("command %s has no _call function" % (com_name), logging_tools.LOG_LEVEL_ERROR)
                    del_names.append(com_name)
            else:
                self.log("command %s is disabled" % (com_name))
        for del_name in del_names:
            initat.cluster_server.command_names.remove(del_name)
            del initat.cluster_server.command_dict[del_name]
        self.log("Found %s" % (logging_tools.get_plural("command", len(initat.cluster_server.command_names))))

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("DATABASE_DEBUG"      , configfile.bool_c_var(False, help_string="enable database debug mode [%(default)s]", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var("%s" % (prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("CONTACT"             , configfile.bool_c_var(False, only_commandline=True, help_string="directly connect cluster-server on localhost [%(default)s]")),
        ("COMMAND"             , configfile.str_c_var("", short_options="c", choices=[""] + initat.cluster_server.command_names, only_commandline=True, help_string="command to execute [%(default)s]")),
        ("BACKUP_DATABASE"     , configfile.bool_c_var(False, only_commandline=True, help_string="start backup of database immediately [%(default)s], only works in DEBUG mode")),
        ("OPTION_KEYS"         , configfile.array_c_var([], short_options="D", only_commandline=True, nargs="*", help_string="optional key-value pairs (command dependent)")),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (prog_name,
                                           VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="server")
    if not sql_info.effective_device:
        print "not a server"
        sys.exit(5)
    ret_state = 256
    if sql_info.device:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(0, database=False))])
    if not global_config["SERVER_IDX"] and not global_config["FORCE"]:
        sys.stderr.write(" %s is no cluster-server, exiting..." % (long_host_name))
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("cluster-server", "Cluster Server", device=sql_info.effective_device).pk))])
    if not global_config["LOG_SOURCE_IDX"]:
        print "Too many log_source with my id present, exiting..."
        sys.exit(5)
    if global_config["KILL_RUNNING"] and not global_config["COMMAND"]:
        log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    cluster_location.read_config_from_db(global_config, "server", [
        ("COM_PORT"             , configfile.int_c_var(SERVER_PORT)),
        ("IMAGE_SOURCE_DIR"     , configfile.str_c_var("/usr/local/share/cluster/images")),
        #("UPDATE_SITE"          , configfile.str_c_var("http://www.initat.org/cluster/RPMs/")),
        ("MAILSERVER"           , configfile.str_c_var("localhost")),
        ("FROM_NAME"            , configfile.str_c_var("quotawarning")),
        ("FROM_ADDR"            , configfile.str_c_var(long_host_name)),
        ("VERSION"              , configfile.str_c_var(VERSION_STRING, database=False)),
        ("QUOTA_ADMINS"         , configfile.str_c_var("cluster@init.at")),
        ("LDAP_SCHEMATA_VERSION", configfile.int_c_var(1)),
        ("MONITOR_QUOTA_USAGE"  , configfile.bool_c_var(False)),
        ("QUOTA_CHECK_TIME_SECS", configfile.int_c_var(3600)),
        ("USER_MAIL_SEND_TIME"  , configfile.int_c_var(3600, info="time in seconds between to mails")),
        ("SERVER_FULL_NAME"     , configfile.str_c_var(long_host_name, database=False)),
        ("SERVER_SHORT_NAME"    , configfile.str_c_var(mach_name, database=False)),
        ("DATABASE_DUMP_DIR"    , configfile.str_c_var("/opt/cluster/share/db_backup")),
        ("DATABASE_KEEP_DAYS"   , configfile.int_c_var(30)),
    ])
    settings.DATABASE_DEBUG = global_config["DATABASE_DEBUG"]
    if not global_config["DEBUG"] and not global_config["COMMAND"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "cluster-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        if global_config["DEBUG"]:
            print "Debugging cluster-server on %s" % (long_host_name)
    ret_state = server_process(options).loop()
    if global_config["DATABASE_DEBUG"]:
        from initat.cluster.backbone.middleware import show_database_calls
        show_database_calls()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
