#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel
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
""" handles extra servers (for instance liebherr) """

import sys
import optparse
import os
import logging_tools
import process_tools

class extra_server_file(object):
    def __init__(self, name="/etc/sysconfig/cluster/extra_servers"):
        self.__file_name = name
        self._read_file()
        self._write_file()
    def _read_file(self):
        if os.path.isfile(self.__file_name):
            try:
                lines = file(self.__file_name, "r").read().split("\n")
            except:
                logging_tools.my_syslog("error reading %s: %s" % (self.__file_name,
                                                                  process_tools.get_except_info()),
                                        logging_tools.LOG_LEVEL_ERROR)
                lines = []
        else:
            lines = []
        self.__lines = sorted([line.strip() for line in lines if line.strip()])
    def _write_file(self):
        try:
            file(self.__file_name, "w").write("\n".join(sorted(self.__lines) + [""]))
        except:
            logging_tools.my_syslog("error writing %s: %s" % (self.__file_name,
                                                              process_tools.get_except_info()),
                                    logging_tools.LOG_LEVEL_ERROR)
    def add_server(self, s_name):
        if s_name.strip() not in self.__lines:
            self.__lines.append(s_name.strip())
            self._write_file()
    def remove_server(self, s_name):
        if s_name.strip() in self.__lines:
            self.__lines.remove(s_name.strip())
            self._write_file()
    def get_server_list(self):
        return sorted(self.__lines)

class my_opt_parser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self)
        # check for 64-bit Machine
        self.add_option("--add", dest="add_server", action="store_true", default=False, help="Add a new server")
        self.add_option("--remove", dest="remove_server", action="store_true", default=False, help="Remove a server")
        self.add_option("--server", dest="server_name", help="server to add or remove", type="str", default=None)
        self.add_option("--list", dest="list_servers", help="shows all servers present in extra_server_list", action="store_true", default=False)
    def parse(self):
        options, args = self.parse_args()
        if args:
            print "Additional arguments found, exiting"
            sys.exit(0)
        self.options = options

def main():
    ret_code = 0
    my_parser = my_opt_parser()
    my_parser.parse()
    es_file = extra_server_file()
    if my_parser.options.list_servers:
        # list servers
        s_list = es_file.get_server_list()
        print "%s in list%s" % (logging_tools.get_plural("extra server", len(s_list)),
                                ": %s" % (", ".join(sorted(s_list))) if s_list else "")
    if my_parser.options.add_server or my_parser.options.remove_server:
        if my_parser.options.server_name:
            if my_parser.options.add_server:
                es_file.add_server(my_parser.options.server_name)
            else:
                es_file.remove_server(my_parser.options.server_name)
        else:
            print "No servername given for adding or removing"
            ret_code = 5
    return ret_code

if __name__ == "__main__":
    sys.exit(main())
