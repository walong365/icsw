#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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
""" copy monitoring settings from old to new db schema """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.db.models import Q, get_app, get_models
from initat.cluster.backbone.models import device, device_group, mon_contact, \
    mon_contactgroup, mon_check_command_type, mon_check_command, \
    config, mon_service_templ, user, mon_period, mon_ext_host, mon_service_templ, \
    mon_device_templ, device_group, group, user, config_str, config_int, config_bool, \
    config_blob
import datetime
from initat.tools import logging_tools
from initat.tools import process_tools


def _parse_value(in_str):
    esc = False
    cur_str, results = ("", [])
    for cur_c in in_str:
        if cur_c == "," and not esc:
            results.append(cur_str)
            cur_str = ""
        else:
            cur_str = "%s%s" % (cur_str, cur_c)
            if cur_c == "'":
                esc = not esc
    results.append(cur_str)
    new_results = []
    for val in results:
        try:
            new_val = datetime.datetime.strptime(val, "'%Y-%m-%d %H:%M:%S'")
        except:
            if val[0] == "'" and val[-1] == "'":
                new_val = val[1:-1]
            else:
                if val.isdigit():
                    new_val = int(val)
                else:
                    new_val = val
        new_results.append(new_val)
    return new_results


def check_for_zero_fks():
    # get all apps
    checked, fixed, errors = (0, 0, 0)
    for model in get_models(get_app("backbone")):
        del_pks = set()
        c_fields = [cur_f for cur_f in model._meta.fields if cur_f.get_internal_type() == "ForeignKey"]
        print "checking model %s (%s: %s; %s)" % (
            model._meta.object_name,
            logging_tools.get_plural("check_field", len(c_fields)),
            ", ".join([cur_c.name for cur_c in c_fields]),
            logging_tools.get_plural("entry", model.objects.all().count()),
        )
        if c_fields:
            obj_count = model.objects.count()
            for obj_idx, cur_obj in enumerate(model.objects.all()):
                checked += 1
                save_it = False
                for c_field in c_fields:
                    if getattr(cur_obj, "%s_id" % (c_field.name)) == 0:
                        try:
                            setattr(cur_obj, c_field.name, None)
                        except:
                            errors += 1
                            print "error setting %s of %s to None: %s" % (
                                c_field.name,
                                unicode(cur_obj),
                                process_tools.get_except_info(),
                            )
                        save_it = True
                    else:
                        try:
                            ref_obj = getattr(cur_obj, c_field.name)
                        except:
                            print "    %s with pk %d references %s with pk %d" % (
                                model._meta.object_name, cur_obj.pk,
                                c_field.name, getattr(cur_obj, "%s_id" % (c_field.name)))
                            del_pks.add(cur_obj.pk)
                    if save_it:
                        fixed += 1
                        try:
                            cur_obj.save()
                        except:
                            errors += 1
                            print "error saving %s: %s" % (
                                unicode(cur_obj),
                                process_tools.get_except_info())
                        else:
                            print "saving (%d of %d) %s" % (
                                obj_idx + 1,
                                obj_count,
                                unicode(cur_obj))
        if del_pks:
            print "from initat.cluster.backbone.models import %s" % (model._meta.object_name)
            print "%s.objects.filter(Q(pk__in=[%s])).delete()" % (
                model._meta.object_name,
                ", ".join(["%d" % (cur_pk) for cur_pk in del_pks]))
    print "checked / fixed / errors: %d / %d / %d" % (checked, fixed, errors)


def remove_duplicate_config_sibs():
    for e_name in [config_str, config_int, config_bool, config_blob]:
        cur_num = e_name.objects.all().count()
        print "%s has %s" % (e_name._meta.object_name, logging_tools.get_plural("entry", cur_num))
        ref_dict = {}
        for entry in e_name.objects.all():
            if entry.device_id == 0:
                entry.device_id = None
            key = (entry.name, entry.config_id, entry.device_id)
            ref_dict.setdefault(key, []).append((entry.pk, entry.value))
        mult_keys = [key for key, value in ref_dict.iteritems() if len(value) > 1]
        if mult_keys:
            print "Found %s" % (logging_tools.get_plural("multiple key", len(mult_keys)))
            for mult_key in sorted(mult_keys):
                print "    %s : %s" % (mult_key, ref_dict[mult_key])
                for del_pk, del_value in ref_dict[mult_key][:-1]:
                    e_name.objects.get(Q(pk=del_pk)).delete()
                    # print key


