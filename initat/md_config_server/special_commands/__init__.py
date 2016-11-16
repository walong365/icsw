# Copyright (C) 2008-2014,2016 Andreas Lang-Nevyjel, init.at
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

""" special tasks for md-config-server, load from submodule instances """

from __future__ import unicode_literals, print_function

from django.db.models import Q

from initat.cluster.backbone.models import mon_check_command_special, mon_check_command, SpecialGroupsEnum
from initat.cluster.backbone.models.functions import get_related_models
from initat.md_config_server.special_commands.base import SpecialBase, ArgTemplate
from .struct import DynamicCheckServer, DynamicCheckAction
from initat.md_config_server.special_commands.instances import *
from initat.tools import logging_tools


def check_special_commands(log_com):
    pks_found = set()
    mccs_dict = {}
    for _name, _entry in dynamic_checks.class_dict.iteritems():
        _inst = _entry(log_com)
        if dynamic_checks.meta_to_class_name(_inst.Meta.name) != _name:
            log_com(
                "special {} has illegal name {}".format(
                    _name,
                    _inst.Meta.name
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            log_com("found special {}".format(_name))
            cur_mccs = check_mccs(log_com, _inst.Meta)
            mccs_dict[cur_mccs.name] = cur_mccs
            pks_found.add(cur_mccs.pk)
            if cur_mccs.meta:
                for _sub_com in _inst.get_commands():
                    if not hasattr(_sub_com.Meta, "db_name"):
                        # set db_name attribute
                        _sub_com.Meta.db_name = _sub_com.Meta.name
                    sub_mccs = check_mccs(log_com, _sub_com.Meta, parent=cur_mccs)
                    mccs_dict[sub_mccs.name] = sub_mccs
                    pks_found.add(sub_mccs.pk)
    # delete stale
    del_mccs = mon_check_command_special.objects.exclude(pk__in=pks_found)
    if del_mccs:
        for _del_mcc in del_mccs:
            log_com(
                "trying to remove stale {}...".format(
                    unicode(_del_mcc),
                )
            )
            _refs = get_related_models(_del_mcc)
            if _refs:
                log_com("  unable to remove because referenced {}".format(logging_tools.get_plural("time", _refs)), logging_tools.LOG_LEVEL_ERROR)
            else:
                _del_mcc.delete()
                log_com("  ...done")
    # rewrite
    for to_rewrite in mon_check_command.objects.filter(Q(name__startswith="@")):
        log_com("rewriting {} to new format... ".format(unicode(to_rewrite)))
        _key = to_rewrite.name.split("@")[1].lower()
        if _key in mccs_dict:
            to_rewrite.name = to_rewrite.name.split("@")[2]
            to_rewrite.mon_check_command_special = mccs_dict[_key]
            to_rewrite.save()
        else:
            log_com("key {} not found in dict".format(_key), logging_tools.LOG_LEVEL_ERROR)


def check_mccs(log_com, meta, parent=None):
    try:
        cur_mccs = mon_check_command_special.objects.get(Q(name=meta.db_name))
    except mon_check_command_special.DoesNotExist:
        cur_mccs = mon_check_command_special(name=meta.db_name)
    # also used in snmp/struct.py and generic_net_handler.py
    for attr_name in {"command_line", "info", "description", "is_active", "meta", "identifier"}:
        setattr(cur_mccs, attr_name, getattr(meta, attr_name, ""))
    cur_mccs.group = getattr(meta, "group", SpecialGroupsEnum.unspec).value
    cur_mccs.parent = parent
    cur_mccs.save()
    return cur_mccs
