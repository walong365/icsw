# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
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

import os

from django.db.models import Q

from initat.cluster.backbone.models import device_group, mon_period, \
    mon_contact, mon_contactgroup, category_tree, mon_notification, \
    host_check_command, MonCheckCommandSystemNames, device_variable, \
    DBStructuredMonBaseConfig
from initat.constants import CLUSTER_DIR
from initat.tools import logging_tools
from .global_config import global_config
from .mon_config_containers import MonFileContainer
from ..base_config.mon_base_config import StructuredMonBaseConfig
from ..special_commands.instances import dynamic_checks

__all__ = [
    "MonAllHostDependencies",
    "MonAllTimePeriods",
    "MonAllServiceGroups",
    "MonAllCommands",
    "MonAllContacts",
    "MonAllContactGroups",
    "MonAllHostGroups",
]

CLUSTER_BIN = os.path.join(CLUSTER_DIR, "bin")
CLUSTER_SBIN = os.path.join(CLUSTER_DIR, "sbin")


class MonAllHostDependencies(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "hostdependency")


class MonAllTimePeriods(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "timeperiod")
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self._add_time_periods_from_db()

    def _add_time_periods_from_db(self):
        for cur_per in mon_period.objects.all():
            nag_conf = StructuredMonBaseConfig(
                "timeperiod",
                cur_per.name,
                timeperiod_name=cur_per.name,
                alias=cur_per.alias.strip() if cur_per.alias.strip() else []
            )
            for short_s, long_s in [
                ("mon", "monday"),
                ("tue", "tuesday"),
                ("wed", "wednesday"),
                ("thu", "thursday"),
                ("fri", "friday"),
                ("sat", "saturday"),
                ("sun", "sunday"),
            ]:
                nag_conf[long_s] = getattr(cur_per, "{}_range".format(short_s))
            self[cur_per.pk] = nag_conf
            self.add_object(nag_conf)


class MonAllServiceGroups(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "servicegroup")
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        # dict : which host has which service_group defined
        self.cat_tree = category_tree()
        self._add_servicegroups_from_db()

    def _add_servicegroups_from_db(self):
        self.__host_srv_lut = {}
        self.clear()
        for cat_pk in self.cat_tree.get_sorted_pks():
            cur_cat = self.cat_tree[cat_pk]
            nag_conf = StructuredMonBaseConfig(
                "servicegroup",
                cur_cat.full_name,
                servicegroup_name=cur_cat.full_name,
                alias="{} group".format(cur_cat.full_name))
            self.__host_srv_lut[cur_cat.full_name] = set()
            self[cur_cat.pk] = nag_conf
            self.add_object(nag_conf)

    def clear_host(self, host_name):
        for _key, value in self.__host_srv_lut.items():
            if host_name in value:
                value.remove(host_name)

    def add_host(self, host_name, srv_groups):
        for srv_group in srv_groups:
            self.__host_srv_lut[srv_group].add(host_name)

    @property
    def object_list(self):
        return [obj for obj in self._obj_list if self.__host_srv_lut[obj.name]]


