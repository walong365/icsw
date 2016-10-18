# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" config part of md-config-server """

from __future__ import unicode_literals, print_function

from initat.cluster.backbone.models import TOP_MONITORING_CATEGORY, parse_commandline
from initat.md_config_server.config.mon_base_config import StructuredMonBaseConfig
from initat.tools import logging_tools
from .global_config import global_config

__all__ = [
    b"CheckCommand",
]


class CheckCommand(object):
    def __init__(self, name, com_line, config, template, descr, exclude_devices=None, **kwargs):
        self.__name = name
        self.__nag_name = kwargs.pop("icinga_name", self.__name)
        # print self.__name, self.__nag_name
        self.__com_line = com_line
        self.config = config
        self.mccs_id = kwargs.pop("mccs_id", 0)
        self.template = template
        self.exclude_devices = [cur_dev.pk for cur_dev in exclude_devices] or []
        self.servicegroup_names = kwargs.get("servicegroup_names", ["/{}".format(TOP_MONITORING_CATEGORY)])
        self.servicegroup_pks = kwargs.get("servicegroup_pks", [])
        self.check_command_pk = kwargs.get("check_command_pk", None)
        self.special_command_pk = kwargs.get("special_command_pk", None)
        self.is_event_handler = kwargs.get("is_event_handler", False)
        self.is_active = kwargs.get("is_active", True)
        self.event_handler = kwargs.get("event_handler", None)
        self.event_handler_enabled = kwargs.get("event_handler_enabled", True)
        self.__descr = descr.replace(",", ".")
        self.enable_perfdata = kwargs.get("enable_perfdata", False)
        self.volatile = kwargs.get("volatile", False)
        self.mon_check_command = None
        if "db_entry" in kwargs:
            if kwargs["db_entry"].pk:
                self.mon_check_command = kwargs["db_entry"]
        self._generate_md_com_line()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        CheckCommand.gen_conf.log("[cc %s] %s" % (self.__name, what), log_level)

    @property
    def command_line(self):
        return self.__com_line

    @property
    def md_command_line(self):
        return self.__md_com_line

    def get_num_args(self):
        return self.__num_args

    def get_default_value(self, arg_name, def_value):
        return self.__default_values.get(arg_name, def_value)

    def _generate_md_com_line(self):
        arg_info, log_lines = parse_commandline(self.command_line)
        # print arg_info, log_lines
        self.__arg_lut = arg_info["arg_lut"]
        self.__arg_list = arg_info["arg_list"]
        self.__num_args = arg_info["num_args"]
        self.__default_values = arg_info["default_values"]
        self.__md_com_line = arg_info["parsed_com_line"]
        if global_config["DEBUG"]:
            for _line in log_lines:
                self.log(_line)

    def correct_argument_list(self, arg_temp, dev_variables):
        out_list = []
        for arg_name in arg_temp.argument_names:
            value = arg_temp[arg_name]
            if arg_name in self.__default_values and not value:
                dv_value = self.__default_values[arg_name]
                if type(dv_value) == tuple:
                    # var_name and default_value
                    var_name = self.__default_values[arg_name][0]
                    if var_name in dev_variables:
                        value = dev_variables[var_name]
                    else:
                        value = self.__default_values[arg_name][1]
                else:
                    # only default_value
                    value = self.__default_values[arg_name]
            if type(value) in [int, long]:
                out_list.append("{:d}".format(value))
            else:
                out_list.append(value)
        return out_list

    def get_mon_config(self):
        return StructuredMonBaseConfig(
            "command",
            self.__nag_name,
            command_name=self.__nag_name,
            command_line=self.md_command_line
        )

    def __getitem__(self, key):
        if key == "command_name":
            return self.__nag_name
        else:
            raise SyntaxError("illegal call to __getitem__ of check_command (key='{}')".format(key))

    def __setitem__(self, key, value):
        if key == "command_name":
            self.__nag_name = value
        else:
            raise SyntaxError("illegal call to __setitem__ of check_command (key='{}')".format(key))

    def get_config(self):
        return self.config

    def get_template(self, default):
        if self.template:
            return self.template
        else:
            return default

    def get_description(self):
        if self.__descr:
            return self.__descr
        else:
            return self.__name

    @property
    def name(self):
        # returns config name for icinga config
        return self.__nag_name

    @property
    def arg_ll(self):
        """
        returns lut and list
        """
        return (self.__arg_lut, self.__arg_list)

    def __repr__(self):
        return u"{} [{}]".format(self.__name, self.command_line)
