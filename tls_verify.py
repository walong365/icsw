#!/usr/bin/python-init -Otu
#
# Copyright (C) 2009,2010,2011 Andreas Lang-Nevyjel
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
""" small script to verify TLS of openvpn """

import sys
import logging_tools
import os
import process_tools
import datetime

class allowed_struct(object):
    def __init__(self, in_str):
        in_str = in_str.strip()
        parts = in_str.split(None, 1)
        if len(parts) > 1:
            self.in_str = parts[1]
        else:
            self.in_str = ""
        if parts[0].count(":"):
            self.key, self.allowed_ip = [part.strip() for part in parts[0].split(":", 1)]
        else:
            self.key, self.allowed_ip = (parts[0], None)
    def _parse(self, logger):
        logger.info("building is_allowed struct from %s" % (self.in_str))
        self.__parts = []
        for part in self.in_str.split():
            try:
                self._feed_part(part, logger)
            except:
                logger.error("error parsing in_str '%s': %s" % (in_str, process_tools.get_except_info()))
    def _feed_part(self, part, logger):
        if part.count(";") == 1:
            p_type, p_info = part.split(";")
            if p_type == "T":
                try:
                    from_time_str, to_time_str = p_info.split("-", 1)
                    from_time, to_time = (datetime.time(int(from_time_str.split(":")[0]),
                                                        int(from_time_str.split(":")[1])),
                                          datetime.time(int(to_time_str.split(":")[0]),
                                                        int(to_time_str.split(":")[1])))
                except:
                    logger.error("error parsing from/to: %s" % (process_tools.get_except_info()))
                else:
                    self.__parts.append(("T", (from_time, to_time)))
    def is_allowed(self, logger):
        allowed = True
        if self.in_str:
            self._parse(logger)
            remote_ip = os.environ["untrusted_ip"]
            if self.allowed_ip:
                if remote_ip == self.allowed_ip:
                    logger.info("remote_ip %s matches allowed_ip %s" % (remote_ip, self.allowed_ip))
                else:
                    logger.error("remote_ip %s does not match allowed_ip %s" % (remote_ip, self.allowed_ip))
                    allowed = True
            else:
                logger.info("remote_ip %s ignored (no allowed_ip set)" % (remote_ip))
            if allowed:
                now = datetime.datetime.now()
                now_time = datetime.time(now.hour, now.minute)
                for p_type, p_stuff in self.__parts:
                    if p_type == "T":
                        from_time, to_time = p_stuff
                        if now_time >= from_time and now_time <= to_time:
                            pass
                        else:
                            logger.error("not allowed: %s not in [%s, %s]" % (str(now_time),
                                                                              str(from_time),
                                                                              str(to_time)))
                            allowed = False
        return allowed

def parse_line(line):
    a_struct = allowed_struct(line)
    return (a_struct.key, a_struct)

def main():
    logger = logging_tools.get_logger("openvpn_tls_check",
                                      "uds:/var/lib/logging-server/py_log",
                                      init_logger=True)
    #for key in sorted(os.environ):
    #    logger.info("%s: %s" % (key, str(os.environ[key])))
    ret_code = 1
    if len(sys.argv) == 3:
        if sys.argv[1] == "0":
            if os.environ.has_key("config"):
                match_name = "%s.tls_match" % (os.environ["config"][:-5])
                if os.path.isfile(match_name):
                    logger.info("checking X_509_name '%s' against match_list '%s', remote_ip is %s" % (sys.argv[2],
                                                                                                       match_name,
                                                                                                       os.environ["untrusted_ip"]))
                    # get CN (common name)
                    parts = [part.strip().split("=", 1) for part in sys.argv[2].split("/") if part.strip().count("=")]
                    value_dict = dict([(key, value) for key, value in parts])
                    if value_dict.has_key("CN"):
                        cn = value_dict["CN"]
                        try:
                            match_dict = dict([parse_line(line) for line in file(match_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")])
                        except:
                            logger.error("cannot read match-file %s: %s" % (match_name,
                                                                            process_tools.get_except_info()))
                        else:
                            if cn in match_dict:
                                logger.info("CN %s in match_list" % (cn))
                                a_struct = match_dict[cn]
                                if a_struct:
                                    if a_struct.is_allowed(logger):
                                        ret_code = 0
                                else:
                                    ret_code = 0
                            elif "*" in match_dict:
                                logger.warning("CN %s accepted by wildcard *" % (cn))
                                ret_code = 0
                            else:
                                logger.error("CN %s not in match_list %s" % (cn,
                                                                             match_name))
                    else:
                        logger.critical("No CN found in X_509_name '%s'" % (sys.argv[2]))
                else:
                    logger.critical("no match_name %s found" % (match_name))
            else:
                logger.critical("No config environment variable found")
        else:
            ret_code = 0
    else:
        logger.critical("Need 3 arguments, %d found" % (len(sys.argv)))
    return ret_code

if __name__ == "__main__":
    sys.exit(main())
    