class MonAllCommands(MonFileContainer):
    def __init__(self, gen_conf: object, logging: bool, create: bool):
        self.__logging = logging
        self.__create = create
        MonFileContainer.__init__(self, "command")
        self.__log_counter = 0
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.clear()
        self._add_notify_commands()
        self._add_commands_from_db(gen_conf)
        self.__log_counter += 1

    def ignore_content(self, in_dict):
        # ignore commands with empty command line (== meta commands)
        return (
            "".join(in_dict.get("command_line", [""]))
        ).strip() == ""

    def _expand_str(self, in_str):
        for key, value in self._str_repl_dict.items():
            in_str = in_str.replace(key, value)
        return in_str

    def _add_notify_commands(self):
        # get cluster_name
        cluster_name = device_variable.objects.get_cluster_name()
        md_vers = global_config["MD_VERSION_STRING"]
        md_type = global_config["MD_TYPE"]
        send_mail_prog = os.path.join(
            CLUSTER_SBIN,
            "icsw --nodb user --mode mail"
        )
        send_sms_prog = os.path.join(
            CLUSTER_DIR,
            "icinga",
            "bin",
            "sendsms",
        )
        from_addr = "{}@{}".format(
            global_config["MD_TYPE"],
            global_config["FROM_ADDR"]
        )

        self._str_repl_dict = {
            "$ICSW_MONITOR_INFO$": "{} {}".format(md_type, md_vers),
            "$ICSW_CLUSTER_NAME$": "{}".format(cluster_name),
        }

        self.add_object(
            StructuredMonBaseConfig(
                "command",
                MonCheckCommandSystemNames.dummy_notify.value,
                command_name=MonCheckCommandSystemNames.dummy_notify.value,
                command_line="/usr/bin/true",
            )
        )
        _rewrite_dict = {
            "$INIT_MONITOR_INFO$": "$ICSW_MONITOR_INFO$",
            "$INIT_CLUSTER_NAME$": "$ICSW_CLUSTER_NAME$",
        }
        for cur_not in mon_notification.objects.filter(Q(enabled=True)):
            _updated = False
            for attr in ["subject", "content"]:
                _old = getattr(cur_not, attr)
                _new = _old
                for key, value in _rewrite_dict.items():
                    _new = _new.replace(key, value)
                if _new != _old:
                    setattr(cur_not, attr, _new)
                    _updated = True
            if _updated:
                self.log("rewrote notification")
                cur_not.save()
            if cur_not.channel == "mail":
                command_line = r"{} -f '{}' -s '{}' -t $CONTACTEMAIL$ --message '{}'".format(
                    send_mail_prog,
                    from_addr,
                    self._expand_str(cur_not.subject),
                    self._expand_str(cur_not.content),
                )
            else:
                command_line = r"{} $CONTACTPAGER$ '{}'".format(
                    send_sms_prog,
                    self._expand_str(cur_not.content),
                )
            _cn_l_name = cur_not.name.replace("-", "_")
            try:
                _cn_name = MonCheckCommandSystemNames[_cn_l_name].value
            except KeyError:
                self.log("Unknown notification command '{}', ignoring".format(_cn_l_name), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.add_object(
                    StructuredMonBaseConfig(
                        "command",
                        _cn_name,
                        command_name=_cn_name,
                        command_line=command_line.replace("\n", "\\n"),
                    )
                )

    def _add_commands_from_db(self, gen_conf):
        # to log or not to log ...
        if self.__logging:
            log_com = gen_conf.log
        else:
            log_com = None
        for hc_com in host_check_command.objects.all():
            cur_nc = StructuredMonBaseConfig(
                "command",
                hc_com.name,
                command_name=hc_com.name,
                command_line=hc_com.command_line,
            )
            self.add_object(cur_nc)
            # simple mon_config, we do not add this to the command dict
            # self.__dict[cur_nc["command_name"]] = cur_nc

        def get_special_db_inst(inst: object, name: str) -> object:
            # inst: Object with a Meta (with an uuid entry)
            # name: name to search for in case no uuid match was found
            try:
                _db_inst = DBStructuredMonBaseConfig.objects.get(
                    Q(uuid=inst.Meta.uuid)
                )
            except DBStructuredMonBaseConfig.DoesNotExist:
                _db_inst = DBStructuredMonBaseConfig.objects.get(
                    Q(name=name) &
                    Q(is_special_command=True)
                )
                _db_inst.uuid = inst.Meta.uuid
                _db_inst.save(update_fields=["uuid"])
            _update_fields = []
            if not _db_inst.command_line:
                _db_inst.command_line = "/bin/true"
                _update_fields.append("command_line")
            if _db_inst.system_command:
                _db_inst.system_command = False
                _update_fields.append("system_command")
            if _update_fields:
                _db_inst.save(update_fields=_update_fields)
            return _db_inst

        # check commands
        # special commands

        # _s_names = DBStructuredMonBaseConfig.objects.filter(Q(is_special_command=True)).values_list("name", flat=True)
        # print("*", _s_names)
        # ensure mon_check_commands for all special commands
        for name, mccs_inst in dynamic_checks.valid_class_dict(gen_conf.log).items():
            get_special_db_inst(mccs_inst, mccs_inst.Meta.database_name)
            if mccs_inst.Meta.meta:
                # handle subcommands
                for sub_com in mccs_inst.get_commands():
                    get_special_db_inst(sub_com, sub_com.Meta.name)
        # check all commands starting with "special" which have the system_command flag set
        stale_list = DBStructuredMonBaseConfig.objects.filter(
            Q(system_command=True) & Q(name__istartswith="special_") & Q(is_special_command=False)
        )
        for entry in stale_list:
            # delete entries
            # - without config
            # - no associated devices
            if not entry.config_rel.all().count() and not entry.devices.all().count():
                log_com(
                    "removing stale entry '{}'".format(str(entry)),
                    logging_tools.LOG_LEVEL_ERROR
                )
                entry.delete()

        check_coms = list(
            DBStructuredMonBaseConfig.objects.filter(
                Q(system_command=False)
            ).prefetch_related(
                "categories",
                "devices",
                "config_rel",
            ).select_related(
                "mon_service_templ",
                "event_handler"
            ).order_by("name")
        )
        enable_perfd = global_config["ENABLE_COLLECTD"]
        if enable_perfd and gen_conf.master:
            check_coms.extend(
                [
                    DBStructuredMonBaseConfig.get_system_check_command(
                        name=MonCheckCommandSystemNames.process_service_perfdata_file.value,
                        command_line="{} {}/service-perfdata".format(
                            os.path.join(CLUSTER_SBIN, "send_collectd_zmq"),
                            gen_conf.var_dir,
                        ),
                        description="Process service performance data",
                        create=self.__create,
                    ),
                    DBStructuredMonBaseConfig.get_system_check_command(
                        name=MonCheckCommandSystemNames.process_host_perfdata_file.value,
                        command_line="{} {}/host-perfdata".format(
                            os.path.join(CLUSTER_SBIN, "send_collectd_zmq"),
                            gen_conf.var_dir
                        ),
                        description="Process host performance data",
                        create=self.__create,
                    ),
                ]
            )

        check_coms.extend(
            [
                DBStructuredMonBaseConfig.get_system_check_command(
                    name=MonCheckCommandSystemNames.ochp_command.value,
                    command_line="{} ochp-event \"$HOSTNAME$\" \"$HOSTSTATE$\" \"{}\"".format(
                        os.path.join(CLUSTER_SBIN, "csendsyncerzmq"),
                        "$HOSTOUTPUT$|$HOSTPERFDATA$" if enable_perfd else "$HOSTOUTPUT$"
                    ),
                    description="OCHP Command",
                    create=self.__create,
                ),
                DBStructuredMonBaseConfig.get_system_check_command(
                    name=MonCheckCommandSystemNames.ocsp_command.value,
                    command_line="{} ocsp-event \"$HOSTNAME$\" \"$SERVICEDESC$\" \"$SERVICESTATE$\" \"{}\" ".format(
                        os.path.join(CLUSTER_SBIN, "csendsyncerzmq"),
                        "$SERVICEOUTPUT$|$SERVICEPERFDATA$" if enable_perfd else "$SERVICEOUTPUT$"
                    ),
                    description="OCSP Command",
                    create=self.__create,
                ),
                DBStructuredMonBaseConfig.get_system_check_command(
                    name=MonCheckCommandSystemNames.check_service_cluster.value,
                    command_line="{} --service -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"".format(
                        os.path.join(CLUSTER_BIN, "check_icinga_cluster.py"),
                    ),
                    description="Check Service Cluster",
                    create=self.__create,
                ),
                DBStructuredMonBaseConfig.get_system_check_command(
                    name=MonCheckCommandSystemNames.check_host_cluster.value,
                    command_line="{} --host -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"".format(
                        os.path.join(CLUSTER_BIN, "check_icinga_cluster.py"),
                    ),
                    description="Check Host Cluster",
                    create=self.__create,
                ),
            ]
        )
        safe_descr = global_config["SAFE_NAMES"]
        for ngc in check_coms:
            # print("*", ngc, type(ngc))
            ngc.generate_md_com_line(log_com, safe_descr)
            self.add_object(ngc)
            self[ngc.unique_name] = ngc
            self[ngc.idx] = ngc


