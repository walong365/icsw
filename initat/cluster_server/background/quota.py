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
from initat.cluster.backbone.models import user, group
from initat.cluster_server.background.base import bg_stuff
from initat.cluster_server.config import global_config
from initat.host_monitoring import hm_classes
import commands
import grp
import logging_tools
import pprint  # @UnusedImport
import process_tools
import psutil
import pwd
import time


class quota_line(object):
    def __init__(self, q_type, line_p):
        self.__quota_type = q_type
        self.__object_id = int(line_p.pop(0)[1:])
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
        return {
            "used": self.__blocks_used,
            "soft": self.__blocks_soft,
            "hard": self.__blocks_hard,
            "grace": self.__blocks_grace
        }

    def get_file_dict(self):
        return {
            "used": self.__files_used,
            "soft": self.__files_soft,
            "hard": self.__files_hard,
            "grace": self.__files_grace
        }

    def get_info_str(self, in_dict):
        return "%d / %d / %d%s" % (
            in_dict["used"],
            in_dict["soft"],
            in_dict["hard"],
            in_dict["grace"] and " / %s" % (in_dict["grace"]) or ""
        )

    @property
    def quotas_defined(self):
        return self.__blocks_soft or self.__blocks_hard

    @property
    def object_id(self):
        return self.__object_id

    def __repr__(self):
        return "quota info for {}, id {:d}, flags {}, block_info: {}, file_info: {}".format(
            self.__quota_type,
            self.__object_id,
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
            p_f.append(
                "soft quota ({} > {})".format(
                    logging_tools.get_size_str(in_dict["used"] * block_s, False, 1000),
                    logging_tools.get_size_str(in_dict["soft"] * block_s, False, 1000)
                )
            )
        if in_dict["hard"] and in_dict["used"] >= in_dict["hard"]:
            p_f.append(
                "hard quota ({} > {})".format(
                    logging_tools.get_size_str(in_dict["used"] * block_s, False, 1000),
                    logging_tools.get_size_str(in_dict["hard"] * block_s, False, 1000)
                )
            )
        return "{} for {}s".format(" and ".join(p_f), name)

    def get_prob_str(self, block_s):
        p_f = []
        if not self.check_for_blocks():
            p_f.append(self.create_prob_str("block", self.get_block_dict(), block_s))
        if not self.check_for_files():
            p_f.append(self.create_prob_str("file", self.get_file_dict(), 1))
        return "; ".join(p_f) or "nothing"


class quota_stuff(bg_stuff):
    class Meta:
        name = "quota"

    def init_bg_stuff(self):
        self.Meta.min_time_between_runs = global_config["QUOTA_CHECK_TIME_SECS"]
        self.Meta.creates_machvector = global_config["MONITOR_QUOTA_USAGE"]
        self.__track_all_quotas = global_config["TRACK_ALL_QUOTAS"]
        # user/group cache
        self.__user_dict = {}
        self.__group_dict = {}
        # last mail sent to admins
        self.__admin_mail_sent = None
        # load value cache
        self.__load_values = {}

    def _resolve_uids(self, uid_list):
        if uid_list:
            for db_rec in user.objects.filter(Q(uid__in=uid_list)):  # @UndefinedVariable
                if db_rec.uid in self.__user_dict:
                    # check for new settings
                    for key, value in [
                        ("source", "SQL"),
                        ("uid", db_rec.uid),
                        ("login", db_rec.login),
                        ("email", db_rec.email),
                        ("firstname", db_rec.first_name),
                        ("lastname", db_rec.last_name)
                    ]:
                        self.__user_dict[db_rec.uid][key] = value
                else:
                    # new record
                    self.__user_dict[db_rec.uid] = {
                        "source": "SQL",
                        "uid": db_rec.uid,
                        "login": db_rec.login,
                        "email": db_rec.email,
                        "firstname": db_rec.first_name,
                        "lastname": db_rec.last_name
                    }
                act_dict = self.__user_dict[db_rec.uid]
                act_dict["info"] = u"uid {:d}, login {} (from SQL), ({} {}, {})".format(
                    act_dict["uid"],
                    act_dict["login"],
                    act_dict["firstname"] or "<first_name not set>",
                    act_dict["lastname"] or "<last_name not set>",
                    act_dict["email"] or "<email not set>"
                )
        missing_uids = [key for key in uid_list if key not in self.__user_dict]
        for missing_uid in missing_uids:
            try:
                pw_stuff = pwd.getpwuid(missing_uid)
            except:
                self.log("Cannot get information for uid %d" % (missing_uid),
                         logging_tools.LOG_LEVEL_ERROR)
                self.__user_dict[missing_uid] = {
                    "info": "user not found in SQL or pwd"
                }
            else:
                self.__user_dict[missing_uid] = {
                    "source": "pwd",
                    "login": pw_stuff[0],
                    "info": "uid {:d}, login {} (from pwd)".format(missing_uid, pw_stuff[0])
                }
        # add missing keys
        for _uid, u_stuff in self.__user_dict.iteritems():
            u_stuff.setdefault("last_mail_sent", None)

    def _resolve_gids(self, gid_list):
        if gid_list:
            for db_rec in group.objects.filter(Q(gid__in=gid_list)):
                if db_rec.gid in self.__group_dict:
                    # check for new settings
                    for key, value in [
                        ("source", "SQL"),
                        ("gid", db_rec.gid),
                        ("groupname", db_rec.groupname),
                        ("email", db_rec.email),
                        ("firstname", db_rec.first_name),
                        ("lastname", db_rec.last_name)
                    ]:
                        self.__group_dict[db_rec.gid][key] = value
                else:
                    # new record
                    self.__group_dict[db_rec.gid] = {
                        "source": "SQL",
                        "uid": db_rec.gid,
                        "groupname": db_rec.groupname,
                        "email": db_rec.email,
                        "firstname": db_rec.first_name,
                        "lastname": db_rec.last_name
                    }
                act_dict = self.__group_dict[db_rec.gid]
                act_dict["info"] = u"gid {:d}, groupname {} (from SQL), ({} {}, {})".format(
                    act_dict["uid"],
                    act_dict["groupname"],
                    act_dict["firstname"] or "<first_name not set>",
                    act_dict["lastname"] or "<last_name not set>",
                    act_dict["email"] or "<email not set>"
                )
        missing_gids = [key for key in gid_list if key not in self.__group_dict]
        for missing_gid in missing_gids:
            try:
                grp_stuff = grp.getgrgid(missing_gid)
            except:
                self.log("Cannot get information for gid {:d}".format(missing_gid),
                         logging_tools.LOG_LEVEL_ERROR)
                self.__group_dict[missing_gid] = {
                    "info": "groiup not found in SQL or grp"
                }
            else:
                self.__group_dict[missing_gid] = {
                    "source": "grp",
                    "groupname": grp_stuff[0],
                    "info": "gid {:d}, groupname {} (from grp)".format(missing_gid, grp_stuff[0])
                }
        # add missing keys
        for _gid, g_stuff in self.__group_dict.iteritems():
            g_stuff.setdefault("last_mail_sent", None)

    def _get_uid_info(self, uid, default=None):
        return self.__user_dict.get(uid, None)

    def _get_gid_info(self, gid, default=None):
        return self.__group_dict.get(gid, None)

    # def init_machvector(self):
    #    self.wakeup()
    #    ret_list = []
    #    for dev_name, uid, _u_stuff in self.__quota_cache:
    #        u_name = self._get_uid_info(uid, {}).get("login", "unknown")
    #        ret_list.extend(
    #            [
    #                "quota.%s.%s.soft:0:Soft Limit for user $3 on $2:B:1000:1000" % (dev_name, u_name),
    #                "quota.%s.%s.hard:0:Hard Limit for user $3 on $2:B:1000:1000" % (dev_name, u_name),
    #                "quota.%s.%s.used:0:Used quota for user $3 on $2:B:1000:1000" % (dev_name, u_name)
    #            ]
    #        )
    #    return ret_list

    # def get_machvector(self):
    #    ret_list = []
    #    for dev_name, uid, u_stuff in self.__quota_cache:
    #        u_name = self._get_uid_info(uid, {}).get("login", "unknown")
    #        block_dict = u_stuff.get_block_dict()
    #        ret_list.extend(
    #            [
    #                "quota.%s.%s.soft:i:%d" % (dev_name, u_name, block_dict["soft"]),
    #                "quota.%s.%s.hard:i:%d" % (dev_name, u_name, block_dict["hard"]),
    #                "quota.%s.%s.used:i:%d" % (dev_name, u_name, block_dict["used"])
    #            ]
    #        )
    #    return ret_list

    def _call(self, cur_time, builder):
        sep_str = "-" * 64
        # vector to report
        my_vector = None
        _quota_bin = process_tools.find_file("repquota")
        if _quota_bin is None:
            self.log("No repquota binary found", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log(sep_str)
            self.log("starting quotacheck")
            q_cmd = "{} -aniug".format(_quota_bin)
            q_stat, q_out = commands.getstatusoutput(q_cmd)
            if q_stat:
                self.log(
                    "Cannot call '{}' (stat={:d}): {}".format(q_cmd, q_stat, str(q_out)),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                q_dict = self._scan_repquota_output(q_out)
                prob_devs, prob_objs, quota_cache = self._check_for_violations(q_dict)
                if prob_devs:
                    self._send_quota_mails(prob_devs, prob_objs)
                if self.Meta.creates_machvector:
                    my_vector = self._create_machvector(builder, cur_time, quota_cache)
            qc_etime = time.time()
            self.log("quotacheck took {}".format(logging_tools.get_diff_time_str(qc_etime - cur_time)))
            self.log(sep_str)
        return my_vector

    def _scan_repquota_output(self, q_out):
        q_dict = {}
        act_dev, q_mode = (None, None)
        for line in [c_line.strip() for c_line in q_out.split("\n") if c_line.strip()]:
            if line.startswith("***"):
                act_dev = line.split()[-1]
                q_mode = line.split()[3]
            elif line.startswith("#"):
                line_p = line.split()
                try:
                    q_line = quota_line(q_mode, line_p)
                except:
                    self.log(
                        u"cannot parse quota_line '{}': {}".format(
                            line,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    if act_dev and q_mode:
                        q_dict.setdefault(act_dev, {}).setdefault(q_mode, {})[q_line.object_id] = q_line
                    else:
                        self.log(
                            "No device known for line '{}'" % (q_line),
                            logging_tools.LOG_LEVEL_WARN
                        )
        return q_dict

    def _check_for_violations(self, q_dict):
        prob_objs, prob_devs = ({"user": {}, "group": {}}, set())
        quota_cache = []
        missing_ids = {"user": set(), "group": set()}
        for dev, obj_dict in q_dict.iteritems():
            # try:
            #    _osres = os.statvfs(dev)
            # except:
            #    self.log(
            #        "cannot do an statvfs() on {}: {}" % (
            #            dev,
            #            process_tools.get_except_info(),
            #        ),
            #        logging_tools.LOG_LEVEL_ERROR
            #    )
            # else:
            #    f_frsize = osres[statvfs.F_FRSIZE]
            if True:
                # always use a fixed block size of 1024 bytes
                f_frsize = 1024
                for obj_name, ug_dict in obj_dict.iteritems():
                    missing_ids.setdefault(obj_name, set())
                    for num_id, stuff in ug_dict.iteritems():
                        if self.Meta.creates_machvector:
                            if stuff.quotas_defined or self.__track_all_quotas:
                                missing_ids[obj_name].add(num_id)
                                quota_cache.append(
                                    (dev, obj_name, num_id, stuff)
                                )
                        if not stuff.everything_ok() or True:
                            prob_objs[obj_name].setdefault(
                                num_id,
                                {}
                            )[dev] = stuff.get_prob_str(f_frsize)
                            prob_devs.add(dev)
        self._resolve_uids(list(set(prob_objs["user"].keys() + list(missing_ids["user"]))))
        self._resolve_gids(list(set(prob_objs["group"].keys() + list(missing_ids["group"]))))
        return prob_devs, prob_objs, quota_cache

    def _send_quota_mails(self, prob_devs, prob_objs):
        _admin_key = ("admin", "admins")
        email_targets = [_admin_key]
        mail_lines = {_key: [] for _key in email_targets}
        log_line = "{} / {} violated the quota policies on {}".format(
            logging_tools.get_plural("user", len(prob_objs["user"].keys())),
            logging_tools.get_plural("group", len(prob_objs["group"].keys())),
            logging_tools.get_plural("device", len(prob_devs)),
        )
        self.log(log_line)
        mail_lines[_admin_key].extend([
            "Servername: {}".format(global_config["SERVER_FULL_NAME"]),
            log_line,
            "",
            "device info:",
            ""])
        # device overview
        dev_dict = {_part.device: _part for _part in psutil.disk_partitions()}
        for prob_dev in sorted(list(prob_devs)):
            if prob_dev in dev_dict:
                _info = dev_dict[prob_dev]
                log_line = "{}: mounted on {} (options {}), fstype is {}".format(
                    prob_dev,
                    _info.mountpoint,
                    _info.opts,
                    _info.fstype,
                )
            else:
                log_line = "{}: cannot find mount info".format(prob_dev)
            self.log(log_line)
            mail_lines[_admin_key].append(log_line)
        if not self.__admin_mail_sent or abs(self.__admin_mail_sent - time.time()) > global_config["USER_MAIL_SEND_TIME"]:
            self.__admin_mail_sent = time.time()
        else:
            email_targets.remove(_admin_key)
        mail_lines[_admin_key].extend(["", "user info:", ""])
        for obj_name, ug_dict in prob_objs.iteritems():
            for num_id, stuff in ug_dict.iteritems():
                _mail_key = (obj_name, num_id)
                if obj_name == "group":
                    _info = self._get_gid_info(num_id)
                    mail_lines[_mail_key] = [
                        "This is an informal mail to notify you that",
                        "your group has violated one or more quota-policies",
                        "on {}, group info: {}".format(global_config["SERVER_FULL_NAME"], _info["info"]),
                        ""
                    ]
                else:
                    _info = self._get_uid_info(num_id)
                    mail_lines[_mail_key] = [
                        "This is an informal mail to notify you that",
                        "you have violated one or more quota-policies",
                        "on {}, user info: {}".format(global_config["SERVER_FULL_NAME"], _info["info"]),
                        ""
                    ]
                if _info.get("email", ""):
                    if (obj_name, num_id) not in email_targets:
                        # only send mail if at least USER_MAIL_SEND_TIME seconds
                        if not _info["last_mail_sent"] or abs(_info["last_mail_sent"] - time.time()) > global_config["USER_MAIL_SEND_TIME"]:
                            email_targets.append((obj_name, num_id))
                            _info["last_mail_sent"] = time.time()
                    mail_lines[_admin_key].append(
                        "{} (send mail to {})".format(
                            _info["info"],
                            _info["email"]
                        )
                    )
                else:
                    mail_lines[_admin_key].append(
                        "{} (no email-address set)".format(_info["info"])
                    )
                self.log(_info["info"])
                for dev, d_stuff in stuff.iteritems():
                    log_line = " --- violated {} on {}".format(d_stuff, dev)
                    mail_lines[_admin_key].append(log_line)
                    mail_lines[_mail_key].append(log_line)
                    self.log(log_line)
                mail_lines[_mail_key].extend(
                    [
                        "",
                        "please delete some of your data from the respective devices.",
                        "",
                        "Thank you in advance,",
                        "regards"
                    ]
                )
        _admin_addrs = sum([q_admin.strip().split() for q_admin in global_config["QUOTA_ADMINS"].split(",")], [])
        self.log(
            "Sending {} / {}, {} for {}".format(
                logging_tools.get_plural("user mail", len([_name for _type, _name in email_targets if _type == "user"])),
                logging_tools.get_plural("group mail", len([_name for _type, _name in email_targets if _type == "group"])),
                logging_tools.get_plural("mail", len([_name for _type, _name in email_targets if _type == "admin"])),
                logging_tools.get_plural("admin", len(_admin_addrs)),
            )
        )
        for _type, email_target in email_targets:
            if _type == "admin":
                to_addrs = _admin_addrs
            elif _type == "user":
                to_addrs = [self._get_uid_info(email_target)["email"]]
            else:
                to_addrs = [self._get_gid_info(email_target)["email"]]
            for to_addr in to_addrs:
                log_lines = self.send_mail(
                    to_addr,
                    "quota warning from {}@{}".format(
                        global_config["SERVER_FULL_NAME"],
                        process_tools.get_cluster_name()
                    ),
                    mail_lines[(_type, email_target)]
                )
                for log_line in log_lines:
                    self.log(log_line)

    def _create_machvector(self, builder, cur_time, quota_cache):
        my_vector = builder("values")
        # 10 minutes valid
        valid_until = cur_time + self.Meta.min_time_between_runs * 2
        for dev_name, obj_type, num_id, stuff in quota_cache:
            if obj_type == "group":
                name = self._get_gid_info(num_id, {}).get("groupname", "unknown")
            else:
                name = self._get_uid_info(num_id, {}).get("login", "unknown")
            block_dict = stuff.get_block_dict()
            pfix = "quota.{}.{}.{}".format(obj_type, name, dev_name)
            my_vector.append(hm_classes.mvect_entry(
                "{}.soft".format(pfix),
                info="Soft Limit for $2 $3 on $4",
                default=0,
                value=block_dict["soft"],
                factor=1000,
                base=1000,
                valid_until=valid_until,
                unit="B").build_xml(builder))
            my_vector.append(hm_classes.mvect_entry(
                "{}.hard".format(pfix),
                info="Hard Limit for $2 $3 on $4",
                default=0,
                value=block_dict["hard"],
                factor=1000,
                base=1000,
                valid_until=valid_until,
                unit="B").build_xml(builder))
            my_vector.append(hm_classes.mvect_entry(
                "{}.used".format(pfix),
                info="Used quota for $2 $3 on $4",
                default=0,
                value=block_dict["used"],
                factor=1000,
                base=1000,
                valid_until=valid_until,
                unit="B").build_xml(builder))
        return my_vector
