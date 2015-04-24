# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

from initat.cluster.backbone.models import mon_device_templ, mon_service_templ, \
    TOP_MONITORING_CATEGORY, parse_commandline
from initat.md_config_server.config.mon_config import mon_config
from initat.tools import configfile
from initat.tools import logging_tools
from initat.tools import process_tools


__all__ = [
    "check_command",
]

global_config = configfile.get_global_config(process_tools.get_programm_name())


class check_command(object):
    def __init__(self, name, com_line, config, template, descr, exclude_devices=None, **kwargs):
        self.__name = name
        self.__nag_name = kwargs.pop("icinga_name", self.__name)
        # print self.__name, self.__nag_name
        self.__com_line = com_line
        self.config = config
        self.mccs_id = kwargs.pop("mccs_id", 0)
        self.template = template
        self.exclude_devices = [cur_dev.pk for cur_dev in exclude_devices] or []
        self.servicegroup_names = kwargs.get("servicegroup_names", [TOP_MONITORING_CATEGORY])
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
        check_command.gen_conf.log("[cc %s] %s" % (self.__name, what), log_level)

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
        return mon_config(
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
        return "%s [%s]" % (self.__name, self.command_line)


class device_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = None
        for dev_templ in mon_device_templ.objects.all().select_related("host_check_command"):
            self[dev_templ.pk] = dev_templ
            if dev_templ.is_default:
                self.__default = dev_templ
        self.log(
            "Found {} ({})".format(
                logging_tools.get_plural("device_template", len(self.keys())),
                ", ".join([cur_dt.name for cur_dt in self.itervalues()])
            )
        )
        if self.__default:
            self.log(
                "Found default device_template named '%s'" % (self.__default.name)
            )
        else:
            if self.keys():
                self.__default = self.values()[0]
                self.log(
                    "No default device_template found, using '%s'" % (self.__default.name),
                    logging_tools.LOG_LEVEL_WARN
                )
            else:
                self.log(
                    "No device_template founds, skipping configuration....",
                    logging_tools.LOG_LEVEL_ERROR
                )

    def is_valid(self):
        return self.__default and True or False

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[device_templates] %s" % (what), level)

    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if act_key not in self:
            self.log(
                "key {} not known, using default {} ({:d})".format(
                    str(act_key),
                    unicode(self.__default),
                    self.__default.pk,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            act_key = self.__default.pk
        return super(device_templates, self).__getitem__(act_key)


class service_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = 0
        for srv_templ in mon_service_templ.objects.all().prefetch_related(
            "mon_device_templ_set",
            "mon_contactgroup_set"
        ):
            # db_rec["contact_groups"] = set()
            # generate notification options
            not_options = []
            for long_name, short_name in [
                ("nrecovery", "r"), ("ncritical", "c"), ("nwarning", "w"), ("nunknown", "u"), ("nflapping", "f"), ("nplanned_downtime", "s")
            ]:
                if getattr(srv_templ, long_name):
                    not_options.append(short_name)
            if not not_options:
                not_options.append("n")
            srv_templ.notification_options = not_options
            self[srv_templ.pk] = srv_templ
            self[srv_templ.name] = srv_templ
            srv_templ.contact_groups = list(set(srv_templ.mon_contactgroup_set.all().values_list("name", flat=True)))
        if self.keys():
            self.__default = self.keys()[0]
        self.log("Found %s (%s)" % (
            logging_tools.get_plural("device_template", len(self.keys())),
            ", ".join([cur_v.name for cur_v in self.values()])))

    def is_valid(self):
        return True

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[service_templates] %s" % (what), level)

    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if act_key not in self:
            self.log(
                "key {} not known, using default {} ({:d})".format(
                    str(act_key),
                    unicode(self.__default),
                    self.__default.pk,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            act_key = self.__default.pk
        return super(service_templates, self).__getitem__(act_key)


