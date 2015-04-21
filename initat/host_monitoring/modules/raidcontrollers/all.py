# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" raid controller, container for all controllers """

from initat.tools import logging_tools

from initat.host_monitoring.modules.raidcontrollers import CTRL_DICT


class dummy_mod(object):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print("[{:d}] {}".format(log_level, what))


class AllRAIDCtrl(object):
    _all_types = None

    @staticmethod
    def init(module_struct):
        AllRAIDCtrl.CTRL_DICT = CTRL_DICT
        AllRAIDCtrl._all_types = {}
        for _name, _value in CTRL_DICT.iteritems():
            AllRAIDCtrl._all_types[_value.Meta.name] = _value(module_struct, AllRAIDCtrl)

    @staticmethod
    def update(c_type, ctrl_ids=[]):
        if c_type is None:
            c_type = AllRAIDCtrl._all_types.keys()
        elif type(c_type) != list:
            c_type = [c_type]
        for cur_type in c_type:
            AllRAIDCtrl._all_types[cur_type]._update(ctrl_ids)

    @staticmethod
    def ctrl(key):
        if AllRAIDCtrl._all_types:
            # server call
            return AllRAIDCtrl._all_types[key]
        else:
            # client call
            return CTRL_DICT[key](dummy_mod(), AllRAIDCtrl, quiet=True)

    @staticmethod
    def ctrl_class(key):
        # client call
        return CTRL_DICT[key]