class MonAllContacts(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "contact")
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.clear()
        self._add_contacts_from_db(gen_conf)

    def _add_contacts_from_db(self, gen_conf):
        all_nots = mon_notification.objects.all()
        for contact in mon_contact.objects.filter(
            Q(user__active=True) &
            Q(user__group__active=True)
        ).prefetch_related(
            "notifications"
        ).select_related(
            "user"
        ):
            full_name = (
                "{} {}".format(
                    contact.user.first_name,
                    contact.user.last_name
                )
            ).strip().replace(" ", "_")
            if not full_name:
                full_name = contact.user.login
            not_h_list = [
                entry for entry in all_nots if entry.channel == "mail" and entry.not_type == "host" and entry.enabled
            ]
            # not_s_list = list(contact.notifications.filter(Q(channel="mail") & Q(not_type="service") & Q(enabled=True)))
            not_s_list = [
                entry for entry in all_nots if entry.channel == "mail" and entry.not_type == "service" and entry.enabled
            ]
            not_pks = [_not.pk for _not in contact.notifications.all()]
            if len(contact.user.pager) > 5:
                # check for pager number
                not_h_list.extend(
                    [
                        entry for entry in all_nots if entry.channel == "sms" and entry.not_type == "host" and entry.enabled
                    ]
                )
                not_s_list.extend(
                    [
                        entry for entry in all_nots if entry.channel == "sms" and entry.not_type == "service" and entry.enabled
                    ]
                )
            # filter
            not_h_list = [entry for entry in not_h_list if entry.pk in not_pks]
            not_s_list = [entry for entry in not_s_list if entry.pk in not_pks]
            if contact.mon_alias:
                alias = contact.mon_alias
            elif contact.user.comment:
                alias = contact.user.comment
            else:
                alias = full_name
            nag_conf = StructuredMonBaseConfig(
                "contact",
                full_name,
                contact_name=contact.user.login,
                host_notification_period=gen_conf["timeperiod"][contact.hnperiod_id].name,
                service_notification_period=gen_conf["timeperiod"][contact.snperiod_id].name,
                alias=alias.strip() if alias.strip() else [],
            )
            if not_h_list:
                nag_conf["host_notification_commands"] = [entry.name for entry in not_h_list]
            else:
                nag_conf["host_notification_commands"] = "dummy-notify"
            if not_s_list:
                nag_conf["service_notification_commands"] = [entry.name for entry in not_s_list]
            else:
                nag_conf["service_notification_commands"] = "dummy-notify"
            for targ_opt, pairs in [
                (
                    "host_notification_options", [
                        ("hnrecovery", "r"), ("hndown", "d"), ("hnunreachable", "u"), ("hflapping", "f"), ("hplanned_downtime", "s")
                    ]
                ),
                (
                    "service_notification_options", [
                        ("snrecovery", "r"), ("sncritical", "c"), ("snwarning", "w"), ("snunknown", "u"), ("sflapping", "f"), ("splanned_downtime", "s")
                    ]
                )
            ]:
                act_a = []
                for long_s, short_s in pairs:
                    if getattr(contact, long_s):
                        act_a.append(short_s)
                if not act_a:
                    act_a = ["n"]
                nag_conf[targ_opt] = act_a
            u_mail = contact.user.email or "root@localhost"
            nag_conf["email"] = u_mail
            nag_conf["pager"] = contact.user.pager or "----"
            self.add_object(nag_conf)
            self[contact.pk] = nag_conf


