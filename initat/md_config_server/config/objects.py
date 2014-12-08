# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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

from django.db.models import Q
from initat.cluster.backbone.models import device, device_group, mon_check_command, mon_period, \
    mon_contact, mon_contactgroup, category_tree, TOP_MONITORING_CATEGORY, mon_notification, \
    host_check_command, mon_check_command_special
from initat.md_config_server.config.check_command import check_command
from initat.md_config_server.config.host_type_config import host_type_config
from initat.md_config_server.config.mon_config import mon_config, unique_list, build_safe_name
import cluster_location
import configfile
import logging_tools
import os
import process_tools

global_config = configfile.get_global_config(process_tools.get_programm_name())


__all__ = [
    "all_host_dependencies",
    "time_periods",
    "all_service_groups",
    "all_commands",
    "all_contacts",
    "all_contact_groups",
    "all_host_groups",
    "all_hosts",
    "all_services",
]


class all_host_dependencies(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list = []

    def get_name(self):
        return "hostdependency"

    def add_host_dependency(self, new_hd):
        self.__obj_list.append(new_hd)

    def get_object_list(self):
        return self.__obj_list


class time_periods(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_time_periods_from_db()

    def get_name(self):
        return "timeperiod"

    def _add_time_periods_from_db(self):
        for cur_per in mon_period.objects.all():
            nag_conf = mon_config(
                "timeperiod",
                cur_per.name,
                timeperiod_name=cur_per.name,
                alias=cur_per.alias.strip() if cur_per.alias.strip() else []
            )
            for short_s, long_s in [
                ("mon", "monday"), ("tue", "tuesday"), ("wed", "wednesday"), ("thu", "thursday"),
                ("fri", "friday"), ("sat", "saturday"), ("sun", "sunday")
            ]:
                nag_conf[long_s] = getattr(cur_per, "%s_range" % (short_s))
            self.__dict[cur_per.pk] = nag_conf
            self.__obj_list.append(nag_conf)

    def __getitem__(self, key):
        return self.__dict[key]

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_service_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        # dict : which host has which service_group defined
        self.__host_srv_lut = {}
        self.cat_tree = category_tree()
        self._add_servicegroups_from_db()

    def get_name(self):
        return "servicegroup"

    def _add_servicegroups_from_db(self):
        for cat_pk in self.cat_tree.get_sorted_pks():
            cur_cat = self.cat_tree[cat_pk]
            nag_conf = mon_config(
                "servicegroup",
                cur_cat.full_name,
                servicegroup_name=cur_cat.full_name,
                alias="{} group".format(cur_cat.full_name))
            self.__host_srv_lut[cur_cat.full_name] = set()
            self.__dict[cur_cat.pk] = nag_conf
            self.__obj_list.append(nag_conf)

    def clear_host(self, host_name):
        for _key, value in self.__host_srv_lut.iteritems():
            if host_name in value:
                value.remove(host_name)

    def add_host(self, host_name, srv_groups):
        for srv_group in srv_groups:
            self.__host_srv_lut[srv_group].add(host_name)

    def get_object_list(self):
        return [obj for obj in self.__obj_list if self.__host_srv_lut[obj.name]]

    def values(self):
        return self.__dict.values()


class all_commands(host_type_config):
    def __init__(self, gen_conf, build_proc):
        check_command.gen_conf = gen_conf
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_notify_commands()
        self._add_commands_from_db(gen_conf)

    def ignore_content(self, in_dict):
        # ignore commands with empty command line (== meta commands)
        return ("".join(in_dict.get("command_line", [""]))).strip() == ""

    def get_name(self):
        return "command"

    def _expand_str(self, in_str):
        for key, value in self._str_repl_dict.iteritems():
            in_str = in_str.replace(key, value)
        return in_str

    def _add_notify_commands(self):
        try:
            cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            cluster_name = "N/A"
        else:
            # cluster_name has to be set, otherwise something went seriously wrong while setting up the cluster
            cluster_name = cluster_location.db_device_variable(cdg, "CLUSTER_NAME", description="name of the cluster").get_value()
        md_vers = global_config["MD_VERSION_STRING"]
        md_type = global_config["MD_TYPE"]
        if os.path.isfile("/opt/cluster/bin/send_mail.py"):
            send_mail_prog = "/opt/cluster/bin/send_mail.py"
        elif os.path.isfile("/usr/local/sbin/send_mail.py"):
            send_mail_prog = "/usr/local/sbin/send_mail.py"
        else:
            send_mail_prog = "/usr/local/bin/send_mail.py"
        send_sms_prog = "/opt/icinga/bin/sendsms"
        from_addr = "{}@{}".format(
            global_config["MD_TYPE"],
            global_config["FROM_ADDR"]
        )

        self._str_repl_dict = {
            "$INIT_MONITOR_INFO$": "{} {}".format(md_type, md_vers),
            "$INIT_CLUSTER_NAME$": "{}".format(cluster_name),
        }

        self.__obj_list.append(
            mon_config(
                "command",
                "dummy-notify",
                command_name="dummy-notify",
                command_line="/usr/bin/true",
            )
        )
        for cur_not in mon_notification.objects.filter(Q(enabled=True)):
            if cur_not.channel == "mail":
                command_line = r"{} -f '{}' -s '{}' -t $CONTACTEMAIL$ -- '{}'".format(
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
            nag_conf = mon_config(
                "command",
                cur_not.name,
                command_name=cur_not.name,
                command_line=command_line.replace("\n", "\\n"),
            )
            self.__obj_list.append(nag_conf)

    def _add_commands_from_db(self, gen_conf):
        # set of names of configs which point to a full check_config
        cc_command_names = unique_list()
        # set of all names
        command_names = unique_list()
        for hc_com in host_check_command.objects.all():
            cur_nc = mon_config(
                "command",
                hc_com.name,
                command_name=hc_com.name,
                command_line=hc_com.command_line,
            )
            self.__obj_list.append(cur_nc)
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
                    command_line="/opt/cluster/sbin/send_collectd_zmq {}/service-perfdata".format(
                        gen_conf.var_dir
                    ),
                    description="Process service performance data",
                ),
                mon_check_command(
                    name="process-host-perfdata-file",
                    command_line="/opt/cluster/sbin/send_collectd_zmq {}/host-perfdata".format(
                        gen_conf.var_dir
                    ),
                    description="Process host performance data",
                ),
            ]
        all_mccs = mon_check_command_special.objects.all()
        check_coms += [
            mon_check_command(
                name=ccs.md_name,
                command_line=ccs.command_line or "/bin/true",
                description=ccs.description,
            ) for ccs in all_mccs
        ]
        check_coms += [
            mon_check_command(
                name="ochp-command",
                command_line="$USER2$ -m DIRECT -s ochp-event \"$HOSTNAME$\" \"$HOSTSTATE$\" \"{}\"".format(
                    "$HOSTOUTPUT$|$HOSTPERFDATA$" if enable_perfd else "$HOSTOUTPUT$"
                ),
                description="OCHP Command"
            ),
            mon_check_command(
                name="ocsp-command",
                command_line="$USER2$ -m DIRECT -s ocsp-event \"$HOSTNAME$\" \"$SERVICEDESC$\" \"$SERVICESTATE$\" \"{}\" ".format(
                    "$SERVICEOUTPUT$|$SERVICEPERFDATA$" if enable_perfd else "$SERVICEOUTPUT$"
                ),
                description="OCSP Command"
            ),
            mon_check_command(
                name="check_service_cluster",
                command_line="/opt/cluster/bin/check_icinga_cluster.py --service -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"",
                description="Check Service Cluster"
            ),
            mon_check_command(
                name="check_host_cluster",
                command_line="/opt/cluster/bin/check_icinga_cluster.py --host -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"",
                description="Check Host Cluster"
            ),
        ]
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
                cats = [TOP_MONITORING_CATEGORY]
                cat_pks = []
            if ngc.mon_check_command_special_id:
                com_line = mccs_dict[ngc.mon_check_command_special_id].command_line
            else:
                com_line = ngc.command_line
            cc_s = check_command(
                ngc_name,
                com_line,
                ngc.config.name if ngc.config_id else None,
                ngc.mon_service_templ.name if ngc.mon_service_templ_id else None,
                build_safe_name(ngc.description) if safe_names else ngc.description,
                exclude_devices=ngc.exclude_devices.all() if ngc.pk else [],
                icinga_name=_nag_name,
                mccs_id=ngc.mon_check_command_special_id,
                servicegroup_names=cats,
                servicegroup_pks=cat_pks,
                enable_perfdata=ngc.enable_perfdata,
                is_event_handler=ngc.is_event_handler,
                event_handler=ngc.event_handler,
                event_handler_enabled=ngc.event_handler_enabled,
                check_command_pk=ngc.pk,
                db_entry=ngc,
                volatile=ngc.volatile,
            )
            nag_conf = cc_s.get_mon_config()
            self.__obj_list.append(nag_conf)
            self.__dict[ngc_name] = cc_s  # ag_conf["command_name"]] = cc_s

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()

    def __getitem__(self, key):
        return self.__dict[key]

    def __contains__(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()


class all_contacts(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_contacts_from_db(gen_conf)

    def get_name(self):
        return "contact"

    def _add_contacts_from_db(self, gen_conf):
        all_nots = mon_notification.objects.all()
        for contact in mon_contact.objects.all().prefetch_related("notifications").select_related("user"):
            full_name = (u"{} {}".format(contact.user.first_name, contact.user.last_name)).strip().replace(" ", "_")
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
            nag_conf = mon_config(
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
            self.__obj_list.append(nag_conf)
            self.__dict[contact.pk] = nag_conf

    def __getitem__(self, key):
        return self.__dict[key]

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_contact_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_contact_groups_from_db(gen_conf)

    def get_name(self):
        return "contactgroup"

    def _add_contact_groups_from_db(self, gen_conf):
        # none group
        self.__dict[0] = mon_config(
            "contactgroup",
            global_config["NONE_CONTACT_GROUP"],
            contactgroup_name=global_config["NONE_CONTACT_GROUP"],
            alias="None group")
        for cg_group in mon_contactgroup.objects.all().prefetch_related("members"):
            nag_conf = mon_config(
                "contactgroup",
                cg_group.name,
                contactgroup_name=cg_group.name,
                alias=cg_group.alias.strip() if cg_group.alias.strip() else [])
            self.__dict[cg_group.pk] = nag_conf
            for member in cg_group.members.all():
                try:
                    nag_conf["members"] = gen_conf["contact"][member.pk]["contact_name"]
                except:
                    pass
        self.__obj_list = self.__dict.values()

    def has_key(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()

    def __getitem__(self, key):
        return self.__dict[key]

    def __contains__(self, key):
        return key in self.__dict__

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_host_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self.cat_tree = category_tree()
        self._add_host_groups_from_db(gen_conf)

    def get_name(self):
        return "hostgroup"

    def _add_host_groups_from_db(self, gen_conf):
        if "device.d" in gen_conf:
            host_pks = gen_conf["device.d"].host_pks
            hostg_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(device_group__pk__in=host_pks)
            host_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(pk__in=host_pks)
            if host_pks:
                # hostgroups by devicegroups
                # distinct is important here
                for h_group in device_group.objects.filter(hostg_filter).prefetch_related("device_group").distinct():
                    nag_conf = mon_config(
                        "hostgroup",
                        h_group.name,
                        hostgroup_name=h_group.name,
                        alias=h_group.description or h_group.name,
                        members=[])
                    self.__dict[h_group.pk] = nag_conf
                    self.__obj_list.append(nag_conf)
                    nag_conf["members"] = [cur_dev.full_name for cur_dev in h_group.device_group.filter(Q(pk__in=host_pks)).select_related("domain_tree_node")]
                # hostgroups by categories
                for cat_pk in self.cat_tree.get_sorted_pks():
                    cur_cat = self.cat_tree[cat_pk]
                    nag_conf = mon_config(
                        "hostgroup",
                        cur_cat.full_name,
                        hostgroup_name=cur_cat.full_name,
                        alias=cur_cat.comment or cur_cat.full_name,
                        members=[])
                    nag_conf["members"] = [cur_dev.full_name for cur_dev in cur_cat.device_set.filter(host_filter).select_related("domain_tree_node")]
                    if nag_conf["members"]:
                        self.__obj_list.append(nag_conf)
            else:
                self.log("empty SQL-Str for in _add_host_groups_from_db()",
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no host-dict found in gen_dict",
                     logging_tools.LOG_LEVEL_WARN)

    def __getitem__(self, key):
        return self.__dict[key]

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_hosts(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)

    def refresh(self, gen_conf):
        pass

    def get_name(self):
        return "host"

    def get_object_list(self):
        return []


class all_services(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)

    def refresh(self, gen_conf):
        pass

    def get_name(self):
        return "service"

    def get_object_list(self):
        return []
