# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" enums for all defined icinga commands """

import time

from dateutil import parser
from enum import Enum
from rest_framework import serializers

from initat.cluster.backbone.models import functions


__all__ = [
    "IcingaCommandEnum",
    "IcingaCommandSerializer",
]


class IcingaCommand(object):
    def __init__(self, name, args, info, for_host, for_service, for_hostgroup, for_servicegroup, for_contact, for_contactgroup):
        self.name = name
        self.args = args
        self.info = info
        self.for_host = for_host
        self.for_service = for_service
        self.for_hostgroup = for_hostgroup
        self.for_servicegroup = for_servicegroup
        self.for_contact = for_contact
        self.for_contactgroup = for_contactgroup
        self.__arg_dict = {arg.name: arg for arg in self.args}
        _arg_names = list(self.__arg_dict.keys())
        for (flag_name, arg_name) in [
            ("for_host", "host_name"),
            ("for_service", "service_description"),
            ("for_contact", "contact_name"),
            ("for_contactgroup", "contactgroup_name"),
            ("for_hostgroup", "hostgroup_name"),
            ("for_servicegroup", "servicegroup_name"),
        ]:
            if getattr(self, flag_name) and arg_name not in _arg_names:
                raise KeyError(
                    "missing argument '{}' when {} is True ({})".format(
                        arg_name,
                        flag_name,
                        self.name,
                    )
                )

    def resolve_args(self, args):
        for name, struct in args.items():
            self.__arg_dict[name].resolve(struct)
        return args

    def create_commands(self, cmd_type, key_list, val_dict, name_dict):
        # cmd_type is one of host or service
        c_list = []
        for entry in key_list:
            entry["host_name"] = name_dict[entry["host_idx"]]
            c_list.append(self.create_command(entry, val_dict))
        return c_list

    def create_command(self, entry, val_dict):
        _r_list = [
            "[{:d}] {}".format(
                int(time.time()),
                self.name,
            )
        ]
        for arg in self.args:
            if arg.name in ["host_name", "service_description"]:
                _val = entry[arg.name]
            else:
                _val = val_dict[arg.name]["value"]
            if isinstance(_val, int):
                _val = "{:d}".format(_val)
            _r_list.append(_val)
        return ";".join(_r_list)


class IcingaCommandArg(object):
    typedict = {}

    def __init__(self, name, optional):
        if name.count(" "):
            raise SyntaxError("Illegal IcingaCommandArg '{}'".format(name))
        self.typedict.setdefault(name, 0)
        self.typedict[name] += 1
        self.name = name
        self.optional = optional
        self.is_author = self.name in ["author"]
        self.is_boolean = self.name in ["persistent", "notify", "sticky"]
        # self.is_tristate = self.name in ["sticky"]
        self.is_string = self.name in ["comment"]
        self.is_timestamp = self.name in ["timestamp"]
        # self.is_sticky = self.name in ["sticky"]

    def resolve(self, struct):
        _raw = struct["raw"]
        if self.is_boolean:
            struct["value"] = (2 if self.name == "sticky" else 1) if _raw else 0
        elif self.is_timestamp:
            struct["value"] = "{:d}".format(int(functions.to_unix_seconds(parser.parse(_raw))))
        else:
            # default value
            struct["value"] = _raw


class IcingaCommandArgSerializer(serializers.Serializer):
    name = serializers.CharField()
    optional = serializers.BooleanField()
    is_boolean = serializers.BooleanField()
    # is_tristate = serializers.BooleanField()
    is_string = serializers.BooleanField()
    is_author = serializers.BooleanField()
    is_timestamp = serializers.BooleanField()


class IcingaCommandSerializer(serializers.Serializer):
    name = serializers.CharField()
    args = IcingaCommandArgSerializer(many=True)
    info = serializers.ListField()
    for_host = serializers.BooleanField()
    for_service = serializers.BooleanField()
    for_hostgroup = serializers.BooleanField()
    for_servicegroup = serializers.BooleanField()
    for_contact = serializers.BooleanField()
    for_contactgroup = serializers.BooleanField()


