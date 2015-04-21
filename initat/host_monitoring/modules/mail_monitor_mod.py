# Copyright (C) 2001-2008,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of host-monitoring
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
""" monitors the mail subsystem """

import commands
import os
import re
import stat
import time

from initat.host_monitoring import hm_classes, limits
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command


MIN_UPDATE_TIME = 30
# load threshold for mailq call
LOAD_THRESHOLD = 5.0
# invalidate number_of_mails in queue after 10 minutes
INVALIDATE_TIME = 60 * 10


class event(object):
    def __init__(self, year, month, day, time, what):
        self.__year = year
        self.__month = month
        self.__day = day
        self.__time = time
        self.__what = what

    def __repr__(self):
        return "{:d}. {:d} {:d} {}: {}".format(
            self.__day,
            self.__month,
            self.__year,
            self.__time,
            self.__what
        )

    def cause(self):
        return self.__what


class file_object(object):
    def __init__(self, file_name, **kwargs):
        self.__name = file_name
        self.__fd = None
        self.__first_call = True
        self.__seek_to_end = kwargs.get("seek_to_end", True)

    def close(self):
        if self.__fd:
            self.__fd.close()

    def read_lines(self):
        if not self.__fd:
            self.open_it()
        if self.__fd:
            while True:
                try:
                    lines = self.__fd.readlines()
                except IOError, _what:
                    self.log("error reading maillines: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    if not lines:
                        fd_results = os.fstat(self.__fd.fileno())
                        try:
                            st_results = os.stat(self.__name)
                        except OSError:
                            st_results = fd_results
                        if st_results.st_ino == fd_results.st_ino:
                            break
                        else:
                            self.__fd = None
                            self.open_it()
                    else:
                        for line in lines:
                            yield line

    def open_it(self):
        if os.path.isfile(self.__name):
            try:
                self.__fd = file(self.__name, "r")
            except:
                self.__fd = None
            else:
                if self.__first_call:
                    self.__first_call = False
                    if self.__seek_to_end:
                        self.__fd.seek(0, 2)
                self.__where = self.__fd.tell()


class mail_log_object(file_object):
    def __init__(self, mod, name="/var/log/mail", **args):
        self.__mod = mod
        file_object.__init__(self, name, **args)
        self.__act_year = time.localtime()[0]
        self.__client_re = re.compile("^[0-9A-F]+: client=(?P<client>[^\[]+)\[(?P<client_ip>[^\]]+)\].*$")
        self.__relay_re = re.compile("^.*, relay=(?P<relay>[^\[]+)\[(?P<relay_ip>[^\]]+)\]:(?P<relay_port>\d+),.*")
        self.__num_dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__mod.log(u"[mlo] {}".format(what), log_level)

    def get_info_str(self, key):
        return "number of mails {} per minute".format(key.replace(".", " "))

    def parse_lines(self):
        act_time = time.time()
        num_lines = 0
        for act_line in self.read_lines():
            num_lines += 1
            try:
                act_event = self._parse_line(act_line.strip(), act_time)
            except:
                act_event = None
                self.log(
                    "error parsing line '{}': {}".format(
                        act_line.strip(),
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            if act_event:
                self.__num_dict.setdefault(act_event.cause(), 0)
                self.__num_dict[act_event.cause()] += 1
        return self.get_snapshot()

    def get_snapshot(self):
        return self.__num_dict.copy()

    def _parse_line(self, in_line, act_time):
        l_ps = in_line.split()
        if len(l_ps[0]) > 3:
            # format YYYY-MM-DDT....
            _dts = l_ps[0].split("-")
            _ymd, _hms = l_ps[0].split("T", 1)
            _ymd = _ymd.split("-")
            _hms = _hms.split(".")[0]
            self.__act_year, act_month, act_day = (
                int(_ymd[0]),
                int(_ymd[1]),
                int(_ymd[2])
            )
            act_hms_str = _hms
            act_prog = l_ps[1]
            first_text = l_ps[2]
            act_text = " ".join(l_ps[2:])
        else:
            act_month = {
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "okt": 10,
                "oct": 10,
                "nov": 11,
                "dec": 12
            }.get(l_ps[0].lower(), 0)
            act_day = int(l_ps[1])
            act_hms_str = l_ps[2]
            # check timestamp and correct year if necessary
            diff_days = int(
                (
                    time.mktime([self.__act_year, act_month, act_day] + [int(x) for x in act_hms_str.split(":")] + [0, 0, -1]) - act_time
                ) / (3600 * 24)
            )
            if diff_days < -150:
                self.__act_year += 1
            elif diff_days > 150:
                self.__act_year -= 1
            act_text = " ".join(l_ps[5:])
            first_text = l_ps[5]
            # parse act_prog
            act_prog = l_ps[4]
        act_event = None
        if not act_prog.count("/") and not act_prog.endswith(":") and first_text.count("/") and first_text.endswith(":"):
            # first_text is our program, act_prog may be the host name
            act_prog = first_text
            act_text = act_text[len(act_prog) + 1:]
        if act_prog.count("["):
            act_prog, prog_pid = act_prog.split("[")
            prog_pid = int(prog_pid.split("]")[0])
        else:
            prog_pid = 0
        if act_prog.count("/"):
            act_prog, sub_prog = act_prog.split("/")
        else:
            act_prog, sub_prog = (act_prog, "")
        if act_prog == "postfix":
            # postfix line
            if sub_prog == "smtp":
                if act_text.count("status=bounced"):
                    act_event = event(self.__act_year, act_month, act_day, act_hms_str, "bounced")
                elif act_text.count("status=sent"):
                    r_re = self.__relay_re.match(act_text)
                    if r_re:
                        # print r_re.group("relay"), r_re.group("relay_ip"), r_re.group("relay_port")
                        if r_re.group("relay_ip") == "127.0.0.1":
                            act_event = event(self.__act_year, act_month, act_day, act_hms_str, "sent.local")
                        else:
                            act_event = event(self.__act_year, act_month, act_day, act_hms_str, "sent.net")
            elif sub_prog == "local":
                if act_text.count("status=bounced"):
                    act_event = event(self.__act_year, act_month, act_day, act_hms_str, "bounced")
            elif sub_prog == "smtpd":
                c_re = self.__client_re.match(act_text)
                if c_re:
                    if c_re.group("client") == "localhost":
                        act_event = event(self.__act_year, act_month, act_day, act_hms_str, "received.local")
                    else:
                        act_event = event(self.__act_year, act_month, act_day, act_hms_str, "received.net")
                elif act_text.count("blocked using"):
                    act_event = event(self.__act_year, act_month, act_day, act_hms_str, "blocked")
            elif sub_prog == "error":
                if act_text.count("status=bounced"):
                    act_event = event(self.__act_year, act_month, act_day, act_hms_str, "bounced")
        elif act_prog.startswith("spamd"):
            if act_text.count("identified spam"):
                act_event = event(self.__act_year, act_month, act_day, act_hms_str, "spam")
        elif act_prog.startswith("smtpgw") or act_prog.startswith("mailgwd"):
            if act_text.count("AV-SCANNED"):
                # antivirus scan
                if act_text.lower().count("infected"):
                    act_event = event(self.__act_year, act_month, act_day, act_hms_str, "virus")
            elif act_text.count("AS-SCANNED"):
                # antispam scan
                if act_text.lower().count("\"spam\""):
                    act_event = event(self.__act_year, act_month, act_day, act_hms_str, "spam")
        elif act_prog.startswith("sendmail"):
            if act_text.count("mailer=local"):
                act_event = event(self.__act_year, act_month, act_day, act_hms_str, "received")
            elif act_text.count("mailer=relay"):
                act_event = event(self.__act_year, act_month, act_day, act_hms_str, "received")
            elif act_text.count("stat=Sent"):
                act_event = event(self.__act_year, act_month, act_day, act_hms_str, "sent")
        else:
            # print "***", act_hms_str, act_prog
            pass
        return act_event


class _general(hm_classes.hm_module):
    class Meta:
        priority = 10

    def init_module(self):
        self.__maillog_object = mail_log_object(self)
        self.__maillog_object.parse_lines()
        self.__mailq_command = process_tools.find_file("mailq")

    def init_machine_vector(self, mv):
        self.__act_snapshot, self.__check_time = ({}, time.time())
        self.__mailcount = {}
        self.__check_kerio = False
        if self.mailq_command_valid():
            mv.register_entry("mail.total", 0, "total number of mails in mail-queue")
            mv.register_entry("mail.queued", 0, "number of queued mails")
            mv.register_entry("mail.active", 0, "number of active mails")
            mv.register_entry("mail.hold", 0, "number of hold mails")

    def stop_module(self):
        self.log("closing maillog object")
        self.__maillog_object.close()

    def get_mailcount(self):
        return self._get_mail_queue_entries()

    def mailq_command_valid(self):
        return True if self.__mailq_command else False

    def ext_num_mails(self, mail_coms):
        ret_dict = {
            "num_mails": 666,
            "command": "notset"
        }
        if mail_coms:
            format_str = mail_coms.pop(-1)
        else:
            format_str = "F0"
        ret_dict["format"] = format_str
        full_com = (" ".join(mail_coms)).strip()
        if full_com:
            ret_dict["command"] = full_com
            stat, out = commands.getstatusoutput(full_com)
            if stat:
                self.log(
                    "cannot execute '%s' (%d): %s" % (
                        full_com,
                        stat,
                        out
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                mail_lines = [line.strip() for line in out.split("\n") if line.strip]
                if mail_lines:
                    last_line = mail_lines[-1]
                    if format_str == "F0":
                        # kaspersky av
                        line_parts = last_line.split()
                        if len(line_parts) == 6:
                            try:
                                ret_dict["num_mails"] = int(line_parts[1])
                            except:
                                ret_dict["num_mails"] = 666
                        else:
                            self.log("need 6 parts for kaspersky format, got %d" % (len(line_parts)),
                                     logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("unknown format_str '%s'" % (format_str),
                                 logging_tools.LOG_LEVEL_ERROR)
        return ret_dict

    def update_machine_vector(self, mv):
        if self.__check_kerio:
            self._do_kerio_stuff(mv)
        else:
            self._do_postfix_stuff(mv)

    def _do_kerio_stuff(self, mv):
        stat_file = "%s/mailserver/stats.dat" % (self.__kerio_main_dir)
        if os.path.isfile(stat_file):
            try:
                stat_lines = [line.strip() for line in open(stat_file, "r").read().split("\n") if line.strip()]
            except:
                self.log(
                    "error reading stat_file %s: %s" % (
                        stat_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                act_ts = os.stat(stat_file)[stat.ST_MTIME]
                if not self.__last_kerio_check:
                    self.__last_kerio_check = act_ts
                    self.__act_kerio_dict = {}
                counter_dict = {}
                for line in stat_lines:
                    if line.count("<counter"):
                        c_name = line.split("=")[1].split(">")[0][1:-1]
                        c_value = line.split(">")[1].split("<")[0]
                        try:
                            c_value = int(c_value)
                        except:
                            pass
                        else:
                            if c_name.startswith("mta"):
                                # only check mta
                                # parse c_name to dotted notation
                                act_tag, tag_list, lcase_found = ("", [], False)
                                for char in c_name:
                                    is_lcase = char.lower() == char
                                    if lcase_found and not is_lcase:
                                        if act_tag:
                                            tag_list.append(act_tag)
                                            act_tag = ""
                                    act_tag = "%s%s" % (act_tag, char)
                                    lcase_found = is_lcase
                                if act_tag:
                                    tag_list.append(act_tag)
                                t_tag_list = [{"mta": "mail"}.get(tag, tag.lower()) for tag in tag_list]
                                counter_dict[".".join(t_tag_list)] = (c_value, " ".join(tag_list))
                if act_ts != self.__last_kerio_check:
                    self.__last_kerio_dict = self.__act_kerio_dict
                    self.__last_kerio_check = act_ts
                    self.__act_kerio_dict = dict([(key, value) for key, (value, info) in counter_dict.iteritems()])
                if self.__act_kerio_dict:
                    diff_time = abs(act_ts - self.__last_kerio_check) or 60.
                    for key, (value, info) in counter_dict.iteritems():
                        if key not in mv:
                            mv.reg_entry(key, 0., info, "1/min")
                        diff_value = value - self.__last_kerio_dict.get(key, value)
                        mv.reg_update(key, float(diff_value * 60. / diff_time))

    def _do_postfix_stuff(self, mv):
        act_snapshot, act_time = (self.__maillog_object.parse_lines(), time.time())
        diff_time = max(1, abs(act_time - self.__check_time))
        for key, value in act_snapshot.iteritems():
            if key not in self.__act_snapshot:
                mv.register_entry("mail.{}".format(key), 0., self.__maillog_object.get_info_str(key), "1/min")
                diff_value = value
            else:
                diff_value = value - self.__act_snapshot[key]
            mv["mail.{}".format(key)] = float(diff_value * 60. / diff_time)
        self.__act_snapshot, self.__check_time = (act_snapshot, act_time)
        if self.mailq_command_valid():
            mc_dict = self.get_mailcount()
            for key in ["hold", "total", "queued", "active"]:
                mv["mail.%s" % (key)] = mc_dict[key]

    def _get_mail_queue_entries(self):
        # total = queued + hold + active
        self.__mailcount = {
            "total": 0,
            "queued": 0,
            "hold": 0,
            "active": 0
        }
        if self.__mailq_command:
            stat, out = commands.getstatusoutput(self.__mailq_command)
            if stat:
                self.log(
                    "cannot execute mailq (%d): %s" % (stat, out),
                    logging_tools.LOG_LEVEL_WARN)
            else:
                mail_lines = [_line.rstrip() for _line in out.split("\n") if _line.strip()]
                if mail_lines:
                    # check mail ids
                    for line in mail_lines:
                        if not line.startswith(" "):
                            parts = line.split()
                            if len(parts) > 5 and len(parts[0]) > 7:
                                q_id = parts[0]
                                try:
                                    int(q_id.replace("!", "").replace("*", ""), 16)
                                except:
                                    pass
                                else:
                                    if q_id.endswith("!"):
                                        self.__mailcount["hold"] += 1
                                    elif q_id.endswith("*"):
                                        self.__mailcount["active"] += 1
                                    else:
                                        self.__mailcount["queued"] += 1
                                    self.__mailcount["total"] += 1
                    last_line = mail_lines[-1]
                    if last_line.count("empty"):
                        # empty mailqueue
                        pass
                    elif last_line.count("directly"):
                        # mail system down, accessing directly
                        pass
                    else:
                        if last_line.startswith("--"):
                            line_parts = last_line.split()
                            if line_parts[-2].isdigit():
                                self.__mailcount["total"] = int(line_parts[-2])
                            else:
                                self.log(
                                    "cannot parse line '{}' (mailq, notdigit)".format(last_line),
                                    logging_tools.LOG_LEVEL_WARN
                                )
                        else:
                            self.log(
                                "cannot parse line '{}' (mailq, '--' missing)".format(last_line),
                                logging_tools.LOG_LEVEL_WARN
                            )
                else:
                    self.log(
                        "no lines got from {}".format(self.__mailq_command),
                        logging_tools.LOG_LEVEL_WARN
                    )
        return self.__mailcount


class mailq_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("-w", dest="warntotal", type=int, help="warning value for total number of mails in queue [%(default)s]", default=5)
        self.parser.add_argument("-c", dest="crittotal", type=int, help="critical value for total number of mails in queue [%(default)s]", default=10)
        self.parser.add_argument("-wq", dest="warnqueued", type=int, help="warning value for number of queued mails in queue [%(default)s]", default=5)
        self.parser.add_argument("-cq", dest="critqueued", type=int, help="critical value for number of queued mails in queue [%(default)s]", default=10)
        self.parser.add_argument("-wh", dest="warnhold", type=int, help="warning value for number of hold mails in queue [%(default)s]", default=5)
        self.parser.add_argument("-ch", dest="crithold", type=int, help="critical value for number of hold mails in queue [%(default)s]", default=10)
        self.parser.add_argument("-wa", dest="warnactive", type=int, help="warning value for number of active mails in queue [%(default)s]", default=5)
        self.parser.add_argument("-ca", dest="critactive", type=int, help="critical value for number of active mails in queue [%(default)s]", default=10)

    def __call__(self, srv_com, cur_ns):
        if self.module.mailq_command_valid():
            mc_dict = self.module.get_mailcount()
            builder = srv_com.builder()
            srv_com["mail_dict"] = builder.values(
                *[builder.count("%d" % (value), info=key) for key, value in mc_dict.iteritems()])
        else:
            srv_com.set_result("no mailq command defined", server_command.SRV_REPLY_STATE_ERROR)

    def interpret(self, srv_com, cur_ns):
        if type(srv_com) in [int, long]:
            mail_dict = {"total": srv_com, "queued": srv_com}
        elif "mail_dict" in srv_com:
            mail_dict = srv_com["mail_dict"][0]
            mail_dict = {entry.attrib["info"]: int(entry.text) for entry in mail_dict}
        else:
            mail_dict = {"total": int(srv_com["num_mails"].text)}
            mail_dict["queued"] = mail_dict["total"]
        ret_state = limits.check_ceiling(
            mail_dict.get("total", 0),
            cur_ns.warntotal,
            cur_ns.crittotal
        )
        ret_f = []
        if mail_dict.get("queued", 0):
            ret_f = ["%s queued" % (logging_tools.get_plural("mail", mail_dict["queued"]))]
            ret_state = max(
                ret_state,
                limits.check_ceiling(
                    mail_dict.get("queued", 0),
                    cur_ns.warnqueued,
                    cur_ns.critqueued
                )
            )
        if mail_dict.get("active", 0):
            ret_f.append("%d active" % (mail_dict["active"]))
            ret_state = max(
                ret_state,
                limits.check_ceiling(
                    mail_dict.get("active", 0),
                    cur_ns.warnactive,
                    cur_ns.critactive
                )
            )
        if mail_dict.get("hold", 0):
            ret_f.append("%d on hold" % (mail_dict["hold"]))
            ret_state = max(
                ret_state,
                limits.check_ceiling(
                    mail_dict.get("hold", 0),
                    cur_ns.warnhold,
                    cur_ns.crithold
                )
            )
        if mail_dict.get("total", 0):
            ret_f.append("%d total" % (mail_dict["total"]))
        if not ret_f:
            ret_f = ["mailqueue is empty"]
        return ret_state, ", ".join(ret_f)

    def interpret_old(self, result, cur_ns):
        num_mails = hm_classes.net_to_sys(result[3:])["mails"]
        return self.interpret(num_mails, cur_ns)


class ext_mailq_commandX(object):  # hm_classes.hmb_command):
    def __init__(self, **args):
        # hm_classes.hmb_command.__init__(self, "ext_mailq", **args)
        self.help_str = "checks the number of mails in a mail queue via the supplied command"
        self.short_client_info = " -w NUM1 -c NUM2"
        self.long_client_info = "warning and critical values for the mailsystem"
        self.short_client_opts = "w:c:"

    def server_call(self, cm):
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.ext_num_mails(cm)))

    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        result = hm_classes.net_to_sys(result[3:])
        raw_output = lim.get_add_flag("R")
        ret_str, ret_state = ("OK", limits.nag_STATE_CRITICAL)
        if not raw_output:
            ret_state, ret_str = lim.check_ceiling(result["num_mails"])
            result = "%s: %s in queue, format '%s' via '%s'" % (ret_str,
                                                                logging_tools.get_plural("mail", result["num_mails"]),
                                                                result["format"],
                                                                result["command"])
        return ret_state, result
