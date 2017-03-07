# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for device variables """

from initat.cluster.backbone import factories
from initat.cluster.backbone.models import device_variable_scope, dvs_allowed_name, DeviceVarTypeEnum, \
    DeviceConnectionEnum
from initat.tools import process_tools


def add_fixtures(**kwargs):
    _fact_dict = {}
    for _name, _prefix, _descr, _pri, _fixed, _sys_scope in [
        ("normal", "", "default Scope", 100, False, True),
        ("inventory", "__$$ICSW_INV$$__", "Scope for device inventory", 50, True, False),
        ("comm", "__$$ICSW_COM$$__", "Scope for device communication", 20, True, True),
    ]:
        _fact_dict[_name] = factories.device_variable_scope_factory(
            name=_name,
            prefix=_prefix,
            description=_descr,
            priority=_pri,
            fixed=_fixed,
            system_scope=_sys_scope,
        )
    # set default scope
    _fact_dict["normal"].default_scope = True
    _fact_dict["normal"].save()
    comm_list = []
    _used_vars = set()
    for dci in DeviceConnectionEnum:
        # name is group
        for cur_var in dci.value.var_list + dci.value.opt_list:
            if cur_var.name not in _used_vars:
                _used_vars.add(cur_var.name)
                comm_list.append(
                    (
                        "*{}".format(cur_var.name),
                        cur_var.info,
                        dci.name,
                        cur_var.var_type,
                        cur_var.is_password,
                    )
                )
    _defaults = {
        "inventory": [
            ("serial", "Serial number", "admin", DeviceVarTypeEnum.string, False),
            ("id", "Numeric ID", "admin", DeviceVarTypeEnum.integer, False),
            ("time_of_purchase", "Date of purchase", "admin", DeviceVarTypeEnum.date, False),
        ],
        "comm": comm_list,
    }
    for _scope_name, _var_list in _defaults.items():
        for _name, _descr, _group, _forced_type, _passwd_field in _var_list:
            editable = not _name.startswith("*")
            if not editable:
                _name = _name[1:]
            factories.DVSAllowedNameFactory(
                name=_name,
                description=_descr,
                device_variable_scope=_fact_dict[_scope_name],
                forced_type=_forced_type.value,
                group=_group,
                editable=editable,
                password_field=_passwd_field,
            )

    if False or process_tools.get_machine_name() in ["eddie"]:
        # debug output
        for _e in device_variable_scope.objects.all():
            print(str(_e))

        for _e in dvs_allowed_name.objects.all():
            print(str(_e))
