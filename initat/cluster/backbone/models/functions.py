# Copyright (C) 2012-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" helper functions for ICSW models """

import collections
import datetime
import time

import decorator
import pytz
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models import Q

from .vnc_functions import *

# to keep optimize import from removing the .vnc_functions import
_ = ForkedPdb

from initat.tools import logging_tools

cluster_timezone = pytz.timezone(settings.TIME_ZONE)
system_timezone = pytz.timezone(time.tzname[0])


def db_limit_1():
    # return True if databases do not support some unique_together combinations
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


def db_t2000_limit():
    # return True if databases has a problem with textfields longer than 2000 chars
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


# helper functions
def check_integer(inst, attr_name, **kwargs):
    cur_val = getattr(inst, attr_name)
    min_val, max_val = (
        kwargs.get("min_val", None),
        kwargs.get("max_val", None)
    )
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
                    raise ValidationError(
                        "{} too high ({:d} > {:d})".format(
                            attr_name,
                            cur_val,
                            max_val
                        )
                    )
            elif max_val is None:
                if cur_val < min_val:
                    raise ValidationError(
                        "{} too low ({:d} < {:d})".format(
                            attr_name,
                            cur_val,
                            min_val
                        )
                    )
            else:
                if cur_val < min_val or cur_val > max_val:
                    raise ValidationError(
                        "{} ({:d}) not in [{:d}, {:d}]".format(
                            attr_name,
                            cur_val,
                            min_val,
                            max_val
                        )
                    )
        setattr(inst, attr_name, cur_val)
        return cur_val


