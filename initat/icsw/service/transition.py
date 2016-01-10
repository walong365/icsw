#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" transition for service containers """

import time

from initat.tools import logging_tools


class ServiceTransition(object):
    def __init__(self, target, service_list, cur_c, inst_xml, log_com, id=None, debug_args=None):
        self.__log_com = log_com
        self.target = target
        self.debug_args = debug_args
        self.id = id
        self.list = cur_c.apply_filter(service_list, inst_xml)
        if not self.list:
            self.log(
                "nothing to do",
                logging_tools.LOG_LEVEL_ERROR,
            )
        self.finished = False
        self.__step_num = 0
        self.log(
            "init, target state is {}, {}: {}".format(
                self.target,
                logging_tools.get_plural("service", len(self.list)),
                ", ".join(sorted([_entry.name for _entry in self.list])),
            )
        )
        self.__init_time = time.time()

    @property
    def init_time(self):
        return self.__init_time

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SrvT] {}".format(what), log_level)

    def step(self, cur_c):
        self.__step_num += 1
        s_time = time.time()
        # next step usgin service container cur_c
        cur_c.update_proc_dict()
        if self.__step_num == 1:
            # init action list
            _action_list = []
            for entry in self.list:
                cur_c.check_service(entry, use_cache=True, refresh=True)
                _action_list.extend([(_action, entry) for _action in cur_c.decide(self.target, entry)])
            self._action_list = _action_list
            if self._action_list:
                self.log(
                    "init action_list with {}: {}".format(
                        logging_tools.get_plural("element", len(self._action_list)),
                        ", ".join(
                            ["{} ({})".format(entry.name, action) for action, entry in self._action_list]
                        ),
                    )
                )
            else:
                self.log("no action_list generated")
            # if self._action_list:
            #    print "***", self._action_list, self._action_list[0][1].name
            # format: name -> init_time
            self.__wait_dict = {}
        _loopcount = 0
        while True:
            _loopcount += 1
            new_list = []
            for _action, entry in self._action_list:
                cur_time = time.time()
                _doit = True
                if entry.name in self.__wait_dict:
                    _wait_time = 2 if self.target == "debug" else int(entry.attrib["wait_time"])
                    if abs(cur_time - self.__wait_dict[entry.name]) < _wait_time:
                        new_list.append((_action, entry))
                        _doit = False
                    else:
                        del self.__wait_dict[entry.name]
                if _doit:
                    if _action == "wait":
                        self.__wait_dict[entry.name] = cur_time
                    else:
                        if _action == "debug":
                            entry.action(_action, cur_c.proc_dict, self.debug_args)
                        else:
                            entry.action(_action, cur_c.proc_dict)
            self._action_list = new_list
            if not self._check_waiting(cur_c):
                # no processes vanished, return
                break
        e_time = time.time()
        self.log(
            "step {:d} after {} took {}, {}{}".format(
                self.__step_num,
                logging_tools.get_diff_time_str(e_time - self.__init_time),
                logging_tools.get_diff_time_str(e_time - s_time),
                logging_tools.get_plural("pending element", len(self._action_list)),
                " (inner loops: {:d})".format(_loopcount) if _loopcount > 1 else "",
            )
        )
        if not self._action_list:
            self.log(
                "finished, transition took {} in {}".format(
                    logging_tools.get_diff_time_str(e_time - self.__init_time),
                    logging_tools.get_plural("step", self.__step_num),
                )
            )
        return len(self._action_list)

    def _check_waiting(self, cur_c):
        _vanished = 0
        _check_keys = self.__wait_dict.keys()
        for _name in _check_keys:
            _srvc = [entry for entry in self.list if entry.name == _name][0]
            cur_c.check_service(_srvc, use_cache=True, refresh=True)
            if not len(_srvc.entry.findall(".//result/pids/pid")):
                del self.__wait_dict[_name]
                _vanished += 1
        return _vanished