def main():
    # remove duplicate config str/int/blob
    remove_duplicate_config_sibs()
    # check for zero foreign keys
    check_for_zero_fks()
    sys.exit(0)
    data_file = sys.argv[1]
    transfer_dict = {
        "ng_check_command_type": (mon_check_command_type, ["pk", "name", None], [],),
        "ng_check_command": (mon_check_command,
                             ["pk", None, ("config", config), ("mon_check_command_type", mon_check_command_type), ("mon_service_templ", mon_service_templ),
                              "name", "command_line", "description", None, None], ["name", ],),
        "ng_contact": (mon_contact,
                       ["pk", ("user", user), ("snperiod", mon_period), ("hnperiod", mon_period), "snrecovery", "sncritical", "snwarning", "snunknown",
                        "hnrecovery", "hndown", "hnunreachable", "sncommand", "hncommand"], [],),
        "ng_contactgroup": (mon_contactgroup, ["pk", "name", "alias"], [],),
        "ng_service_templ": (mon_service_templ,
                             ["pk", "name", "volatile", ("nsc_period", mon_period), "max_attempts", "check_interval", "retry_interval", "ninterval",
                              ("nsn_period", mon_period), "nrecovery", "ncritical", "nwarning", "nunknown"], []),
        "ng_device_templ": (mon_device_templ,
                            ["pk", "name", ("mon_service_templ", mon_service_templ), "ccommand", "max_attempts", "ninterval", ("mon_period", mon_period),
                             "nrecovery", "ndown", "nunreachable", "is_default"], []),
    }
    copy_dict = {
        "device": (
            device, [
                (11, "mon_ext_host", "mon_ext_host"),
                (10, "mon_device_templ", mon_device_templ),
                (57, "monitor_checks", None),
            ]
        ),
        "group": (
            group, [
                (6, "first_name", None),
                (7, "last_name", None),
                (8, "title", None),
                (9, "email", None),
                (10, "tel", None),
                (11, "comment", None),
            ]
        ),
        "user": (
            user, [
                (13, "first_name", None),
                (14, "last_name", None),
                (15, "title", None),
                (16, "email", None),
                (17, "pager", None),
                (18, "tel", None),
                (19, "comment", None),
            ]
        ),
    }
    lut_dict = {
        "ng_ext_host": ("mon_ext_host", mon_ext_host, 1, "name"),
    }
    lut_table = {}
    for line in file(data_file, "r").xreadlines():
        line = line.strip()
        l_line = line.lower()
        if l_line.startswith("insert into"):
            t_obj_name = l_line.split()[2][1:-1]
            if t_obj_name in lut_dict:
                values = [_parse_value(val) for val in line.split(None, 4)[-1][1:-2].split("),(")]
                t_name, obj_class, lut_idx, lut_name = lut_dict[t_obj_name]
                for value in values:
                    lut_table.setdefault(t_name, {})[value[0]] = obj_class.objects.get(Q(**{lut_name: value[lut_idx]}))
            if t_obj_name in transfer_dict:
                values = [_parse_value(val) for val in line.split(None, 4)[-1][1:-2].split("),(")]
                obj_class, t_list, unique_list = transfer_dict[t_obj_name]
                if obj_class.objects.all().count():
                    print "%s already populated" % (obj_class)
                else:
                    print "----", obj_class
                    unique_dict = dict([(cur_name, []) for cur_name in unique_list])
                    for value in values:
                        new_obj = obj_class()
                        create = True
                        for cur_val, t_info in zip(value, t_list):
                            # print cur_val, t_info
                            if t_info is not None:
                                if type(t_info) == tuple:
                                    if cur_val == 0:
                                        cur_val = None
                                    else:
                                        try:
                                            cur_val = t_info[1].objects.get(Q(pk=cur_val))
                                        except getattr(t_info[1], "DoesNotExist"):
                                            print "object not found (%s, %s)" % (t_info[1], cur_val)
                                            create = False
                                    t_info = t_info[0]
                                if t_info in unique_dict:
                                    if cur_val in unique_dict[t_info]:
                                        cur_val = "%sx" % (cur_val)
                                    unique_dict[t_info].append(cur_val)
                                if create:
                                    setattr(new_obj, t_info, cur_val)
                        if create:
                            new_obj.save()
            if t_obj_name in copy_dict:
                values = [_parse_value(val) for val in line.split(None, 4)[-1][1:-2].split("),(")]
                obj_class, c_list = copy_dict[t_obj_name]
                for value in values:
                    cur_obj = obj_class.objects.get(Q(pk=value[0]))
                    for val_idx, attr_name, val_obj_name in c_list:
                        val = value[val_idx]
                        if val == 0:
                            val = None
                        else:
                            if isinstance(val_obj_name, basestring):
                                val = lut_table[val_obj_name].get(val, None)
                            elif val_obj_name is None:
                                pass
                            else:
                                try:
                                    val = val_obj_name.objects.get(Q(pk=val))
                                except:
                                    print "object not found (%s, %s)" % (val_obj_name, val)
                                    val = None
                        setattr(cur_obj, attr_name, val)
                    cur_obj.save()
            # n2m relations
            if t_obj_name == "ng_device_contact":
                values = [_parse_value(val) for val in line.split(None, 4)[-1][1:-2].split("),(")]
                for value in values:
                    c_group = mon_contactgroup.objects.get(Q(pk=value[2]))
                    c_group.device_groups.add(device_group.objects.get(Q(pk=value[1])))
            elif t_obj_name == "ng_ccgroup":
                values = [_parse_value(val) for val in line.split(None, 4)[-1][1:-2].split("),(")]
                for value in values:
                    c_group = mon_contactgroup.objects.get(Q(pk=value[2]))
                    c_group.members.add(mon_contact.objects.get(Q(pk=value[1])))
            elif t_obj_name == "ng_cgservicet":
                values = [_parse_value(val) for val in line.split(None, 4)[-1][1:-2].split("),(")]
                for value in values:
                    c_group = mon_contactgroup.objects.get(Q(pk=value[1]))
                    c_group.service_templates.add(mon_service_templ.objects.get(Q(pk=value[2])))
    fix_dict = {
        "device": {
            "zero_to_null": [
                "bootserver", "mon_device_templ", "mon_ext_host",
                "act_kernel", "new_kernel", "new_image", "act_image",
                "bootnetdevice", "prod_link", "rrd_class", "partition_table",
                "act_partition_table", "new_state", "monitor_server", "nagvis_parent",
            ],
            "zero_to_value": [
                # ("device_class", device_class.objects.all()[0]),
            ]
        },
        "device_group": {
            "zero_to_null": ["device", ],
        }
    }
    for obj_name, f_dict in fix_dict.iteritems():
        obj_class = globals()[obj_name]
        print "checking %s" % (obj_name)
        change_list = []
        for cur_obj in obj_class.objects.all():
            changed = False
            for ztn_field in f_dict.get("zero_to_null", []):
                if getattr(cur_obj, "%s_id" % (ztn_field)) == 0:
                    changed = True
                    setattr(cur_obj, ztn_field, None)
            for ztv_field, ztv_value in f_dict.get("zero_to_value", []):
                if getattr(cur_obj, "%s_id" % (ztv_field)) == 0:
                    changed = True
                    setattr(cur_obj, ztv_field, ztv_value)
            if changed:
                change_list.append(cur_obj)
                cur_obj.save()
        print "changed %d" % (len(change_list))


if __name__ == "__main__":
    main()