class MonAllContactGroups(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "contactgroup")
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.clear()
        self._add_contact_groups_from_db(gen_conf)

    def _add_contact_groups_from_db(self, gen_conf):
        # none group
        self.add_object(
            StructuredMonBaseConfig(
                "contactgroup",
                global_config["NONE_CONTACT_GROUP"],
                contactgroup_name=global_config["NONE_CONTACT_GROUP"],
                alias="None group"
            )
        )
        for cg_group in mon_contactgroup.objects.all().prefetch_related(
            "members"
        ):
            nag_conf = StructuredMonBaseConfig(
                "contactgroup",
                cg_group.name,
                contactgroup_name=cg_group.name,
                alias=cg_group.alias.strip() if cg_group.alias.strip() else []
            )
            self[cg_group.pk] = nag_conf
            self.add_object(nag_conf)
            for member in cg_group.members.all():
                try:
                    nag_conf["members"] = gen_conf["contact"][member.pk]["contact_name"]
                except:
                    pass


class MonAllHostGroups(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "hostgroup")
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.clear()
        self.cat_tree = category_tree()
        self._add_host_groups_from_db(gen_conf)

    def _add_host_groups_from_db(self, gen_conf):
        if "device" in gen_conf:
            host_pks = gen_conf["device"].host_pks
            hostg_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(device_group__pk__in=host_pks)
            host_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(pk__in=host_pks)
            if host_pks:
                # hostgroups by devicegroups
                # distinct is important here
                for h_group in device_group.objects.filter(hostg_filter).prefetch_related("device_group").distinct():
                    nag_conf = StructuredMonBaseConfig(
                        "hostgroup",
                        h_group.name,
                        hostgroup_name=h_group.name,
                        alias=h_group.description or h_group.name,
                        members=[]
                    )
                    self[h_group.pk] = nag_conf
                    self.add_object(nag_conf)
                    nag_conf["members"] = [
                        cur_dev.full_name for cur_dev in h_group.device_group.filter(Q(pk__in=host_pks)).select_related("domain_tree_node")
                    ]
                # hostgroups by categories
                for cat_pk in self.cat_tree.get_sorted_pks():
                    cur_cat = self.cat_tree[cat_pk]
                    nag_conf = StructuredMonBaseConfig(
                        "hostgroup",
                        cur_cat.full_name,
                        hostgroup_name=cur_cat.full_name,
                        alias=cur_cat.comment or cur_cat.full_name,
                        members=[]
                    )
                    nag_conf["members"] = [
                        cur_dev.full_name for cur_dev in cur_cat.device_set.filter(host_filter).select_related("domain_tree_node")
                    ]
                    if nag_conf["members"]:
                        self.add_object(nag_conf)
            else:
                self.log(
                    "empty SQL-Str for in _add_host_groups_from_db()",
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            self.log(
                "no host-dict found in gen_dict",
                logging_tools.LOG_LEVEL_WARN
            )
