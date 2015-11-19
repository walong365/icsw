# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" SNMP base sink """

from ..snmp_struct import ResultNode
from ..handler.instances import handlers
from initat.tools import logging_tools, process_tools


class SNMPSink(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        # possible handlers, build instance list (not only classes)
        self.__handlers = [_handler(self.__log_com) for _handler in handlers]

        # print [_h.Meta.mon_check for _h in self.__handlers]
        # registered handlers
        self.__reg_handlers = {}
        # lut for mon_commands
        self.__mon_com_lut = {}

        self.log("init ({} found)".format(logging_tools.get_plural("handler", len(self.__handlers))))

    @property
    def handlers(self):
        return self.__handlers

    def info(self):
        print self.__reg_handlers

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SS] {}".format(what), log_level)

    def get_handlers(self, schemes):
        return [_val for _val in [self.get_handler(_scheme) for _scheme in schemes] if _val is not None]

    def get_handler_from_mon(self, mon_name):
        if mon_name not in self.__mon_com_lut:
            self.__mon_com_lut[mon_name] = None
            for handler in self.__handlers:
                if handler.Meta.mon_check:
                    _found = [_check for _check in handler.config_mon_check() if _check.Meta.name == mon_name]
                    if _found:
                        self.__mon_com_lut[mon_name] = _found[0]
        return self.__mon_com_lut[mon_name]

    def get_handler(self, scheme):
        full_name, full_name_version = (scheme.full_name, scheme.full_name_version)
        if full_name_version not in self.__reg_handlers:
            # search for full name with version
            _v_found, _found = ([], [])
            for _handler in self.__handlers:
                if full_name_version in _handler.Meta.lookup_keys:
                    _v_found.append(_handler)
                if full_name in _handler.Meta.lookup_keys:
                    _found.append(_handler)
            if _v_found:
                self.__reg_handlers[full_name_version] = _v_found[0]
            elif _found:
                self.__reg_handlers[full_name_version] = _found[0]
            else:
                self.log("no handlers found for {} or {}".format(full_name_version, full_name), logging_tools.LOG_LEVEL_ERROR)
                self.__reg_handlers[full_name_version] = None
        return self.__reg_handlers[full_name_version]

    def update(self, dev, scheme, result_dict, oid_list, flags):
        # update dev with results from given snmp_scheme
        # valid oid_list is oid_list
        # results are in result_dict
        _handler = self.get_handler(scheme)
        if _handler:
            try:
                return _handler.update(dev, scheme, result_dict, oid_list, flags)
            except:
                exc_info = process_tools.exception_info()
                _err_str = "unable to process results: {}".format(process_tools.get_except_info())
                self.log(_err_str, logging_tools.LOG_LEVEL_ERROR)
                for _line in exc_info.log_lines:
                    self.log("  {}".format(_line), logging_tools.LOG_LEVEL_ERROR)
                return ResultNode(error=_err_str)
        else:
            return ResultNode(error="no handler found for {}".format(scheme.full_name_version))
