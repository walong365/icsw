# Copyright (C) 2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
# -*- coding: utf-8 -*-
#
""" helper functions for cluster-backbone-sql models """

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models import Q
import pytz
import time

cluster_timezone = pytz.timezone(settings.TIME_ZONE)
system_timezone = pytz.timezone(time.tzname[0])


# helper functions
def _check_integer(inst, attr_name, **kwargs):
    cur_val = getattr(inst, attr_name)
    min_val, max_val = (kwargs.get("min_val", None),
                        kwargs.get("max_val", None))
    if cur_val is None and kwargs.get("none_to_zero", False):
        cur_val = 0
    try:
        cur_val = int(cur_val)
    except:
        raise ValidationError("{} is not an integer".format(attr_name))
    else:
        if min_val is not None and max_val is not None:
            if min_val is None:
                if cur_val > max_val:
                    raise ValidationError("{} too high ({:d} > {:d})".format(
                        attr_name,
                        cur_val,
                        max_val))
            elif max_val is None:
                if cur_val < min_val:
                    raise ValidationError("{} too low ({:d} < {:d})".format(
                        attr_name,
                        cur_val,
                        min_val))
            else:
                if cur_val < min_val or cur_val > max_val:
                    raise ValidationError("{} ({:d}) not in [{:d}, {:d}]".format(
                        attr_name,
                        cur_val,
                        min_val,
                        max_val))
        setattr(inst, attr_name, cur_val)
        return cur_val


def _check_float(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    try:
        cur_val = float(cur_val)
    except:
        raise ValidationError("{} is not a float".format(attr_name))
    setattr(inst, attr_name, cur_val)


def _check_empty_string(inst, attr_name, **kwargs):
    _strip = kwargs.get("strip", False)
    cur_val = getattr(inst, attr_name)
    if cur_val is None:
        # cast to string
        cur_val = ""
    if not cur_val.strip():
        raise ValidationError("{} can not be empty".format(attr_name))
    if _strip:
        setattr(inst, attr_name, cur_val.strip())


def _check_non_empty_string(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    if cur_val.strip():
        raise ValidationError("{} must be empty".format(attr_name))


def to_system_tz(in_dt):
    return in_dt.astimezone(system_timezone)


def get_related_models(in_obj, m2m=False, detail=False, check_all=False, ignore_objs=[]):
    used_objs = [] if detail else 0
    if hasattr(in_obj, "CSW_Meta"):
        # copy list because we remove entries as we iterate over foreign models
        fk_ignore_list = [entry for entry in getattr(in_obj.CSW_Meta, "fk_ignore_list", [])]
    else:
        fk_ignore_list = []
    if check_all:
        ignore_list = []
    else:
        ignore_list = fk_ignore_list
    _lock_list = []
    # copy ignore_list to static list because some entries can be referenced more than once
    # (peer_information for instance [in netdevice])
    ignore_list_static = [entry for entry in ignore_list]
    for rel_obj in in_obj._meta.get_all_related_objects():
        rel_field_name = rel_obj.field.name
        _rel_name = rel_obj.model._meta.object_name
        if _rel_name not in ignore_list_static:
            if rel_obj.field.rel.on_delete == models.SET_NULL:
                # ignore foreign keys where on_delete == SET_NULL
                pass
            else:
                ref_list = [entry for entry in rel_obj.model.objects.filter(Q(**{rel_field_name: in_obj})) if entry not in ignore_objs]
                if ref_list:
                    _lock_list.append("{} -> {} ({:d})".format(rel_field_name, _rel_name, len(ref_list)))
                    if detail:
                        used_objs.extend(ref_list)
                    else:
                        used_objs += len(ref_list)
        else:
            # _rel_name can be missing from ignore list in case the object references the target more than once
            # (again peer_information in netdevice)
            if _rel_name in ignore_list:
                ignore_list.remove(_rel_name)
    if m2m:
        for m2m_obj in in_obj._meta.get_all_related_many_to_many_objects():
            m2m_field_name = m2m_obj.field.name
            if detail:
                used_objs.extend(list(m2m_obj.model.objects.filter(Q(**{m2m_field_name: in_obj}))))
            else:
                used_objs += m2m_obj.model.objects.filter(Q(**{m2m_field_name: in_obj})).count()
    in_obj._lock_list = _lock_list
    if ignore_list:
        raise ImproperlyConfigured(
            "ignore_list not empty, typos (model {}, {}) ?".format(
                in_obj._meta.model_name,
                ", ".join(ignore_list)
            )
        )
    return used_objs


def get_change_reset_list(s_obj, d_obj, required_changes=None):
    # changes required from client
    if not required_changes:
        required_changes = {}
    c_list, r_list = ([], [])
    for _f in s_obj._meta.fields:
        s_val, d_val = (getattr(s_obj, _f.name), getattr(d_obj, _f.name))
        cur_t = _f.get_internal_type()
        # ignore Date(Time)Fields
        if _f.name in required_changes and cur_t not in ["DateTimeField", "DateField"]:
            # value for reset list
            dr_val = d_val
            if cur_t == "ForeignKey":
                # print _f.name, cur_t, d_val, required_changes[_f.name]
                if d_val is not None:
                    # d_val_orig = d_val
                    dr_val = d_val.pk
            if dr_val != required_changes[_f.name]:
                # values was reset from pre / post save, store in r_list
                r_list.append((_f.name, dr_val))
        if cur_t in ["CharField", "TextField", "IntegerField", "PositiveIntegerField", "BooleanField", "NullBooleanField", "ForeignKey"]:
            if s_val != d_val:
                c_list.append((_f.verbose_name, "changed from '{!s}' to '{!s}'".format(s_val, d_val)))
        # elif cur_t in ["ForeignKey"]:
        #    print "**", _f.name, s_val, d_val
        elif cur_t in ["DateTimeField", "AutoField", "FloatField"]:
            # ignore
            pass
        else:
            print "FieldType() in get_change_reset_list: {}".format(cur_t)
    return c_list, r_list
