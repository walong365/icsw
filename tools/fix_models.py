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

from django.conf import settings
from initat.cluster.backbone.models import device, device_class

def main():
    fix_dict = {
        "device" : 
        {
            "zero_to_null" : [
                "bootserver", "mon_device_templ", "device_location", "mon_ext_host",
                "act_kernel", "new_kernel", "new_image", "act_image",
                "bootnetdevice", "prod_link", "rrd_class", "partition_table",
                "act_partition_table", "new_state", "monitor_server", "nagvis_parent",
            ],
            "zero_to_value" : [
                ("device_class", device_class.objects.all()[0]),
            ]
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
                print cur_obj.pk
                cur_obj.save()
        print "changed %d" % (len(change_list))

if __name__ == "__main__":
    main()
    