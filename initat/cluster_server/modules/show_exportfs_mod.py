# Copyright (C) 2014-2015 Andreas Lang-Nevyjel
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
""" show exportfs entries for the current server """

from django.db.models import Q
from initat.cluster.backbone.models import device_config, home_export_list
import cs_base_class


class show_exportfs(cs_base_class.server_com):
    class Meta:
        needed_configs = ["server"]

    def _call(self, cur_inst):
        # normal exports
        exp_entries = device_config.objects.filter(
            Q(config__name__icontains="export") &
            Q(device__is_meta_device=False)).prefetch_related("config__config_str_set").select_related("device")
        ei_dict = {}
        for entry in exp_entries:
            dev_pk, act_pk = (entry.device.pk,
                              entry.config.pk)
            ei_dict.setdefault(
                dev_pk, {}
            ).setdefault(
                act_pk, {
                    "export": None,
                    "import": None,
                    "node_postfix": "",
                    "options": "-soft"
                }
            )
            for c_str in entry.config.config_str_set.all():
                if c_str.name in ei_dict[dev_pk][act_pk]:
                    ei_dict[dev_pk][act_pk][c_str.name] = c_str.value
            if not ei_dict[dev_pk][act_pk]["export"]:
                del ei_dict[dev_pk][act_pk]
        # home-exports
        home_exp_dict = home_export_list().exp_dict
        # flatten list, structure:
        # - dev_pk
        # - export
        # - options
        exp_list = []
        for _key, _struct in home_exp_dict.iteritems():
            exp_list.append((_struct["entry"].device.pk, _struct["createdir"], _struct["options"]))
        for _devpk, _sstruct in ei_dict.iteritems():
            for _cpk, _struct in _sstruct.iteritems():
                exp_list.append((_devpk, _struct["export"], _struct["options"]))
        num_dict = {}
        for _is_local in [True, False]:
            _type = "local" if _is_local else "foreign"
            if _is_local:
                _vals = [_entry for _entry in exp_list if _entry[0] == self.server_idx]
            else:
                _vals = [_entry for _entry in exp_list if _entry[0] != self.server_idx]
            num_dict[_type] = len(_vals)
            if _vals:
                print("\nshowing {:d} {} export entries:\n".format(num_dict[_type], _type))
                for _val in _vals:
                    print("{:<40s} *(rw,no_root_squash,async,no_subtree_check)".format(_val[1]))
                print("\n")
        cur_inst.srv_com.set_result(
            "ok showed {:d} local and {:d} foreign exports".format(num_dict["local"], num_dict["foreign"])
        )
