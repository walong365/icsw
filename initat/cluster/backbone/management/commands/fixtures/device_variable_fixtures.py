# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
from initat.cluster.backbone.models import device_variable_scope, dvs_allowed_name
from initat.tools import process_tools


def add_fixtures(**kwargs):
    _fact_dict = {}
    for _name, _prefix, _descr, _pri in [
        ("normal", "", "default Scope", 100),
        ("inventory", "__$$ICSW_INV$$__", "Scope for device inventory", 50),
        ("comm", "__$$ICSW_COM$$__", "Scope for device communication", 20),
    ]:
        _fact_dict[_name] = factories.device_variable_scope_factory(
            name=_name,
            prefix=_prefix,
            description=_descr,
            priority=_pri,
        )
    _defaults = {
        "inventory": [
            ("serial", "Serial number", "admin", "s"),
            ("id", "Numeric ID", "admin", "i"),
            ("time_of_purchase", "Date of purchase", "admin", "D"),
        ],
        "comm": [
            ("*IPMI_USERNAME", "IPMI Username", "ipmi", "s"),
            ("*IPMI_PASSWORD", "IPMI Password", "ipmi", "s"),
            ("*IPMI_INTERFACE", "IPMI Interface type", "ipmi", "s"),
            ("*WMI_USERNAME", "WMI Username", "wmi", "s"),
            ("*WMI_PASSWORD", "WMI Password", "wmi", "s"),
        ]
    }
    for _scope_name, _var_list in _defaults.iteritems():
        for _name, _descr, _group, _forced_type in _var_list:
            editable = not _name.startswith("*")
            if not editable:
                _name = _name[1:]
            factories.DVSAllowedNameFactory(
                name=_name,
                description=_descr,
                device_variable_scope=_fact_dict[_scope_name],
                forced_type=_forced_type,
                group=_group,
                editable=editable,
            )

    if False or process_tools.get_machine_name() in ["eddie"]:
        # debug output
        for _e in device_variable_scope.objects.all():
            print unicode(_e)

        for _e in dvs_allowed_name.objects.all():
            print unicode(_e)
