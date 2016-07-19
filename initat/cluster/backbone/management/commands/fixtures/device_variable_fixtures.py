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
from initat.cluster.backbone.models import device_variable_scope, dvs_allowed_names


def add_fixtures(**kwargs):
    _fact_dict = {}
    for _name, _prefix in [
        ("normal", ""),
        ("inventory", "__$$ICSW_INV$$__"),
    ]:
        _fact_dict[_name] = factories.device_variable_scope_factory(
            name=_name,
            prefix=_prefix,
        )
    for _name, _descr, _forced_type in [
        ("serial", "Serial number", "s"),
    ]:
        factories.DVSAllowedNamesFactory(
            name=_name,
            description=_descr,
            unique_per_device=True,
            device_variable_scope=_fact_dict["inventory"],
            forced_type=_forced_type,
        )

    if False:
        # debug output
        for _e in device_variable_scope.objects.all():
            print unicode(_e)

        for _e in dvs_allowed_names.objects.all():
            print unicode(_e)
