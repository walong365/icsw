#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013 Andreas Lang-Nevyjel
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
""" restore users / groups from old CSW """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import datetime
from django.conf import settings
from django.db.models import Q
from initat.cluster.backbone.models import device, device_class, device_group, \
     mon_contact, mon_contactgroup, mon_check_command_type, mon_check_command, \
     config, mon_service_templ, user, mon_period
from django.db.models.base import ModelBase
     
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

def main():
    data_file = sys.argv[1]
    transfer_dict = {
        "ng_check_command_type" : (mon_check_command_type, ["pk", "name", None], [],),
        "ng_check_command"      : (mon_check_command, ["pk", None, ("config", config), ("mon_check_command_type", mon_check_command_type), ("mon_service_templ", mon_service_templ), "name", "command_line", "description", None, None], ["name",],),
        "ng_contact"            : (mon_contact, ["pk", ("user", user), ("snperiod", mon_period), ("hnperiod", mon_period), "snrecovery", "sncritical", "snwarning", "snunknown", "hnrecovery", "hndown", "hnunreachable", "sncommand", "hncommand"], [],),
        "ng_contactgroup"       : (mon_contactgroup, ["pk", "name", "alias"], [],),
    }
    for line in file(data_file, "r").xreadlines():
        line = line.strip()
        l_line = line.lower()
        if l_line.startswith("insert into"):
            t_obj_name = l_line.split()[2][1:-1]
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
                            #print cur_val, t_info
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
    fix_dict = {
        "device" : {
            "zero_to_null" : [
                "bootserver", "mon_device_templ", "device_location", "mon_ext_host",
                "act_kernel", "new_kernel", "new_image", "act_image",
                "bootnetdevice", "prod_link", "rrd_class", "partition_table",
                "act_partition_table", "new_state", "monitor_server", "nagvis_parent",
            ],
            "zero_to_value" : [
                ("device_class", device_class.objects.all()[0]),
            ]
        },
        "device_group" : {
            "zero_to_null" : ["device",],
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
    