class IcingaCommandEnum(Enum):
    acknowledge_host_problem = IcingaCommand(
        name="ACKNOWLEDGE_HOST_PROBLEM",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("sticky", optional=False),
            IcingaCommandArg("notify", optional=False),
            IcingaCommandArg("persistent", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Allows you to acknowledge the current problem for the specified "
            "host. By acknowledging the current problem, future notifications "
            "(for the same host state) are disabled.",
            "If the \"sticky\" option is set to two (2), the acknowledgement "
            "will remain until the host recovers (returns to an UP state). "
            "Otherwise the acknowledgement will automatically be removed when "
            "the host changes state.",
            "If the \"notify\" option is set to one (1), a notification will "
            "be sent out to contacts indicating that the current host problem "
            "has been acknowledged, if set to null (0) there will be no notification.",
            "If the \"persistent\" option is set to one (1), the comment associated "
            "with the acknowledgement will remain even after the host recovers.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    acknowledge_host_problem_expire = IcingaCommand(
        name="ACKNOWLEDGE_HOST_PROBLEM_EXPIRE",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("sticky", optional=False),
            IcingaCommandArg("notify", optional=False),
            IcingaCommandArg("persistent", optional=False),
            IcingaCommandArg("timestamp", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Allows you to define the time (seconds since the UNIX epoch) "
            "when the acknowledgement will expire (will be deleted).",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    acknowledge_svc_problem = IcingaCommand(
        name="ACKNOWLEDGE_SVC_PROBLEM",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("sticky", optional=False),
            IcingaCommandArg("notify", optional=False),
            IcingaCommandArg("persistent", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Allows you to acknowledge the current problem for the specified "
            "service. By acknowledging the current problem, future notifications "
            "(for the same servicestate) are disabled.",
            "If the \"sticky\" option is set to two (2), the acknowledgement "
            "will remain until the service recovers (returns to an OK state). "
            "Otherwise the acknowledgement will automatically be removed when "
            "the service changes state.",
            "If the \"notify\" option is set to one (1), a notification will "
            "be sent out to contacts indicating that the current service problem "
            "has been acknowledged, if set to null (0) there will be no notification.",
            "If the \"persistent\" option is set to one (1), the comment associated "
            "with the acknowledgement will remain even after the service recovers.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    acknowledge_svc_problem_expire = IcingaCommand(
        name="ACKNOWLEDGE_SVC_PROBLEM_EXPIRE",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("sticky", optional=False),
            IcingaCommandArg("notify", optional=False),
            IcingaCommandArg("persistent", optional=False),
            IcingaCommandArg("timestamp", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Allows you to define the time (seconds since the UNIX epoch) "
            "when the acknowledgement will expire (will be deleted).",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    add_host_comment = IcingaCommand(
        name="ADD_HOST_COMMENT",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("persistent", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Adds a comment to a particular host. If the \"persistent\" field "
            "is set to zero (0), the comment will be deleted the next time "
            "Icinga is restarted. Otherwise, the comment will persist across "
            "program restarts until it is deleted manually.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    add_svc_comment = IcingaCommand(
        name="ADD_SVC_COMMENT",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("persistent", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Adds a comment to a particular service. If the \"persistent\" field "
            "is set to zero (0), the comment will be deleted the next time "
            "Icinga is restarted. Otherwise, the comment will persist across "
            "program restarts until it is deleted manually.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_contact_host_notification_timeperiod = IcingaCommand(
        name="CHANGE_CONTACT_HOST_NOTIFICATION_TIMEPERIOD",
        args=[
            IcingaCommandArg("contact_name", optional=False),
            IcingaCommandArg("notification_timeperiod", optional=False),
        ],
        info=[
            "Changes the host notification timeperiod for a particular contact "
            "to what is specified by the \"notification_timeperiod\" option. "
            "The \"notification_timeperiod\" option should be the short name "
            "of the timeperiod that is to be used as the contact's host notification "
            "timeperiod. The timeperiod must have been configured in Icinga "
            "before it was last (re)started.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    change_contact_modattr = IcingaCommand(
        name="CHANGE_CONTACT_MODATTR",
        args=[
            IcingaCommandArg("contact_name", optional=False),
            IcingaCommandArg("value", optional=False),
        ],
        info=[
            "This command changes the modified attributes value for the specified "
            "contact. Modified attributes values are used by Icinga to determine "
            "which object properties should be retained across program restarts. "
            "Thus, modifying the value of the attributes can affect data retention. "
            "This is an advanced option and should only be used by people "
            "who are intimately familiar with the data retention logic in "
            "Icinga.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    change_contact_modhattr = IcingaCommand(
        name="CHANGE_CONTACT_MODHATTR",
        args=[
            IcingaCommandArg("contact_name", optional=False),
            IcingaCommandArg("value", optional=False),
        ],
        info=[
            "This command changes the modified host attributes value for the "
            "specified contact. Modified attributes values are used by Icinga "
            "to determine which object properties should be retained across "
            "program restarts. Thus, modifying the value of the attributes "
            "can affect data retention. This is an advanced option and should "
            "only be used by people who are intimately familiar with the data "
            "retention logic in Icinga.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    change_contact_modsattr = IcingaCommand(
        name="CHANGE_CONTACT_MODSATTR",
        args=[
            IcingaCommandArg("contact_name", optional=False),
            IcingaCommandArg("value", optional=False),
        ],
        info=[
            "This command changes the modified service attributes value for "
            "the specified contact. Modified attributes values are used by "
            "Icinga to determine which object properties should be retained "
            "across program restarts. Thus, modifying the value of the attributes "
            "can affect data retention. This is an advanced option and should "
            "only be used by people who are intimately familiar with the data "
            "retention logic in Icinga.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    change_contact_svc_notification_timeperiod = IcingaCommand(
        name="CHANGE_CONTACT_SVC_NOTIFICATION_TIMEPERIOD",
        args=[
            IcingaCommandArg("contact_name", optional=False),
            IcingaCommandArg("notification_timeperiod", optional=False),
        ],
        info=[
            "Changes the service notification timeperiod for a particular "
            "contact to what is specified by the \"notification_timeperiod\" "
            "option. The \"notification_timeperiod\" option should be the short "
            "name of the timeperiod that is to be used as the contact's service "
            "notification timeperiod. The timeperiod must have been configured "
            "in Icinga before it was last (re)started.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    change_custom_contact_var = IcingaCommand(
        name="CHANGE_CUSTOM_CONTACT_VAR",
        args=[
            IcingaCommandArg("contact_name", optional=False),
            IcingaCommandArg("varname", optional=False),
            IcingaCommandArg("varvalue", optional=False),
        ],
        info=[
            "Changes the value of a custom contact variable.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    change_custom_host_var = IcingaCommand(
        name="CHANGE_CUSTOM_HOST_VAR",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("varname", optional=False),
            IcingaCommandArg("varvalue", optional=False),
        ],
        info=[
            "Changes the value of a custom host variable.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_custom_svc_var = IcingaCommand(
        name="CHANGE_CUSTOM_SVC_VAR",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("varname", optional=False),
            IcingaCommandArg("varvalue", optional=False),
        ],
        info=[
            "Changes the value of a custom service variable.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_global_host_event_handler = IcingaCommand(
        name="CHANGE_GLOBAL_HOST_EVENT_HANDLER",
        args=[
            IcingaCommandArg("event_handler_command", optional=False),
        ],
        info=[
            "Changes the global host event handler command to be that specified "
            "by the \"event_handler_command\" option. The \"event_handler_command\" "
            "option specifies the short name of the command that should be "
            "used as the new host event handler. The command must have been "
            "configured in Icinga before it was last (re)started.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_global_svc_event_handler = IcingaCommand(
        name="CHANGE_GLOBAL_SVC_EVENT_HANDLER",
        args=[
            IcingaCommandArg("event_handler_command", optional=False),
        ],
        info=[
            "Changes the global service event handler command to be that specified "
            "by the \"event_handler_command\" option. The \"event_handler_command\" "
            "option specifies the short name of the command that should be "
            "used as the new service event handler. The command must have "
            "been configured in Icinga before it was last (re)started.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_host_check_command = IcingaCommand(
        name="CHANGE_HOST_CHECK_COMMAND",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_command", optional=False),
        ],
        info=[
            "Changes the check command for a particular host to be that specified "
            "by the \"check_command\" option. The \"check_command\" option specifies "
            "the short name of the command that should be used as the new "
            "host check command. The command must have been configured in "
            "Icinga before it was last (re)started.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_host_check_timeperiod = IcingaCommand(
        name="CHANGE_HOST_CHECK_TIMEPERIOD",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("timeperiod", optional=False),
        ],
        info=[
            "Changes the valid check period for the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_host_event_handler = IcingaCommand(
        name="CHANGE_HOST_EVENT_HANDLER",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("event_handler_command", optional=False),
        ],
        info=[
            "Changes the event handler command for a particular host to be "
            "that specified by the \"event_handler_command\" option. The \"event_handler_command\" "
            "option specifies the short name of the command that should be "
            "used as the new host event handler. The command must have been "
            "configured in Icinga before it was last (re)started.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_host_modattr = IcingaCommand(
        name="CHANGE_HOST_MODATTR",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("value", optional=False),
        ],
        info=[
            "This command changes the modified attributes value for the specified "
            "host. Modified attributes values are used by Icinga to determine "
            "which object properties should be retained across program restarts. "
            "Thus, modifying the value of the attributes can affect data retention. "
            "This is an advanced option and should only be used by people "
            "who are intimately familiar with the data retention logic in "
            "Icinga.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_host_notification_timeperiod = IcingaCommand(
        name="CHANGE_HOST_NOTIFICATION_TIMEPERIOD",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("notification_timeperiod", optional=False),
        ],
        info=[
            "Changes the notification timeperiod for a particular host to "
            "what is specified by the \"notification_timeperiod\" option. The "
            "\"notification_timeperiod\" option should be the short name of "
            "the timeperiod that is to be used as the service notification "
            "timeperiod. The timeperiod must have been configured in Icinga "
            "before it was last (re)started.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_max_host_check_attempts = IcingaCommand(
        name="CHANGE_MAX_HOST_CHECK_ATTEMPTS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_attempts", optional=False),
        ],
        info=[
            "Changes the maximum number of check attempts (retries) for a "
            "particular host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_max_svc_check_attempts = IcingaCommand(
        name="CHANGE_MAX_SVC_CHECK_ATTEMPTS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_attempts", optional=False),
        ],
        info=[
            "Changes the maximum number of check attempts (retries) for a "
            "particular service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_normal_host_check_interval = IcingaCommand(
        name="CHANGE_NORMAL_HOST_CHECK_INTERVAL",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_interval", optional=False),
        ],
        info=[
            "Changes the normal (regularly scheduled) check interval for a "
            "particular host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_normal_svc_check_interval = IcingaCommand(
        name="CHANGE_NORMAL_SVC_CHECK_INTERVAL",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_interval", optional=False),
        ],
        info=[
            "Changes the normal (regularly scheduled) check interval for a "
            "particular service",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_retry_host_check_interval = IcingaCommand(
        name="CHANGE_RETRY_HOST_CHECK_INTERVAL",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_interval", optional=False),
        ],
        info=[
            "Changes the retry check interval for a particular host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_retry_svc_check_interval = IcingaCommand(
        name="CHANGE_RETRY_SVC_CHECK_INTERVAL",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_interval", optional=False),
        ],
        info=[
            "Changes the retry check interval for a particular service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_svc_check_command = IcingaCommand(
        name="CHANGE_SVC_CHECK_COMMAND",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_command", optional=False),
        ],
        info=[
            "Changes the check command for a particular service to be that "
            "specified by the \"check_command\" option. The \"check_command\" "
            "option specifies the short name of the command that should be "
            "used as the new service check command. The command must have "
            "been configured in Icinga before it was last (re)started.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_svc_check_timeperiod = IcingaCommand(
        name="CHANGE_SVC_CHECK_TIMEPERIOD",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_timeperiod", optional=False),
        ],
        info=[
            "Changes the check timeperiod for a particular service to what "
            "is specified by the \"check_timeperiod\" option. The \"check_timeperiod\" "
            "option should be the short name of the timeperod that is to be "
            "used as the service check timeperiod. The timeperiod must have "
            "been configured in Icinga before it was last (re)started.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_svc_event_handler = IcingaCommand(
        name="CHANGE_SVC_EVENT_HANDLER",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("event_handler_command", optional=False),
        ],
        info=[
            "Changes the event handler command for a particular service to "
            "be that specified by the \"event_handler_command\" option. The "
            "\"event_handler_command\" option specifies the short name of the "
            "command that should be used as the new service event handler. "
            "The command must have been configured in Icinga before it was "
            "last (re)started.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_svc_modattr = IcingaCommand(
        name="CHANGE_SVC_MODATTR",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("value", optional=False),
        ],
        info=[
            "This command changes the modified attributes value for the specified "
            "service. Modified attributes values are used by Icinga to determine "
            "which object properties should be retained across program restarts. "
            "Thus, modifying the value of the attributes can affect data retention. "
            "This is an advanced option and should only be used by people "
            "who are intimately familiar with the data retention logic in "
            "Icinga.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    change_svc_notification_timeperiod = IcingaCommand(
        name="CHANGE_SVC_NOTIFICATION_TIMEPERIOD",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("notification_timeperiod", optional=False),
        ],
        info=[
            "Changes the notification timeperiod for a particular service "
            "to what is specified by the \"notification_timeperiod\" option. "
            "The \"notification_timeperiod\" option should be the short name "
            "of the timeperiod that is to be used as the service notification "
            "timeperiod. The timeperiod must have been configured in Icinga "
            "before it was last (re)started.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    delay_host_notification = IcingaCommand(
        name="DELAY_HOST_NOTIFICATION",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("notification_time", optional=False),
        ],
        info=[
            "Delays the next notification for a particular host until \"notification_time\". "
            "The \"notification_time\" argument is specified in time_t format "
            "(seconds since the UNIX epoch). Note that this will only have "
            "an affect if the host stays in the same problem state that it "
            "is currently in. If the host changes to another state, a new "
            "notification may go out before the time you specify in the \"notification_time\" "
            "argument.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    delay_svc_notification = IcingaCommand(
        name="DELAY_SVC_NOTIFICATION",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("notification_time", optional=False),
        ],
        info=[
            "Delays the next notification for a parciular service until \"notification_time\". "
            "The \"notification_time\" argument is specified in time_t format "
            "(seconds since the UNIX epoch). Note that this will only have "
            "an affect if the service stays in the same problem state that "
            "it is currently in. If the service changes to another state, "
            "a new notification may go out before the time you specify in "
            "the \"notification_time\" argument.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_all_host_comments = IcingaCommand(
        name="DEL_ALL_HOST_COMMENTS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Deletes all comments associated with a particular host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_all_svc_comments = IcingaCommand(
        name="DEL_ALL_SVC_COMMENTS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Deletes all comments associated with a particular service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_downtime_by_hostgroup_name = IcingaCommand(
        name="DEL_DOWNTIME_BY_HOSTGROUP_NAME",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
            IcingaCommandArg("hostname", optional=True),
            IcingaCommandArg("servicedesc", optional=True),
            IcingaCommandArg("starttime", optional=True),
            IcingaCommandArg("commentstring", optional=True),
        ],
        info=[
            "Deletes the host downtime entries and associated services of "
            "all hosts of the host group matching the \"hostgroup_name\" argument. "
            "If the downtime is currently in effect, the host will come out "
            "of scheduled downtime (as long as there are no other overlapping "
            "active downtime entries). Please note that you can add more (optional) "
            "\"filters\" to limit the scope.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_downtime_by_host_name = IcingaCommand(
        name="DEL_DOWNTIME_BY_HOST_NAME",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("servicedesc", optional=True),
            IcingaCommandArg("starttime", optional=True),
            IcingaCommandArg("commentstring", optional=True),
        ],
        info=[
            "Deletes the host downtime entry and associated services for the "
            "host whose host_name matches the \"host_name\" argument. If the "
            "downtime is currently in effect, the host will come out of scheduled "
            "downtime (as long as there are no other overlapping active downtime "
            "entries). Please note that you can add more (optional) \"filters\" "
            "to limit the scope.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_downtime_by_start_time_comment = IcingaCommand(
        name="DEL_DOWNTIME_BY_START_TIME_COMMENT",
        args=[
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("comment_string", optional=True),
        ],
        info=[
            "Deletes downtimes with start times matching the timestamp specified "
            "by the \"start time\" argument and an optional comment string.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_host_comment = IcingaCommand(
        name="DEL_HOST_COMMENT",
        args=[
            IcingaCommandArg("comment_id", optional=False),
        ],
        info=[
            "Deletes a host comment. The id number of the comment that is "
            "to be deleted must be specified.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_host_downtime = IcingaCommand(
        name="DEL_HOST_DOWNTIME",
        args=[
            IcingaCommandArg("downtime_id", optional=False),
        ],
        info=[
            "Deletes the host downtime entry that has an ID number matching "
            "the \"downtime_id\" argument. If the downtime is currently in effect, "
            "the host will come out of scheduled downtime (as long as there "
            "are no other overlapping active downtime entries).",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_svc_comment = IcingaCommand(
        name="DEL_SVC_COMMENT",
        args=[
            IcingaCommandArg("comment_id", optional=False),
        ],
        info=[
            "Deletes a service comment. The id number of the comment that "
            "is to be deleted must be specified.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    del_svc_downtime = IcingaCommand(
        name="DEL_SVC_DOWNTIME",
        args=[
            IcingaCommandArg("downtime_id", optional=False),
        ],
        info=[
            "Deletes the service downtime entry that has an ID number matching "
            "the \"downtime_id\" argument. If the downtime is currently in effect, "
            "the service will come out of scheduled downtime (as long as there "
            "are no other overlapping active downtime entries).",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_all_notifications_beyond_host = IcingaCommand(
        name="DISABLE_ALL_NOTIFICATIONS_BEYOND_HOST",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables notifications for all hosts and services \"beyond\" (e.g. "
            "on all child hosts of) the specified host. The current notification "
            "setting for the specified host is not affected.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_contactgroup_host_notifications = IcingaCommand(
        name="DISABLE_CONTACTGROUP_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contactgroup_name", optional=False),
        ],
        info=[
            "Disables host notifications for all contacts in a particular "
            "contactgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=True,
    )
    disable_contactgroup_svc_notifications = IcingaCommand(
        name="DISABLE_CONTACTGROUP_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contactgroup_name", optional=False),
        ],
        info=[
            "Disables service notifications for all contacts in a particular "
            "contactgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=True,
    )
    disable_contact_host_notifications = IcingaCommand(
        name="DISABLE_CONTACT_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contact_name", optional=False),
        ],
        info=[
            "Disables host notifications for a particular contact.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    disable_contact_svc_notifications = IcingaCommand(
        name="DISABLE_CONTACT_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contact_name", optional=False),
        ],
        info=[
            "Disables service notifications for a particular contact.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    disable_event_handlers = IcingaCommand(
        name="DISABLE_EVENT_HANDLERS",
        args=[],
        info=[
            "Disables host and service event handlers on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_failure_prediction = IcingaCommand(
        name="DISABLE_FAILURE_PREDICTION",
        args=[],
        info=[
            "Disables failure prediction on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_flap_detection = IcingaCommand(
        name="DISABLE_FLAP_DETECTION",
        args=[],
        info=[
            "Disables host and service flap detection on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_hostgroup_host_checks = IcingaCommand(
        name="DISABLE_HOSTGROUP_HOST_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Disables active checks for all hosts in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_hostgroup_host_notifications = IcingaCommand(
        name="DISABLE_HOSTGROUP_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Disables notifications for all hosts in a particular hostgroup. "
            "This does not disable notifications for the services associated "
            "with the hosts in the hostgroup - see the DISABLE_HOSTGROUP_SVC_NOTIFICATIONS "
            "command for that.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_hostgroup_passive_host_checks = IcingaCommand(
        name="DISABLE_HOSTGROUP_PASSIVE_HOST_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Disables passive checks for all hosts in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_hostgroup_passive_svc_checks = IcingaCommand(
        name="DISABLE_HOSTGROUP_PASSIVE_SVC_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Disables passive checks for all services associated with hosts "
            "in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_hostgroup_svc_checks = IcingaCommand(
        name="DISABLE_HOSTGROUP_SVC_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Disables active checks for all services associated with hosts "
            "in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_hostgroup_svc_notifications = IcingaCommand(
        name="DISABLE_HOSTGROUP_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Disables notifications for all services associated with hosts "
            "in a particular hostgroup. This does not disable notifications "
            "for the hosts in the hostgroup - see the DISABLE_HOSTGROUP_HOST_NOTIFICATIONS "
            "command for that.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_and_child_notifications = IcingaCommand(
        name="DISABLE_HOST_AND_CHILD_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables notifications for the specified host, as well as all "
            "hosts \"beyond\" (e.g. on all child hosts of) the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_check = IcingaCommand(
        name="DISABLE_HOST_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables (regularly scheduled and on-demand) active checks of "
            "the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_event_handler = IcingaCommand(
        name="DISABLE_HOST_EVENT_HANDLER",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables the event handler for the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_flap_detection = IcingaCommand(
        name="DISABLE_HOST_FLAP_DETECTION",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables flap detection for the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_freshness_checks = IcingaCommand(
        name="DISABLE_HOST_FRESHNESS_CHECKS",
        args=[],
        info=[
            "Disables freshness checks of all hosts on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_notifications = IcingaCommand(
        name="DISABLE_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables notifications for a particular host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_svc_checks = IcingaCommand(
        name="DISABLE_HOST_SVC_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables active checks of all services on the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_host_svc_notifications = IcingaCommand(
        name="DISABLE_HOST_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables notifications for all services on the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_notifications = IcingaCommand(
        name="DISABLE_NOTIFICATIONS",
        args=[],
        info=[
            "Disables host and service notifications on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_notifications_expire_time = IcingaCommand(
        name="DISABLE_NOTIFICATIONS_EXPIRE_TIME",
        args=[],
        info=[
            "<schedule_time> has no effect currently, set it to current timestamp "
            "in your scripts.",
            "Disables host and service notifications on a program-wide basis, "
            "with given expire time.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_passive_host_checks = IcingaCommand(
        name="DISABLE_PASSIVE_HOST_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables acceptance and processing of passive host checks for "
            "the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_passive_svc_checks = IcingaCommand(
        name="DISABLE_PASSIVE_SVC_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Disables passive checks for the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_performance_data = IcingaCommand(
        name="DISABLE_PERFORMANCE_DATA",
        args=[],
        info=[
            "Disables the processing of host and service performance data "
            "on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_servicegroup_host_checks = IcingaCommand(
        name="DISABLE_SERVICEGROUP_HOST_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Disables active checks for all hosts that have services that "
            "are members of a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_servicegroup_host_notifications = IcingaCommand(
        name="DISABLE_SERVICEGROUP_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Disables notifications for all hosts that have services that "
            "are members of a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_servicegroup_passive_host_checks = IcingaCommand(
        name="DISABLE_SERVICEGROUP_PASSIVE_HOST_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Disables the acceptance and processing of passive checks for "
            "all hosts that have services that are members of a particular "
            "service group.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_servicegroup_passive_svc_checks = IcingaCommand(
        name="DISABLE_SERVICEGROUP_PASSIVE_SVC_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Disables the acceptance and processing of passive checks for "
            "all services in a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_servicegroup_svc_checks = IcingaCommand(
        name="DISABLE_SERVICEGROUP_SVC_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Disables active checks for all services in a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_servicegroup_svc_notifications = IcingaCommand(
        name="DISABLE_SERVICEGROUP_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Disables notifications for all services that are members of a "
            "particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_service_freshness_checks = IcingaCommand(
        name="DISABLE_SERVICE_FRESHNESS_CHECKS",
        args=[],
        info=[
            "Disables freshness checks of all services on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_svc_check = IcingaCommand(
        name="DISABLE_SVC_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Disables active checks for a particular service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_svc_event_handler = IcingaCommand(
        name="DISABLE_SVC_EVENT_HANDLER",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Disables the event handler for the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_svc_flap_detection = IcingaCommand(
        name="DISABLE_SVC_FLAP_DETECTION",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Disables flap detection for the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    disable_svc_notifications = IcingaCommand(
        name="DISABLE_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Disables notifications for a particular service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_all_notifications_beyond_host = IcingaCommand(
        name="ENABLE_ALL_NOTIFICATIONS_BEYOND_HOST",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables notifications for all hosts and services \"beyond\" (e.g. "
            "on all child hosts of) the specified host. The current notification "
            "setting for the specified host is not affected. Notifications "
            "will only be sent out for these hosts and services if notifications "
            "are also enabled on a program-wide basis.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_contactgroup_host_notifications = IcingaCommand(
        name="ENABLE_CONTACTGROUP_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contactgroup_name", optional=False),
        ],
        info=[
            "Enables host notifications for all contacts in a particular contactgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=True,
    )
    enable_contactgroup_svc_notifications = IcingaCommand(
        name="ENABLE_CONTACTGROUP_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contactgroup_name", optional=False),
        ],
        info=[
            "Enables service notifications for all contacts in a particular "
            "contactgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=True,
    )
    enable_contact_host_notifications = IcingaCommand(
        name="ENABLE_CONTACT_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contact_name", optional=False),
        ],
        info=[
            "Enables host notifications for a particular contact.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    enable_contact_svc_notifications = IcingaCommand(
        name="ENABLE_CONTACT_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("contact_name", optional=False),
        ],
        info=[
            "Disables service notifications for a particular contact.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=True,
        for_contactgroup=False,
    )
    enable_event_handlers = IcingaCommand(
        name="ENABLE_EVENT_HANDLERS",
        args=[],
        info=[
            "Enables host and service event handlers on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_failure_prediction = IcingaCommand(
        name="ENABLE_FAILURE_PREDICTION",
        args=[],
        info=[
            "Enables failure prediction on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_flap_detection = IcingaCommand(
        name="ENABLE_FLAP_DETECTION",
        args=[],
        info=[
            "Enables host and service flap detection on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_hostgroup_host_checks = IcingaCommand(
        name="ENABLE_HOSTGROUP_HOST_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Enables active checks for all hosts in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_hostgroup_host_notifications = IcingaCommand(
        name="ENABLE_HOSTGROUP_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Enables notifications for all hosts in a particular hostgroup. "
            "This does not enable notifications for the services associated "
            "with the hosts in the hostgroup - see the ENABLE_HOSTGROUP_SVC_NOTIFICATIONS "
            "command for that. In order for notifications to be sent out for "
            "these hosts, notifications must be enabled on a program-wide "
            "basis as well.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_hostgroup_passive_host_checks = IcingaCommand(
        name="ENABLE_HOSTGROUP_PASSIVE_HOST_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Enables passive checks for all hosts in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_hostgroup_passive_svc_checks = IcingaCommand(
        name="ENABLE_HOSTGROUP_PASSIVE_SVC_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Enables passive checks for all services associated with hosts "
            "in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_hostgroup_svc_checks = IcingaCommand(
        name="ENABLE_HOSTGROUP_SVC_CHECKS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Enables active checks for all services associated with hosts "
            "in a particular hostgroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_hostgroup_svc_notifications = IcingaCommand(
        name="ENABLE_HOSTGROUP_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
        ],
        info=[
            "Enables notifications for all services that are associated with "
            "hosts in a particular hostgroup. This does not enable notifications "
            "for the hosts in the hostgroup - see the ENABLE_HOSTGROUP_HOST_NOTIFICATIONS "
            "command for that. In order for notifications to be sent out for "
            "these services, notifications must be enabled on a program-wide "
            "basis as well.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_and_child_notifications = IcingaCommand(
        name="ENABLE_HOST_AND_CHILD_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables notifications for the specified host, as well as all "
            "hosts \"beyond\" (e.g. on all child hosts of) the specified host. "
            "Notifications will only be sent out for these hosts if notifications "
            "are also enabled on a program-wide basis.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_check = IcingaCommand(
        name="ENABLE_HOST_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables (regularly scheduled and on-demand) active checks of "
            "the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_event_handler = IcingaCommand(
        name="ENABLE_HOST_EVENT_HANDLER",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables the event handler for the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_flap_detection = IcingaCommand(
        name="ENABLE_HOST_FLAP_DETECTION",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables flap detection for the specified host. In order for the "
            "flap detection algorithms to be run for the host, flap detection "
            "must be enabled on a program-wide basis as well.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_freshness_checks = IcingaCommand(
        name="ENABLE_HOST_FRESHNESS_CHECKS",
        args=[],
        info=[
            "Enables freshness checks of all hosts on a program-wide basis. "
            "Individual hosts that have freshness checks disabled will not "
            "be checked for freshness.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_notifications = IcingaCommand(
        name="ENABLE_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables notifications for a particular host. Notifications will "
            "be sent out for the host only if notifications are enabled on "
            "a program-wide basis as well.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_svc_checks = IcingaCommand(
        name="ENABLE_HOST_SVC_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables active checks of all services on the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_host_svc_notifications = IcingaCommand(
        name="ENABLE_HOST_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables notifications for all services on the specified host. "
            "Note that notifications will not be sent out if notifications "
            "are disabled on a program-wide basis.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_notifications = IcingaCommand(
        name="ENABLE_NOTIFICATIONS",
        args=[],
        info=[
            "Enables host and service notifications on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_passive_host_checks = IcingaCommand(
        name="ENABLE_PASSIVE_HOST_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables acceptance and processing of passive host checks for "
            "the specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_passive_svc_checks = IcingaCommand(
        name="ENABLE_PASSIVE_SVC_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Enables passive checks for the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_performance_data = IcingaCommand(
        name="ENABLE_PERFORMANCE_DATA",
        args=[],
        info=[
            "Enables the processing of host and service performance data on "
            "a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_servicegroup_host_checks = IcingaCommand(
        name="ENABLE_SERVICEGROUP_HOST_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Enables active checks for all hosts that have services that are "
            "members of a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_servicegroup_host_notifications = IcingaCommand(
        name="ENABLE_SERVICEGROUP_HOST_NOTIFICATIONS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Enables notifications for all hosts that have services that are "
            "members of a particular servicegroup. In order for notifications "
            "to be sent out for these hosts, notifications must also be enabled "
            "on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_servicegroup_passive_host_checks = IcingaCommand(
        name="ENABLE_SERVICEGROUP_PASSIVE_HOST_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Enables the acceptance and processing of passive checks for all "
            "hosts that have services that are members of a particular service "
            "group.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_servicegroup_passive_svc_checks = IcingaCommand(
        name="ENABLE_SERVICEGROUP_PASSIVE_SVC_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Enables the acceptance and processing of passive checks for all "
            "services in a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_servicegroup_svc_checks = IcingaCommand(
        name="ENABLE_SERVICEGROUP_SVC_CHECKS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Enables active checks for all services in a particular servicegroup.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_servicegroup_svc_notifications = IcingaCommand(
        name="ENABLE_SERVICEGROUP_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
        ],
        info=[
            "Enables notifications for all services that are members of a "
            "particular servicegroup. In order for notifications to be sent "
            "out for these services, notifications must also be enabled on "
            "a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_service_freshness_checks = IcingaCommand(
        name="ENABLE_SERVICE_FRESHNESS_CHECKS",
        args=[],
        info=[
            "Enables freshness checks of all services on a program-wide basis. "
            "Individual services that have freshness checks disabled will "
            "not be checked for freshness.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_svc_check = IcingaCommand(
        name="ENABLE_SVC_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Enables active checks for a particular service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_svc_event_handler = IcingaCommand(
        name="ENABLE_SVC_EVENT_HANDLER",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Enables the event handler for the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_svc_flap_detection = IcingaCommand(
        name="ENABLE_SVC_FLAP_DETECTION",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Enables flap detection for the specified service. In order for "
            "the flap detection algorithms to be run for the service, flap "
            "detection must be enabled on a program-wide basis as well.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    enable_svc_notifications = IcingaCommand(
        name="ENABLE_SVC_NOTIFICATIONS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Enables notifications for a particular service. Notifications "
            "will be sent out for the service only if notifications are enabled "
            "on a program-wide basis as well.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    process_file = IcingaCommand(
        name="PROCESS_FILE",
        args=[
            IcingaCommandArg("file_name", optional=False),
            IcingaCommandArg("delete", optional=False),
        ],
        info=[
            "Directs Icinga to process all external commands that are found "
            "in the file specified by the <file_name> argument. If the <delete> "
            "option is non-zero, the file will be deleted once it has been "
            "processes. If the <delete> option is set to zero, the file is "
            "left untouched.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    process_host_check_result = IcingaCommand(
        name="PROCESS_HOST_CHECK_RESULT",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("status_code", optional=False),
            IcingaCommandArg("plugin_output", optional=False),
        ],
        info=[
            "This is used to submit a passive check result for a particular "
            "host. The \"status_code\" indicates the state of the host check "
            "and should be one of the following: 0=UP, 1=DOWN, 2=UNREACHABLE. "
            "The \"plugin_output\" argument contains the text returned from "
            "the host check, along with optional performance data.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    process_service_check_result = IcingaCommand(
        name="PROCESS_SERVICE_CHECK_RESULT",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("return_code", optional=False),
            IcingaCommandArg("plugin_output", optional=False),
        ],
        info=[
            "This is used to submit a passive check result for a particular "
            "service. The \"return_code\" field should be one of the following: "
            "0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN. The \"plugin_output\" field "
            "contains text output from the service check, along with optional "
            "performance data.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    read_state_information = IcingaCommand(
        name="READ_STATE_INFORMATION",
        args=[],
        info=[
            "Causes Icinga to load all current monitoring status information "
            "from the state retention file. Normally, state retention information "
            "is loaded when the Icinga process starts up and before it starts "
            "monitoring. WARNING: This command will cause Icinga to discard "
            "all current monitoring status information and use the information "
            "stored in state retention file! Use with care.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    remove_host_acknowledgement = IcingaCommand(
        name="REMOVE_HOST_ACKNOWLEDGEMENT",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "This removes the problem acknowledgement for a particular host. "
            "Once the acknowledgement has been removed, notifications can "
            "once again be sent out for the given host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    remove_svc_acknowledgement = IcingaCommand(
        name="REMOVE_SVC_ACKNOWLEDGEMENT",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "This removes the problem acknowledgement for a particular service. "
            "Once the acknowledgement has been removed, notifications can "
            "once again be sent out for the given service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    restart_process = IcingaCommand(
        name="RESTART_PROCESS",
        args=[],
        info=[
            "Restarts the Icinga process.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    save_state_information = IcingaCommand(
        name="SAVE_STATE_INFORMATION",
        args=[],
        info=[
            "Causes Icinga to save all current monitoring status information "
            "to the state retention file. Normally, state retention information "
            "is saved before the Icinga process shuts down and (potentially) "
            "at regularly scheduled intervals. This command allows you to "
            "force Icinga to save this information to the state retention "
            "file immediately. This does not affect the current status information "
            "in the Icinga process.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_and_propagate_host_downtime = IcingaCommand(
        name="SCHEDULE_AND_PROPAGATE_HOST_DOWNTIME",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for a specified host and all of its children "
            "(hosts). If the \"fixed\" argument is set to one (1), downtime "
            "will start and end at the times specified by the \"start\" and "
            "\"end\" arguments. Otherwise, downtime will begin between the \"start\" "
            "and \"end\" times and last for \"duration\" seconds. The \"start\" "
            "and \"end\" arguments are specified in time_t format (seconds since "
            "the UNIX epoch). The specified (parent) host downtime can be "
            "triggered by another downtime entry if the \"trigger_id\" is set "
            "to the ID of another scheduled downtime entry. Set the \"trigger_id\" "
            "argument to zero (0) if the downtime for the specified (parent) "
            "host should not be triggered by another downtime entry.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_and_propagate_triggered_host_downtime = IcingaCommand(
        name="SCHEDULE_AND_PROPAGATE_TRIGGERED_HOST_DOWNTIME",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for a specified host and all of its children "
            "(hosts). If the \"fixed\" argument is set to one (1), downtime "
            "will start and end at the times specified by the \"start\" and "
            "\"end\" arguments. Otherwise, downtime will begin between the \"start\" "
            "and \"end\" times and last for \"duration\" seconds. The \"start\" "
            "and \"end\" arguments are specified in time_t format (seconds since "
            "the UNIX epoch). Downtime for child hosts are all set to be triggered "
            "by the downtime for the specified (parent) host. The specified "
            "(parent) host downtime can be triggered by another downtime entry "
            "if the \"trigger_id\" is set to the ID of another scheduled downtime "
            "entry. Set the \"trigger_id\" argument to zero (0) if the downtime "
            "for the specified (parent) host should not be triggered by another "
            "downtime entry.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_forced_host_check = IcingaCommand(
        name="SCHEDULE_FORCED_HOST_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_time", optional=False),
        ],
        info=[
            "Schedules a forced active check of a particular host at \"check_time\". "
            "The \"check_time\" argument is specified in time_t format (seconds "
            "since the UNIX epoch). Forced checks are performed regardless "
            "of what time it is (e.g. timeperiod restrictions are ignored) "
            "and whether or not active checks are enabled on a host-specific "
            "or program-wide basis.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_forced_host_svc_checks = IcingaCommand(
        name="SCHEDULE_FORCED_HOST_SVC_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_time", optional=False),
        ],
        info=[
            "Schedules a forced active check of all services associated with "
            "a particular host at \"check_time\". The \"check_time\" argument "
            "is specified in time_t format (seconds since the UNIX epoch). "
            "Forced checks are performed regardless of what time it is (e.g. "
            "timeperiod restrictions are ignored) and whether or not active "
            "checks are enabled on a service-specific or program-wide basis.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_forced_svc_check = IcingaCommand(
        name="SCHEDULE_FORCED_SVC_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_time", optional=False),
        ],
        info=[
            "Schedules a forced active check of a particular service at \"check_time\". "
            "The \"check_time\" argument is specified in time_t format (seconds "
            "since the UNIX epoch). Forced checks are performed regardless "
            "of what time it is (e.g. timeperiod restrictions are ignored) "
            "and whether or not active checks are enabled on a service-specific "
            "or program-wide basis.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_hostgroup_host_downtime = IcingaCommand(
        name="SCHEDULE_HOSTGROUP_HOST_DOWNTIME",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for all hosts in a specified hostgroup. If "
            "the \"fixed\" argument is set to one (1), downtime will start and "
            "end at the times specified by the \"start\" and \"end\" arguments. "
            "Otherwise, downtime will begin between the \"start\" and \"end\" "
            "times and last for \"duration\" seconds. The \"start\" and \"end\" "
            "arguments are specified in time_t format (seconds since the UNIX "
            "epoch). The host downtime entries can be triggered by another "
            "downtime entry if the \"trigger_id\" is set to the ID of another "
            "scheduled downtime entry. Set the \"trigger_id\" argument to zero "
            "(0) if the downtime for the hosts should not be triggered by "
            "another downtime entry.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_hostgroup_svc_downtime = IcingaCommand(
        name="SCHEDULE_HOSTGROUP_SVC_DOWNTIME",
        args=[
            IcingaCommandArg("hostgroup_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for all services associated with hosts in "
            "a specified hostgroup. If the \"fixed\" argument is set to one "
            "(1), downtime will start and end at the times specified by the "
            "\"start\" and \"end\" arguments. Otherwise, downtime will begin between "
            "the \"start\" and \"end\" times and last for \"duration\" seconds. "
            "The \"start\" and \"end\" arguments are specified in time_t format "
            "(seconds since the UNIX epoch). The service downtime entries "
            "can be triggered by another downtime entry if the \"trigger_id\" "
            "is set to the ID of another scheduled downtime entry. Set the "
            "\"trigger_id\" argument to zero (0) if the downtime for the services "
            "should not be triggered by another downtime entry.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=True,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_host_check = IcingaCommand(
        name="SCHEDULE_HOST_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_time", optional=False),
        ],
        info=[
            "Schedules the next active check of a particular host at \"check_time\". "
            "The \"check_time\" argument is specified in time_t format (seconds "
            "since the UNIX epoch). Note that the host may not actually be "
            "checked at the time you specify. This could occur for a number "
            "of reasons: active checks are disabled on a program-wide or host-specific "
            "basis, the host is already scheduled to be checked at an earlier "
            "time, etc. If you want to force the host check to occur at the "
            "time you specify, look at the SCHEDULE_FORCED_HOST_CHECK command.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_host_downtime = IcingaCommand(
        name="SCHEDULE_HOST_DOWNTIME",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for a specified host. If the \"fixed\" argument "
            "is set to one (1), downtime will start and end at the times specified "
            "by the \"start\" and \"end\" arguments. Otherwise, downtime will "
            "begin between the \"start\" and \"end\" times and last for \"duration\" "
            "seconds. The \"start\" and \"end\" arguments are specified in time_t "
            "format (seconds since the UNIX epoch). The specified host downtime "
            "can be triggered by another downtime entry if the \"trigger_id\" "
            "is set to the ID of another scheduled downtime entry. Set the "
            "\"trigger_id\" argument to zero (0) if the downtime for the specified "
            "host should not be triggered by another downtime entry.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_host_svc_checks = IcingaCommand(
        name="SCHEDULE_HOST_SVC_CHECKS",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("check_time", optional=False),
        ],
        info=[
            "Schedules the next active check of all services on a particular "
            "host at \"check_time\". The \"check_time\" argument is specified "
            "in time_t format (seconds since the UNIX epoch). Note that the "
            "services may not actually be checked at the time you specify. "
            "This could occur for a number of reasons: active checks are disabled "
            "on a program-wide or service-specific basis, the services are "
            "already scheduled to be checked at an earlier time, etc. If you "
            "want to force the service checks to occur at the time you specify, "
            "look at the SCHEDULE_FORCED_HOST_SVC_CHECKS command.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_host_svc_downtime = IcingaCommand(
        name="SCHEDULE_HOST_SVC_DOWNTIME",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for all services associated with a particular "
            "host. If the \"fixed\" argument is set to one (1), downtime will "
            "start and end at the times specified by the \"start\" and \"end\" "
            "arguments. Otherwise, downtime will begin between the \"start\" "
            "and \"end\" times and last for \"duration\" seconds. The \"start\" "
            "and \"end\" arguments are specified in time_t format (seconds since "
            "the UNIX epoch). The service downtime entries can be triggered "
            "by another downtime entry if the \"trigger_id\" is set to the ID "
            "of another scheduled downtime entry. Set the \"trigger_id\" argument "
            "to zero (0) if the downtime for the services should not be triggered "
            "by another downtime entry.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_servicegroup_host_downtime = IcingaCommand(
        name="SCHEDULE_SERVICEGROUP_HOST_DOWNTIME",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for all hosts that have services in a specified "
            "servicegroup. If the \"fixed\" argument is set to one (1), downtime "
            "will start and end at the times specified by the \"start\" and "
            "\"end\" arguments. Otherwise, downtime will begin between the \"start\" "
            "and \"end\" times and last for \"duration\" seconds. The \"start\" "
            "and \"end\" arguments are specified in time_t format (seconds since "
            "the UNIX epoch). The host downtime entries can be triggered by "
            "another downtime entry if the \"trigger_id\" is set to the ID of "
            "another scheduled downtime entry. Set the \"trigger_id\" argument "
            "to zero (0) if the downtime for the hosts should not be triggered "
            "by another downtime entry.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_servicegroup_svc_downtime = IcingaCommand(
        name="SCHEDULE_SERVICEGROUP_SVC_DOWNTIME",
        args=[
            IcingaCommandArg("servicegroup_name", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for all services in a specified servicegroup. "
            "If the \"fixed\" argument is set to one (1), downtime will start "
            "and end at the times specified by the \"start\" and \"end\" arguments. "
            "Otherwise, downtime will begin between the \"start\" and \"end\" "
            "times and last for \"duration\" seconds. The \"start\" and \"end\" "
            "arguments are specified in time_t format (seconds since the UNIX "
            "epoch). The service downtime entries can be triggered by another "
            "downtime entry if the \"trigger_id\" is set to the ID of another "
            "scheduled downtime entry. Set the \"trigger_id\" argument to zero "
            "(0) if the downtime for the services should not be triggered "
            "by another downtime entry.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=True,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_svc_check = IcingaCommand(
        name="SCHEDULE_SVC_CHECK",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("check_time", optional=False),
        ],
        info=[
            "Schedules the next active check of a specified service at \"check_time\". "
            "The \"check_time\" argument is specified in time_t format (seconds "
            "since the UNIX epoch). Note that the service may not actually "
            "be checked at the time you specify. This could occur for a number "
            "of reasons: active checks are disabled on a program-wide or service-specific "
            "basis, the service is already scheduled to be checked at an earlier "
            "time, etc. If you want to force the service check to occur at "
            "the time you specify, look at the SCHEDULE_FORCED_SVC_CHECK command.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    schedule_svc_downtime = IcingaCommand(
        name="SCHEDULE_SVC_DOWNTIME",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("start_time", optional=False),
            IcingaCommandArg("end_time", optional=False),
            IcingaCommandArg("fixed", optional=False),
            IcingaCommandArg("trigger_id", optional=False),
            IcingaCommandArg("duration", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Schedules downtime for a specified service. If the \"fixed\" argument "
            "is set to one (1), downtime will start and end at the times specified "
            "by the \"start\" and \"end\" arguments. Otherwise, downtime will "
            "begin between the \"start\" and \"end\" times and last for \"duration\" "
            "seconds. The \"start\" and \"end\" arguments are specified in time_t "
            "format (seconds since the UNIX epoch). The specified service "
            "downtime can be triggered by another downtime entry if the \"trigger_id\" "
            "is set to the ID of another scheduled downtime entry. Set the "
            "\"trigger_id\" argument to zero (0) if the downtime for the specified "
            "service should not be triggered by another downtime entry.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    send_custom_host_notification = IcingaCommand(
        name="SEND_CUSTOM_HOST_NOTIFICATION",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("options", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Allows you to send a custom host notification. Very useful in "
            "dire situations, emergencies or to communicate with all admins "
            "that are responsible for a particular host. When the host notification "
            "is sent out, the $NOTIFICATIONTYPE$ macro will be set to \"CUSTOM\". "
            "The <options> field is a logical OR of the following integer "
            "values that affect aspects of the notification that are sent "
            "out: 0 = No option (default), 1 = Broadcast (send notification "
            "to all normal and all escalated contacts for the host), 2 = Forced "
            "(notification is sent out regardless of current time, whether "
            "or not notifications are enabled, etc.), 4 = Increment current "
            "notification # for the host (this is not done by default for "
            "custom notifications). The contents of the comment field is available "
            "in notification commands using the $NOTIFICATIONCOMMENT$ macro.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    send_custom_svc_notification = IcingaCommand(
        name="SEND_CUSTOM_SVC_NOTIFICATION",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("options", optional=False),
            IcingaCommandArg("author", optional=False),
            IcingaCommandArg("comment", optional=False),
        ],
        info=[
            "Allows you to send a custom service notification. Very useful "
            "in dire situations, emergencies or to communicate with all admins "
            "that are responsible for a particular service. When the service "
            "notification is sent out, the $NOTIFICATIONTYPE$ macro will be "
            "set to \"CUSTOM\". The <options> field is a logical OR of the following "
            "integer values that affect aspects of the notification that are "
            "sent out: 0 = No option (default), 1 = Broadcast (send notification "
            "to all normal and all escalated contacts for the service), 2 "
            "= Forced (notification is sent out regardless of current time, "
            "whether or not notifications are enabled, etc.), 4 = Increment "
            "current notification # for the service(this is not done by default "
            "for custom notifications). The contents of the comment field "
            "is available in notification commands using the $NOTIFICATIONCOMMENT$ "
            "macro.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    set_host_notification_number = IcingaCommand(
        name="SET_HOST_NOTIFICATION_NUMBER",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("notification_number", optional=False),
        ],
        info=[
            "Sets the current notification number for a particular host. A "
            "value of 0 indicates that no notification has yet been sent for "
            "the current host problem. Useful for forcing an escalation (based "
            "on notification number) or replicating notification information "
            "in redundant monitoring environments. Notification numbers greater "
            "than zero have no noticeable affect on the notification process "
            "if the host is currently in an UP state.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    set_svc_notification_number = IcingaCommand(
        name="SET_SVC_NOTIFICATION_NUMBER",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
            IcingaCommandArg("notification_number", optional=False),
        ],
        info=[
            "Sets the current notification number for a particular service. "
            "A value of 0 indicates that no notification has yet been sent "
            "for the current service problem. Useful for forcing an escalation "
            "(based on notification number) or replicating notification information "
            "in redundant monitoring environments. Notification numbers greater "
            "than zero have no noticeable affect on the notification process "
            "if the service is currently in an OK state.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    shutdown_process = IcingaCommand(
        name="SHUTDOWN_PROCESS",
        args=[],
        info=[
            "Shuts down the Icinga process.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_accepting_passive_host_checks = IcingaCommand(
        name="START_ACCEPTING_PASSIVE_HOST_CHECKS",
        args=[],
        info=[
            "Enables acceptance and processing of passive host checks on a "
            "program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_accepting_passive_svc_checks = IcingaCommand(
        name="START_ACCEPTING_PASSIVE_SVC_CHECKS",
        args=[],
        info=[
            "Enables passive service checks on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_executing_host_checks = IcingaCommand(
        name="START_EXECUTING_HOST_CHECKS",
        args=[],
        info=[
            "Enables active host checks on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_executing_svc_checks = IcingaCommand(
        name="START_EXECUTING_SVC_CHECKS",
        args=[],
        info=[
            "Enables active checks of services on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_obsessing_over_host = IcingaCommand(
        name="START_OBSESSING_OVER_HOST",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Enables processing of host checks via the OCHP command for the "
            "specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_obsessing_over_host_checks = IcingaCommand(
        name="START_OBSESSING_OVER_HOST_CHECKS",
        args=[],
        info=[
            "Enables processing of host checks via the OCHP command on a program-wide "
            "basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_obsessing_over_svc = IcingaCommand(
        name="START_OBSESSING_OVER_SVC",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Enables processing of service checks via the OCSP command for "
            "the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    start_obsessing_over_svc_checks = IcingaCommand(
        name="START_OBSESSING_OVER_SVC_CHECKS",
        args=[],
        info=[
            "Enables processing of service checks via the OCSP command on "
            "a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_accepting_passive_host_checks = IcingaCommand(
        name="STOP_ACCEPTING_PASSIVE_HOST_CHECKS",
        args=[],
        info=[
            "Disables acceptance and processing of passive host checks on "
            "a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_accepting_passive_svc_checks = IcingaCommand(
        name="STOP_ACCEPTING_PASSIVE_SVC_CHECKS",
        args=[],
        info=[
            "Disables passive service checks on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_executing_host_checks = IcingaCommand(
        name="STOP_EXECUTING_HOST_CHECKS",
        args=[],
        info=[
            "Disables active host checks on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_executing_svc_checks = IcingaCommand(
        name="STOP_EXECUTING_SVC_CHECKS",
        args=[],
        info=[
            "Disables active checks of services on a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_obsessing_over_host = IcingaCommand(
        name="STOP_OBSESSING_OVER_HOST",
        args=[
            IcingaCommandArg("host_name", optional=False),
        ],
        info=[
            "Disables processing of host checks via the OCHP command for the "
            "specified host.",
        ],
        for_host=True,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_obsessing_over_host_checks = IcingaCommand(
        name="STOP_OBSESSING_OVER_HOST_CHECKS",
        args=[],
        info=[
            "Disables processing of host checks via the OCHP command on a "
            "program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_obsessing_over_svc = IcingaCommand(
        name="STOP_OBSESSING_OVER_SVC",
        args=[
            IcingaCommandArg("host_name", optional=False),
            IcingaCommandArg("service_description", optional=False),
        ],
        info=[
            "Disables processing of service checks via the OCSP command for "
            "the specified service.",
        ],
        for_host=True,
        for_service=True,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
    stop_obsessing_over_svc_checks = IcingaCommand(
        name="STOP_OBSESSING_OVER_SVC_CHECKS",
        args=[],
        info=[
            "Disables processing of service checks via the OCSP command on "
            "a program-wide basis.",
        ],
        for_host=False,
        for_service=False,
        for_hostgroup=False,
        for_servicegroup=False,
        for_contact=False,
        for_contactgroup=False,
    )
