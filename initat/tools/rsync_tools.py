# Copyright (C) 2008,2014-2015 Andreas Lang-Nevyjel
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
""" rsync tools """

import commands
import time

from initat.tools import logging_tools


class rsync_call(object):
    def __init__(self, **args):
        self.__log_command = args.get("log_command", None)
        if args.get("source_path"):
            self.__v_dict = {
                "source_path": args["source_path"],
                "dest_path": args["dest_path"],
                "start_time": None,
                "run_time": None,
                "verbose": args.get("verbose", False)
            }

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__log_command:
            self.__log_command("[rsync] %s" % (what), level)
        else:
            logging_tools.my_syslog(what, level)

    def __getitem__(self, key):
        return self.__v_dict[key]

    def __setitem__(self, key, value):
        self.__v_dict[key] = value

    def rsync(self):
        log_lines = []
        self["start_time"] = time.time()
        self["rsync_com"] = "rsync --stats -a --delete {} {}".format(
            self["source_path"],
            self["dest_path"]
        )
        if self["verbose"]:
            self.log("rsync target is {}".format(self["dest_path"]))
            self.log("starting rsync-command '{}' ...".format(self["rsync_com"]))
        sync_stat, sync_out = commands.getstatusoutput(self["rsync_com"])
        self["call_stat"] = sync_stat
        self["call_log"] = sync_out.split("\n")
        e_time = time.time()
        self["run_time"] = e_time - self["start_time"]
        if self["verbose"]:
            self.log(
                "syncing took {}".format(
                    logging_tools.get_diff_time_str(self["run_time"])
                )
            )
        self._interpret_output()
        log_str = "rsync state is {}, {} of output, took {}".format(
            self._interpret_call_stat(self["call_stat"]),
            logging_tools.get_plural("line", len(self["call_log"])),
            logging_tools.get_diff_time_str(self["run_time"])
        )
        log_lines.append(log_str)
        self.log(log_str,
                 logging_tools.LOG_LEVEL_ERROR if self["call_stat"] else logging_tools.LOG_LEVEL_OK)
        if self["verbose"]:
            for line in self["call_log"]:
                log_lines.append(line)
                self.log(" - {}".format(line))
        # show it
        # pprint.pprint(self.__v_dict)
        return log_lines

    def _interpret_call_stat(self, cs):
        # return strings
        r_str_dict = {
            0: "Success",
            1: "Syntax or usage error",
            2: "Protocol incompatibility",
            3: "Errors selecting input/output files, dirs",
            4: "Requested action not supported: an attempt was made to manipulate 64-bit files on a platform that cannot support them; "
            "or an option was specified that is supported by the client and not by the server.",
            5: "Error starting client-server protocol",
            6: "Daemon unable to append to log-file",
            10: "Error in socket I/O",
            11: "Error in file I/O",
            12: "Error in rsync protocol data stream",
            13: "Errors with program diagnostics",
            14: "Error in IPC code",
            20: "Received SIGUSR1 or SIGINT",
            21: "Some error returned by waitpid()",
            22: "Error allocating core memory buffers",
            23: "Partial transfer due to error",
            24: "Partial transfer due to vanished source files",
            25: "The --max-delete limit stopped deletions",
            30: "Timeout in data send/receive"
        }
        # left and right call stat
        l_cs, r_cs = (cs >> 8, cs & 255)
        return "[{}]".format(
            ", ".join(
                [
                    "{} ({:d})".format(
                        r_str_dict.get(act_cs, "unknown code {:d}".format(act_cs)),
                        act_cs
                    ) for act_cs in [l_cs, r_cs]
                ]
            )
        )

    def _interpret_output(self):
        key_list = [
            "number of files",
            "number of files transferred",
            "total file size",
            "total transferred file size",
            "total bytes sent",
            "total bytes received"
        ]
        key_lut = {key: "".join([part[0] for part in key.split()]) for key in key_list}
        key_dict = {key_lut[key]: 0 for key in key_list}
        for line in [
            s_line for s_line in [
                line.strip() for line in self["call_log"]
            ] if s_line and not s_line.startswith("rsync")
        ]:
            if line.count(":"):
                key, value = line.split(":", 1)
                if key.lower() in key_list:
                    value = value.strip()
                    if value.endswith(" bytes"):
                        value = value[:-6].strip()
                    key_dict[key_lut[key.lower()]] = int(value)
        self["decoded"] = key_dict
