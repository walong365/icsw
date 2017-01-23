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

from initat.cluster.backbone.models import device, device_group, mon_check_command, mon_period, \
    mon_contact, mon_contactgroup, category_tree, TOP_MONITORING_CATEGORY, mon_notification, \
    host_check_command, mon_check_command_special
from initat.constants import CLUSTER_DIR
from initat.md_config_server.config.check_command import CheckCommand
from initat.md_config_server.config.mon_base_config import StructuredMonBaseConfig, MonUniqueList, \
    build_safe_name
from initat.md_config_server.config.mon_config_containers import MonFileContainer
from initat.tools import cluster_location, logging_tools
from .global_config import global_config

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
    def __init__(self, gen_conf, logging):
        self.__logging = logging
        MonFileContainer.__init__(self, "command")
        self.__log_counter = 0
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        CheckCommand.gen_conf = gen_conf
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
        try:
            cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            cluster_name = "N/A"
        else:
            # cluster_name has to be set, otherwise something went seriously wrong while setting up the cluster
            cluster_name = cluster_location.db_device_variable(
                cdg,
                "CLUSTER_NAME",
                description="name of the cluster"
            ).get_value()
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
                "dummy-notify",
                command_name="dummy-notify",
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
            self.add_object(
                StructuredMonBaseConfig(
                    "command",
                    cur_not.name,
                    command_name=cur_not.name,
                    command_line=command_line.replace("\n", "\\n"),
                )
            )

    def _add_commands_from_db(self, gen_conf):
        # set of names of configs which point to a full check_config
        cc_command_names = MonUniqueList()
        # set of all names
        command_names = MonUniqueList()
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
            command_names.add(hc_com.name)
        check_coms = list(
            mon_check_command.objects.all().prefetch_related(
                "categories",
                "exclude_devices"
            ).select_related(
                "mon_service_templ",
                "config",
                "event_handler"
            ).order_by("name")
        )
        enable_perfd = global_config["ENABLE_COLLECTD"]
        if enable_perfd and gen_conf.master:
            check_coms += [
                mon_check_command(
                    name="process-service-perfdata-file",
                    command_line="{} {}/service-perfdata".format(
                        os.path.join(CLUSTER_SBIN, "send_collectd_zmq"),
                        gen_conf.var_dir,
                    ),
                    description="Process service performance data",
                ),
                mon_check_command(
                    name="process-host-perfdata-file",
                    command_line="{} {}/host-perfdata".format(
                        os.path.join(CLUSTER_SBIN, "send_collectd_zmq"),
                        gen_conf.var_dir
                    ),
                    description="Process host performance data",
                ),
            ]
        all_mccs = mon_check_command_special.objects.all()
        for ccs in all_mccs:
            # create a mon_check_command instance for every special command
            special_cc = mon_check_command(
                name=ccs.md_name,
                command_line=ccs.command_line or "/bin/true",
                description=ccs.description,
            )
            # set pk of special command
            special_cc.spk = ccs.pk
            check_coms.append(special_cc)
        check_coms.extend(
            [
                mon_check_command(
                    name="ochp-command",
                    command_line="{} ochp-event \"$HOSTNAME$\" \"$HOSTSTATE$\" \"{}\"".format(
                        os.path.join(CLUSTER_SBIN, "csendsyncerzmq"),
                        "$HOSTOUTPUT$|$HOSTPERFDATA$" if enable_perfd else "$HOSTOUTPUT$"
                    ),
                    description="OCHP Command"
                ),
                mon_check_command(
                    name="ocsp-command",
                    command_line="{} ocsp-event \"$HOSTNAME$\" \"$SERVICEDESC$\" \"$SERVICESTATE$\" \"{}\" ".format(
                        os.path.join(CLUSTER_SBIN, "csendsyncerzmq"),
                        "$SERVICEOUTPUT$|$SERVICEPERFDATA$" if enable_perfd else "$SERVICEOUTPUT$"
                    ),
                    description="OCSP Command"
                ),
                mon_check_command(
                    name="check_service_cluster",
                    command_line="{} --service -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"".format(
                        os.path.join(CLUSTER_BIN, "check_icinga_cluster.py"),
                    ),
                    description="Check Service Cluster"
                ),
                mon_check_command(
                    name="check_host_cluster",
                    command_line="{} --host -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"".format(
                        os.path.join(CLUSTER_BIN, "check_icinga_cluster.py"),
                    ),
                    description="Check Host Cluster"
                ),
            ]
        )
        safe_names = global_config["SAFE_NAMES"]
        mccs_dict = {mccs.pk: mccs for mccs in mon_check_command_special.objects.all()}
        for ngc in check_coms:
            # pprint.pprint(ngc)
            # build / extract ngc_name
            ngc_name = ngc.name
            _ngc_name = cc_command_names.add(ngc_name)
            if _ngc_name != ngc_name:
                self.log(
                    "rewrite {} to {}".format(
                        ngc_name,
                        _ngc_name
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                ngc_name = _ngc_name
            _nag_name = command_names.add(ngc_name)
            if ngc.pk:
                # print ngc.categories.all()
                cats = [cur_cat.full_name for cur_cat in ngc.categories.all()]  # .values_list("full_name", flat=True)
                cat_pks = [cur_cat.pk for cur_cat in ngc.categories.all()]
            else:
                cats = ["/{}".format(TOP_MONITORING_CATEGORY)]
                cat_pks = []
            if ngc.mon_check_command_special_id:
                com_line = mccs_dict[ngc.mon_check_command_special_id].command_line
            else:
                com_line = ngc.command_line
            cc_s = CheckCommand(
                ngc_name,
                com_line,
                ngc.config.name if ngc.config_id else None,
                ngc.mon_service_templ.name if ngc.mon_service_templ_id else None,
                build_safe_name(ngc.description) if safe_names else ngc.description,
                exclude_devices=ngc.exclude_devices.all() if ngc.pk else [],
                icinga_name=_nag_name,
                # link to mon_check_command_special
                mccs_id=ngc.mon_check_command_special_id,
                servicegroup_names=cats,
                servicegroup_pks=cat_pks,
                enable_perfdata=ngc.enable_perfdata,
                is_event_handler=ngc.is_event_handler,
                event_handler=ngc.event_handler,
                event_handler_enabled=ngc.event_handler_enabled,
                # id of check_command
                check_command_pk=ngc.pk,
                # id of mon_check_command_special
                special_command_pk=getattr(ngc, "spk", None),
                db_entry=ngc,
                is_active=ngc.is_active,
                volatile=ngc.volatile,
                show_log=self.__log_counter % 10 == 0 and global_config["DEBUG"] and self.__logging,
            )
            nag_conf = cc_s.get_mon_config()
            self.add_object(nag_conf)
            self[ngc_name] = cc_s


class MonAllContacts(MonFileContainer):
    def __init__(self, gen_conf):
        MonFileContainer.__init__(self, "contact")
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.clear()
        self._add_contacts_from_db(gen_conf)

    def _add_contacts_from_db(self, gen_conf):
        all_nots = mon_notification.objects.all()
        for contact in mon_contact.objects.all().prefetch_related("notifications").select_related("user"):
            full_name = ("{} {}".format(contact.user.first_name, contact.user.last_name)).strip().replace(" ", "_")
            if not full_name:
                full_name = contact.user.login
            not_h_list = [entry for entry in all_nots if entry.channel == "mail" and entry.not_type == "host" and entry.enabled]
            # not_s_list = list(contact.notifications.filter(Q(channel="mail") & Q(not_type="service") & Q(enabled=True)))
            not_s_list = [entry for entry in all_nots if entry.channel == "mail" and entry.not_type == "service" and entry.enabled]
            not_pks = [_not.pk for _not in contact.notifications.all()]
            if len(contact.user.pager) > 5:
                # check for pager number
                not_h_list.extend([entry for entry in all_nots if entry.channel == "sms" and entry.not_type == "host" and entry.enabled])
                not_s_list.extend([entry for entry in all_nots if entry.channel == "sms" and entry.not_type == "service" and entry.enabled])
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
        for cg_group in mon_contactgroup.objects.all().prefetch_related("members"):
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
