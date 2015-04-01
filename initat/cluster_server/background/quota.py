# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel
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
""" cluster-server, quota handling """

from django.db.models import Q
from initat.cluster.backbone.models import user
from initat.cluster_server.background.base import bg_stuff
from initat.cluster_server.config import global_config
from initat.host_monitoring import hm_classes
import commands
import logging_tools
import os
import process_tools
import pwd
import time

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
        return "quota info, uid %d, flags %s, block_info: %s, file_info: %s" % (
            self.__uid,
            self.__quota_flags,
            self.get_info_str(self.get_block_dict()),
            self.get_info_str(self.get_file_dict()),
        )
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
        self.__track_all_quotas = global_config["TRACK_ALL_QUOTAS"]
        # user cache
        self.__user_dict = {}
        # last mail sent to admins
        self.__admin_mail_sent = None
        # load value cache
        self.__load_values = {}
    def _resolve_uids(self, uid_list):
        if uid_list:
            for db_rec in user.objects.filter(Q(uid__in=uid_list)):
                if self.__user_dict.has_key(db_rec.uid):
                    # check for new settings
                    for key, value in [("source"    , "SQL"),
                                       ("uid"       , db_rec.uid),
                                       ("login"     , db_rec.login),
                                       ("email"     , db_rec.email),
                                       ("firstname" , db_rec.first_name),
                                       ("lastname"  , db_rec.last_name)]:
                        self.__user_dict[db_rec.uid][key] = value
                else:
                    # new record
                    self.__user_dict[db_rec.uid] = {
                        "source"    : "SQL",
                        "uid"       : db_rec.uid,
                        "login"     : db_rec.login,
                        "email"     : db_rec.email,
                        "firstname" : db_rec.first_name,
                        "lastname"  : db_rec.last_name}
                act_dict = self.__user_dict[db_rec.uid]
                act_dict["info"] = u"uid {:d}, login {} (from SQL), ({} {}, {})".format(
                    act_dict["uid"],
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
        for _uid, u_stuff in self.__user_dict.iteritems():
            u_stuff.setdefault("last_mail_sent", None)
    def _get_uid_info(self, uid, default=None):
        return self.__user_dict.get(uid, None)
    def init_machvector(self):
        self.wakeup()
        ret_list = []
        for dev_name, uid, _u_stuff in self.__quota_cache:
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
        # dc = self.server_process.get_dc()
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
                    _osres = os.statvfs(dev)
                except:
                    self.log(
                        "cannot do an statvfs() on %s: %s" % (
                            dev,
                            process_tools.get_except_info()),
                        logging_tools.LOG_LEVEL_ERROR)
                else:
                    # f_frsize = osres[statvfs.F_FRSIZE]
                    f_frsize = 1024
                    for uid, u_stuff in u_dict.iteritems():
                        if self.Meta.creates_machvector:
                            if u_stuff.quotas_defined() or self.__track_all_quotas:
                                missing_uids.add(uid)
                                quota_cache.append((dev, uid, u_stuff))
                        if not u_stuff.everything_ok():
                            prob_users.setdefault(uid, {})[dev] = u_stuff.get_prob_str(f_frsize)
                            prob_devs.setdefault(dev, mtab_dict.get(dev, ("unknown mountpoint",
                                                                          "unknown fstype",
                                                                          "unknown flags")))
            self._resolve_uids(list(set(prob_users.keys() + list(missing_uids))))
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
        return my_vector