def check_float(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    try:
        cur_val = float(cur_val)
    except:
        raise ValidationError("{} is not a float".format(attr_name))
    setattr(inst, attr_name, cur_val)


def check_empty_string(inst, attr_name, **kwargs):
    _strip = kwargs.get("strip", False)
    cur_val = getattr(inst, attr_name)
    if cur_val is None:
        # cast to string
        cur_val = ""
    if not cur_val.strip():
        raise ValidationError("{} can not be empty".format(attr_name))
    if _strip:
        setattr(inst, attr_name, cur_val.strip())


def check_non_empty_string(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    if cur_val.strip():
        raise ValidationError("{} must be empty".format(attr_name))


def to_system_tz(in_dt):
    return in_dt.astimezone(system_timezone)


def get_related_models(in_obj, m2m=False, detail=False, check_all=False, ignore_objs=[], related_objects=None):
    """
    :param related_objects: If not None, RelatedObjects with references are appended
    """
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
    # django 1.9 code
    rel_objs = list(
        [
            _f for _f in in_obj._meta.get_fields() if (_f.one_to_many or _f.one_to_one) and _f.auto_created
        ]
    )
    for rel_obj in rel_objs:
        rel_field_name = rel_obj.field.name
        _rel_name = rel_obj.related_model._meta.object_name
        if _rel_name not in ignore_list_static:
            if rel_obj.field.rel.on_delete == models.SET_NULL:
                # ignore foreign keys where on_delete == SET_NULL
                pass
            else:
                ref_list = [
                    entry for entry in rel_obj.related_model.objects.filter(
                        Q(**{rel_field_name: in_obj})
                    ) if entry not in ignore_objs
                ]
                if ref_list:
                    if related_objects is not None:
                        rel_obj.ref_list = ref_list
                        related_objects.append(rel_obj)
                    _lock_list.append(
                        "{} -> {} ({:d})".format(
                            rel_field_name,
                            _rel_name,
                            len(ref_list)
                        )
                    )
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
        all_m2ms = [
            _f for _f in in_obj._meta.get_fields(include_hidden=True) if _f.many_to_many and _f.auto_created
        ]
        for m2m_obj in all_m2ms:
            m2m_field_name = m2m_obj.field.name
            if detail:
                used_objs.extend(
                    list(
                        m2m_obj.related_model.objects.filter(
                            Q(**{m2m_field_name: in_obj})
                        )
                    )
                )
            else:
                used_objs += m2m_obj.related_model.objects.filter(
                    Q(**{m2m_field_name: in_obj})
                ).count()
    in_obj._lock_list = _lock_list
    if ignore_list:
        raise ImproperlyConfigured(
            "ignore_list not empty, typos (model {}, {}) ?".format(
                in_obj._meta.model_name,
                ", ".join(ignore_list)
            )
        )
    return used_objs


def can_delete_obj(obj, logger=None):
    """
    Check is obj is referenced in models which are not in fk_ignore_list
    NOTE: references which are set to NULL on delete are considered deletable
    :return: Response obj which can be evaluated to bool and contains a "msg"-field
    """
    from initat.cluster.backbone.models import device
    ignore_objs = {
        "device_group": list(device.objects.filter(Q(device_group=obj.idx) & Q(is_meta_device=True)))
    }.get(obj._meta.object_name, [])
    related_objects = []
    num_refs = get_related_models(obj, ignore_objs=ignore_objs, related_objects=related_objects)

    delete_ok = False
    msg = u''
    if num_refs:
        if logger:
            logger.error(
                "lock_list for {} contains {}:".format(
                    unicode(obj),
                    logging_tools.get_plural("entry", len(obj._lock_list))
                )
            )
        for _num, _entry in enumerate(obj._lock_list, 1):
            if logger:
                logger.error(" - {:2d}: {}".format(_num, _entry))
        msg = "cannot delete {}: referenced {}".format(
            obj._meta.object_name,
            logging_tools.get_plural("time", num_refs)
        )
    else:
        delete_ok = True

    class CanDeleteAnswer(object):
        def __init__(self, delete_ok, msg, related_objects):
            """
            :param related_objects: list of RelatedObject (django)
            """
            self.delete_ok = delete_ok
            self.msg = msg
            self.related_objects = related_objects

        def __nonzero__(self):
            return self.delete_ok

    return CanDeleteAnswer(delete_ok, msg, related_objects)


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
                c_list.append((_f.verbose_name, u"changed from '{!s}' to '{!s}'".format(s_val, d_val)))
        # elif cur_t in ["ForeignKey"]:
        #    print "**", _f.name, s_val, d_val
        elif cur_t in ["DateTimeField", "AutoField", "FloatField", "DateField", "GenericIPAddressField"]:
            # ignore
            pass
        else:
            print "FieldType() in get_change_reset_list: {}".format(cur_t)
    return c_list, r_list


class duration(object):
    """
    Utility for databases which have a duration type
    """

    @classmethod
    def get_class(cls, ident):
        for klass in cls.Hour, cls.Day, cls.Week, cls.Month:
            if ident == klass.ID:
                return klass
        raise Exception()

    # NOTE: don't use timezone info here
    class Day(object):
        ID = 1

        @classmethod
        def get_time_frame_start(cls, timepoint):
            return timepoint.replace(hour=0, minute=0, second=0, microsecond=0)

        @classmethod
        def get_end_time_for_start(cls, starttime):
            return starttime + datetime.timedelta(days=1)

        @classmethod
        def get_display_date(cls, timepoint):
            return u"{:02d}-{:02d}".format(timepoint.month, timepoint.day)

    class Month(object):
        ID = 2

        @classmethod
        def get_time_frame_start(cls, timepoint):
            return timepoint.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        @classmethod
        def get_end_time_for_start(cls, starttime):
            return cls.get_time_frame_start(starttime + datetime.timedelta(days=35))  # take beginning of next month

        @classmethod
        def get_display_date(cls, timepoint):
            return u"{}-{:02d}".format(timepoint.year, timepoint.month)

    class Hour(object):
        ID = 3

        @classmethod
        def get_time_frame_start(cls, timepoint):
            return timepoint.replace(minute=0, second=0, microsecond=0)

        @classmethod
        def get_end_time_for_start(cls, starttime):
            return starttime + datetime.timedelta(seconds=60 * 60)

        @classmethod
        def get_display_date(cls, timepoint):
            return u"{:02d}:{:02d}".format(timepoint.hour, 0)

    class Week(object):
        ID = 4

        @classmethod
        def get_time_frame_start(cls, timepoint):
            date_day = duration.Day.get_time_frame_start(timepoint)
            return date_day - datetime.timedelta(days=date_day.weekday())

        @classmethod
        def get_end_time_for_start(cls, starttime):
            return starttime + datetime.timedelta(days=7)

        @classmethod
        def get_display_date(cls, timepoint):
            return u"{:02d}-{:02d}".format(timepoint.month, timepoint.day)

    class Year(object):
        ID = 5

        @classmethod
        def get_time_frame_start(cls, timepoint):
            return timepoint.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        @classmethod
        def get_end_time_for_start(cls, starttime):
            return cls.get_time_frame_start(starttime + datetime.timedelta(days=370))

        @classmethod
        def get_display_date(cls, timepoint):
            return u"{:04d}".format(timepoint.year)

    class Decade(object):
        ID = 6

        @classmethod
        def get_time_frame_start(cls, timepoint):
            return timepoint.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0, year=10 * int(timepoint.year / 10))

        @classmethod
        def get_end_time_for_start(cls, starttime):
            return cls.get_time_frame_start(starttime + datetime.timedelta(days=3660))

        @classmethod
        def get_display_date(cls, timepoint):
            return u"{:04d}".format(timepoint.year)

    @classmethod
    def get_shorter_duration(cls, duration_type):
        if type(duration_type) == int:
            duration_type = cls.get_class(duration_type)

        if duration_type == cls.Day:
            shorter_duration = cls.Hour
        elif duration_type == cls.Week:
            shorter_duration = cls.Day
        elif duration_type == cls.Month:
            shorter_duration = cls.Day  # weeks are not nice
        elif duration_type == cls.Year:
            shorter_duration = cls.Month
        elif duration_type == cls.Decade:
            shorter_duration = cls.Year
        else:
            raise ValueError("Invalid duration type: {}".format(duration_type))
        return shorter_duration


_memoize_cache = collections.defaultdict(lambda: {})


def memoize_with_expiry(expiry_time=0, _cache=None, num_args=None):
    def _memoize_with_expiry(func, *args, **kw):
        # NOTE: if _cache is explicitly specified, it is not cleared by clear_memoize_cache()
        cache = _cache or _memoize_cache[func]

        mem_args = args[:num_args]
        # frozenset is used to ensure hashability
        if kw:
            key = mem_args, frozenset(kw.iteritems())
        else:
            key = mem_args
        if key in cache:
            result, timestamp = cache[key]
            # Check the age.
            age = time.time() - timestamp
            if not expiry_time or age < expiry_time:
                return result
        result = func(*args, **kw)
        cache[key] = (result, time.time())
        return result
    return decorator.decorator(_memoize_with_expiry)


def clear_memoize_cache():
    # useful for tests
    _memoize_cache.clear()
