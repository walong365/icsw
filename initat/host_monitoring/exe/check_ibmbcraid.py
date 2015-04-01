#!/usr/bin/python-init -Ot
#
# Copyright (C) 2012,2013 Andreas Lang-Nevyjel, init.at
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
""" reads the status of IBM SAS Raid-controller(s) """

import telnetlib
import argparse
import pprint
import time
import re
import marshal

CLI_STR = "<CLI>"

class ctrl_command(object):
    target_dict = {}
    com_list = []
    run_time = 0.0
    def __init__(self, command, wait_for=None, targ_key=None):
        self.command = command
        self.wait_for = wait_for or CLI_STR
        self.targ_key = targ_key
        self.send_str = "%s\n" % (self.command)
    def read(self, cur_con):
        if self.command:
            ctrl_command.com_list.append(self.send_str)
            cur_con.write(self.send_str)
        s_time = time.time()
        cur_str = ""
        while True:
            try:
                in_str = cur_con.read_very_eager()
            except EOFError:
                break
            if in_str:
                cur_str = "%s%s" % (cur_str, in_str)
                if cur_str.strip().endswith(self.wait_for):
                    break
        ctrl_command.com_list.append(cur_str)
        if self.targ_key:
            ctrl_command.target_dict[self.targ_key] = self._interpret(self.interpret_list([line.rstrip() for line in "".join(cur_str).split("\r\n") if line.rstrip() and line.strip() != CLI_STR]))
        e_time = time.time()
        ctrl_command.run_time += e_time - s_time
    def interpret_list(self, in_list):
        return in_list
    def _interpret(self, in_value):
        if type(in_value) == type({}):
            for key, value in in_value.iteritems():
                if type(value) == type(""):
                    if value.isdigit() and "%d" % (int(value)) == value:
                        in_value[key] = int(value)
                    elif value.lower() == "true":
                        in_value[key] = True
                    elif value.lower() == "false":
                        in_value[key] = False
                else:
                    self._interpret(value)
        elif type(in_value) == type([]):
            for value in in_value:
                self._interpret(value)
        return in_value
    
class ctrl_list(ctrl_command):
    def interpret_list(self, in_list):
        line_re = re.compile("^\|\s*(?P<num>\d+)\s*\|\s*(?P<name>\S+)\s*\|\s*(?P<status>\S+)\s*\|\s*(?P<ports>\S+)\s*\|\s*(?P<luns>\S+)\s*\|$")
        return [cur_re.groupdict() for cur_re in [line_re.match(cur_line) for cur_line in in_list] if cur_re]
    
class ctrl_detail(ctrl_command):
    def interpret_list(self, in_list):
        keyvalue_re = re.compile("^\s+(?P<key>.*?):(?P<value>.+)$")
        volume_re = re.compile("^\|\s*(?P<volume>\d+)\s*\|\s+(?P<name>\S+)\s*\|\s+(?P<capacity>\S+)\s*\|\s+(?P<raidlevel>\d+)\s*\|\s+(?P<status>.*)\|$")
        kv_dict = dict([(cur_re.group("key").strip(), cur_re.group("value").strip()) for cur_re in [keyvalue_re.match(cur_line) for cur_line in in_list] if cur_re])
        kv_dict["volumes"] = [cur_re.groupdict() for cur_re in [volume_re.match(cur_line) for cur_line in in_list] if cur_re]
        return kv_dict
    
def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--host", type=str, default="", help="address of raidcontroller [%(default)s]", required=True)
    my_parser.add_argument("--user", type=str, default="", help="user login [%(default)s]", required=True)
    my_parser.add_argument("--passwd", type=str, default="", help="user password [%(default)s]", required=True)
    my_parser.add_argument("--target", type=str, default="/tmp/.ctrl_result", help="target file name [%(default)s]")
    options = my_parser.parse_args()
    act_con = telnetlib.Telnet(options.host)
    [act_cmd.read(act_con) for act_cmd in [
        ctrl_command("", "login:"),
        ctrl_command(options.user, "Password:"),
        ctrl_command(options.passwd),
        ctrl_list("list controller", targ_key="ctrl_list"),
        ctrl_detail("detail controller -ctlr 0", targ_key="ctrl_0"),
        ctrl_detail("detail controller -ctlr 1", targ_key="ctrl_1"),
        ctrl_command("exit")]]
    #pprint.pprint(ctrl_command.target_dict)
    # total runtime
    #print ctrl_command.run_time
    file(options.target, "w").write(marshal.dumps(ctrl_command.target_dict))

if __name__ == "__main__":
    main()
    
