# Copyright (C) 2012-2015 Andreas Lang-Nevyjel, init.at
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
import datetime
import sys
import pdb
from initat.tools import logging_tools

cluster_timezone = pytz.timezone(settings.TIME_ZONE)
system_timezone = pytz.timezone(time.tzname[0])


# helper functions
def _check_integer(inst, attr_name, **kwargs):
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
                    if related_objects is not None:
                        rel_obj.ref_list = ref_list
                        related_objects.append(rel_obj)
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
        elif cur_t in ["DateTimeField", "AutoField", "FloatField", "DateField"]:
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
            return starttime + datetime.timedelta(seconds=60*60)

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
        else:
            raise ValueError("Invalid duration type: {}".format(duration_type))
        return shorter_duration


# Modified DES required by vnc

#  D3DES (V5.09) -
#
#  A portable, public domain, version of the Data Encryption Standard.
#
#  Written with Symantec's THINK (Lightspeed) C by Richard Outerbridge.
#  Thanks to: Dan Hoey for his excellent Initial and Inverse permutation
#  code;  Jim Gillogly & Phil Karn for the DES key schedule code; Dennis
#  Ferguson, Eric Young and Dana How for comparing notes; and Ray Lau,
#  for humouring me on.
#
#  Copyright (c) 1988,1989,1990,1991,1992 by Richard Outerbridge.
#  (GEnie : OUTER; CIS : [71755,204]) Graven Imagery, 1992.
#

from struct import pack, unpack


# vnc des key
vnckey = [23, 82, 107, 6, 35, 78, 88, 7]

# strange des adaption
# bytebit = [ 0200, 0100, 040, 020, 010, 04, 02, 01 ] # original
bytebit = [01, 02, 04, 010, 020, 040, 0100, 0200]  # VNC version


bigbyte = [
    0x800000L,    0x400000L,    0x200000L,    0x100000L,
    0x80000L,    0x40000L,    0x20000L,    0x10000L,
    0x8000L,    0x4000L,    0x2000L,    0x1000L,
    0x800L,     0x400L,     0x200L,     0x100L,
    0x80L,    0x40L,        0x20L,        0x10L,
    0x8L,        0x4L,        0x2L,        0x1L
]

# Use the key schedule specified in the Standard (ANSI X3.92-1981).

pc1 = [
    56, 48, 40, 32, 24, 16,  8,     0, 57, 49, 41, 33, 25, 17,
    9,  1, 58, 50, 42, 34, 26,    18, 10,  2, 59, 51, 43, 35,
    62, 54, 46, 38, 30, 22, 14,     6, 61, 53, 45, 37, 29, 21,
    13,  5, 60, 52, 44, 36, 28,    20, 12,  4, 27, 19, 11,  3
]

totrot = [1, 2, 4, 6, 8, 10, 12, 14, 15, 17, 19, 21, 23, 25, 27, 28]

pc2 = [
    13, 16, 10, 23,  0,  4,  2, 27, 14,  5, 20,  9,
    22, 18, 11,  3, 25,  7, 15,  6, 26, 19, 12,  1,
    40, 51, 30, 36, 46, 54, 29, 39, 50, 44, 32, 47,
    43, 48, 38, 55, 33, 52, 45, 41, 49, 35, 28, 31
]


def deskey(key, decrypt):      # Thanks to James Gillogly & Phil Karn!
    key = unpack('8B', key)

    pc1m = [0]*56
    pcr = [0]*56
    kn = [0L]*32
  
    for j in range(56):
        l = pc1[j]
        m = l & 07
        if key[l >> 3] & bytebit[m]:
            pc1m[j] = 1
        else:
            pc1m[j] = 0

    for i in range(16):
        if decrypt:
            m = (15 - i) << 1
        else:
            m = i << 1
        n = m + 1
        kn[m] = kn[n] = 0L
        for j in range(28):
            l = j + totrot[i]
            if l < 28:
                pcr[j] = pc1m[l]
            else:
                pcr[j] = pc1m[l - 28]
        for j in range(28, 56):
            l = j + totrot[i]
            if l < 56:
                pcr[j] = pc1m[l]
            else:
                pcr[j] = pc1m[l - 28]
        for j in range(24):
            if pcr[pc2[j]]:
                kn[m] |= bigbyte[j]
            if pcr[pc2[j+24]]:
                kn[n] |= bigbyte[j]

    return cookey(kn)


def cookey(raw):
    key = []
    for i in range(0, 32, 2):
        (raw0, raw1) = (raw[i], raw[i+1])
        k = (raw0 & 0x00fc0000L) << 6
        k |= (raw0 & 0x00000fc0L) << 10
        k |= (raw1 & 0x00fc0000L) >> 10
        k |= (raw1 & 0x00000fc0L) >> 6
        key.append(k)
        k = (raw0 & 0x0003f000L) << 12
        k |= (raw0 & 0x0000003fL) << 16
        k |= (raw1 & 0x0003f000L) >> 4
        k |= (raw1 & 0x0000003fL)
        key.append(k)
    return key

SP1 = [
    0x01010400L, 0x00000000L, 0x00010000L, 0x01010404L,
    0x01010004L, 0x00010404L, 0x00000004L, 0x00010000L,
    0x00000400L, 0x01010400L, 0x01010404L, 0x00000400L,
    0x01000404L, 0x01010004L, 0x01000000L, 0x00000004L,
    0x00000404L, 0x01000400L, 0x01000400L, 0x00010400L,
    0x00010400L, 0x01010000L, 0x01010000L, 0x01000404L,
    0x00010004L, 0x01000004L, 0x01000004L, 0x00010004L,
    0x00000000L, 0x00000404L, 0x00010404L, 0x01000000L,
    0x00010000L, 0x01010404L, 0x00000004L, 0x01010000L,
    0x01010400L, 0x01000000L, 0x01000000L, 0x00000400L,
    0x01010004L, 0x00010000L, 0x00010400L, 0x01000004L,
    0x00000400L, 0x00000004L, 0x01000404L, 0x00010404L,
    0x01010404L, 0x00010004L, 0x01010000L, 0x01000404L,
    0x01000004L, 0x00000404L, 0x00010404L, 0x01010400L,
    0x00000404L, 0x01000400L, 0x01000400L, 0x00000000L,
    0x00010004L, 0x00010400L, 0x00000000L, 0x01010004L
]

SP2 = [
    0x80108020L, 0x80008000L, 0x00008000L, 0x00108020L,
    0x00100000L, 0x00000020L, 0x80100020L, 0x80008020L,
    0x80000020L, 0x80108020L, 0x80108000L, 0x80000000L,
    0x80008000L, 0x00100000L, 0x00000020L, 0x80100020L,
    0x00108000L, 0x00100020L, 0x80008020L, 0x00000000L,
    0x80000000L, 0x00008000L, 0x00108020L, 0x80100000L,
    0x00100020L, 0x80000020L, 0x00000000L, 0x00108000L,
    0x00008020L, 0x80108000L, 0x80100000L, 0x00008020L,
    0x00000000L, 0x00108020L, 0x80100020L, 0x00100000L,
    0x80008020L, 0x80100000L, 0x80108000L, 0x00008000L,
    0x80100000L, 0x80008000L, 0x00000020L, 0x80108020L,
    0x00108020L, 0x00000020L, 0x00008000L, 0x80000000L,
    0x00008020L, 0x80108000L, 0x00100000L, 0x80000020L,
    0x00100020L, 0x80008020L, 0x80000020L, 0x00100020L,
    0x00108000L, 0x00000000L, 0x80008000L, 0x00008020L,
    0x80000000L, 0x80100020L, 0x80108020L, 0x00108000L
]

SP3 = [
    0x00000208L, 0x08020200L, 0x00000000L, 0x08020008L,
    0x08000200L, 0x00000000L, 0x00020208L, 0x08000200L,
    0x00020008L, 0x08000008L, 0x08000008L, 0x00020000L,
    0x08020208L, 0x00020008L, 0x08020000L, 0x00000208L,
    0x08000000L, 0x00000008L, 0x08020200L, 0x00000200L,
    0x00020200L, 0x08020000L, 0x08020008L, 0x00020208L,
    0x08000208L, 0x00020200L, 0x00020000L, 0x08000208L,
    0x00000008L, 0x08020208L, 0x00000200L, 0x08000000L,
    0x08020200L, 0x08000000L, 0x00020008L, 0x00000208L,
    0x00020000L, 0x08020200L, 0x08000200L, 0x00000000L,
    0x00000200L, 0x00020008L, 0x08020208L, 0x08000200L,
    0x08000008L, 0x00000200L, 0x00000000L, 0x08020008L,
    0x08000208L, 0x00020000L, 0x08000000L, 0x08020208L,
    0x00000008L, 0x00020208L, 0x00020200L, 0x08000008L,
    0x08020000L, 0x08000208L, 0x00000208L, 0x08020000L,
    0x00020208L, 0x00000008L, 0x08020008L, 0x00020200L
]

SP4 = [
    0x00802001L, 0x00002081L, 0x00002081L, 0x00000080L,
    0x00802080L, 0x00800081L, 0x00800001L, 0x00002001L,
    0x00000000L, 0x00802000L, 0x00802000L, 0x00802081L,
    0x00000081L, 0x00000000L, 0x00800080L, 0x00800001L,
    0x00000001L, 0x00002000L, 0x00800000L, 0x00802001L,
    0x00000080L, 0x00800000L, 0x00002001L, 0x00002080L,
    0x00800081L, 0x00000001L, 0x00002080L, 0x00800080L,
    0x00002000L, 0x00802080L, 0x00802081L, 0x00000081L,
    0x00800080L, 0x00800001L, 0x00802000L, 0x00802081L,
    0x00000081L, 0x00000000L, 0x00000000L, 0x00802000L,
    0x00002080L, 0x00800080L, 0x00800081L, 0x00000001L,
    0x00802001L, 0x00002081L, 0x00002081L, 0x00000080L,
    0x00802081L, 0x00000081L, 0x00000001L, 0x00002000L,
    0x00800001L, 0x00002001L, 0x00802080L, 0x00800081L,
    0x00002001L, 0x00002080L, 0x00800000L, 0x00802001L,
    0x00000080L, 0x00800000L, 0x00002000L, 0x00802080L
]

SP5 = [
    0x00000100L, 0x02080100L, 0x02080000L, 0x42000100L,
    0x00080000L, 0x00000100L, 0x40000000L, 0x02080000L,
    0x40080100L, 0x00080000L, 0x02000100L, 0x40080100L,
    0x42000100L, 0x42080000L, 0x00080100L, 0x40000000L,
    0x02000000L, 0x40080000L, 0x40080000L, 0x00000000L,
    0x40000100L, 0x42080100L, 0x42080100L, 0x02000100L,
    0x42080000L, 0x40000100L, 0x00000000L, 0x42000000L,
    0x02080100L, 0x02000000L, 0x42000000L, 0x00080100L,
    0x00080000L, 0x42000100L, 0x00000100L, 0x02000000L,
    0x40000000L, 0x02080000L, 0x42000100L, 0x40080100L,
    0x02000100L, 0x40000000L, 0x42080000L, 0x02080100L,
    0x40080100L, 0x00000100L, 0x02000000L, 0x42080000L,
    0x42080100L, 0x00080100L, 0x42000000L, 0x42080100L,
    0x02080000L, 0x00000000L, 0x40080000L, 0x42000000L,
    0x00080100L, 0x02000100L, 0x40000100L, 0x00080000L,
    0x00000000L, 0x40080000L, 0x02080100L, 0x40000100L
]

SP6 = [
    0x20000010L, 0x20400000L, 0x00004000L, 0x20404010L,
    0x20400000L, 0x00000010L, 0x20404010L, 0x00400000L,
    0x20004000L, 0x00404010L, 0x00400000L, 0x20000010L,
    0x00400010L, 0x20004000L, 0x20000000L, 0x00004010L,
    0x00000000L, 0x00400010L, 0x20004010L, 0x00004000L,
    0x00404000L, 0x20004010L, 0x00000010L, 0x20400010L,
    0x20400010L, 0x00000000L, 0x00404010L, 0x20404000L,
    0x00004010L, 0x00404000L, 0x20404000L, 0x20000000L,
    0x20004000L, 0x00000010L, 0x20400010L, 0x00404000L,
    0x20404010L, 0x00400000L, 0x00004010L, 0x20000010L,
    0x00400000L, 0x20004000L, 0x20000000L, 0x00004010L,
    0x20000010L, 0x20404010L, 0x00404000L, 0x20400000L,
    0x00404010L, 0x20404000L, 0x00000000L, 0x20400010L,
    0x00000010L, 0x00004000L, 0x20400000L, 0x00404010L,
    0x00004000L, 0x00400010L, 0x20004010L, 0x00000000L,
    0x20404000L, 0x20000000L, 0x00400010L, 0x20004010L
]

SP7 = [
    0x00200000L, 0x04200002L, 0x04000802L, 0x00000000L,
    0x00000800L, 0x04000802L, 0x00200802L, 0x04200800L,
    0x04200802L, 0x00200000L, 0x00000000L, 0x04000002L,
    0x00000002L, 0x04000000L, 0x04200002L, 0x00000802L,
    0x04000800L, 0x00200802L, 0x00200002L, 0x04000800L,
    0x04000002L, 0x04200000L, 0x04200800L, 0x00200002L,
    0x04200000L, 0x00000800L, 0x00000802L, 0x04200802L,
    0x00200800L, 0x00000002L, 0x04000000L, 0x00200800L,
    0x04000000L, 0x00200800L, 0x00200000L, 0x04000802L,
    0x04000802L, 0x04200002L, 0x04200002L, 0x00000002L,
    0x00200002L, 0x04000000L, 0x04000800L, 0x00200000L,
    0x04200800L, 0x00000802L, 0x00200802L, 0x04200800L,
    0x00000802L, 0x04000002L, 0x04200802L, 0x04200000L,
    0x00200800L, 0x00000000L, 0x00000002L, 0x04200802L,
    0x00000000L, 0x00200802L, 0x04200000L, 0x00000800L,
    0x04000002L, 0x04000800L, 0x00000800L, 0x00200002L
]

SP8 = [
    0x10001040L, 0x00001000L, 0x00040000L, 0x10041040L,
    0x10000000L, 0x10001040L, 0x00000040L, 0x10000000L,
    0x00040040L, 0x10040000L, 0x10041040L, 0x00041000L,
    0x10041000L, 0x00041040L, 0x00001000L, 0x00000040L,
    0x10040000L, 0x10000040L, 0x10001000L, 0x00001040L,
    0x00041000L, 0x00040040L, 0x10040040L, 0x10041000L,
    0x00001040L, 0x00000000L, 0x00000000L, 0x10040040L,
    0x10000040L, 0x10001000L, 0x00041040L, 0x00040000L,
    0x00041040L, 0x00040000L, 0x10041000L, 0x00001000L,
    0x00000040L, 0x10040040L, 0x00001000L, 0x00041040L,
    0x10001000L, 0x00000040L, 0x10000040L, 0x10040000L,
    0x10040040L, 0x10000000L, 0x00040000L, 0x10001040L,
    0x00000000L, 0x10041040L, 0x00040040L, 0x10000040L,
    0x10040000L, 0x10001000L, 0x10001040L, 0x00000000L,
    0x10041040L, 0x00041000L, 0x00041000L, 0x00001040L,
    0x00001040L, 0x00040040L, 0x10000000L, 0x10041000L
]


def desfunc(block, keys):
    (leftt, right) = unpack('>II', block)
  
    work = ((leftt >> 4) ^ right) & 0x0f0f0f0fL
    right ^= work
    leftt ^= (work << 4)
    work = ((leftt >> 16) ^ right) & 0x0000ffffL
    right ^= work
    leftt ^= (work << 16)
    work = ((right >> 2) ^ leftt) & 0x33333333L
    leftt ^= work
    right ^= (work << 2)
    work = ((right >> 8) ^ leftt) & 0x00ff00ffL
    leftt ^= work
    right ^= (work << 8)
    right = ((right << 1) | ((right >> 31) & 1L)) & 0xffffffffL
    work = (leftt ^ right) & 0xaaaaaaaaL
    leftt ^= work
    right ^= work
    leftt = ((leftt << 1) | ((leftt >> 31) & 1L)) & 0xffffffffL

    for i in range(0, 32, 4):
        work = (right << 28) | (right >> 4)
        work ^= keys[i]
        fval = SP7[work & 0x3fL]
        fval |= SP5[(work >> 8) & 0x3fL]
        fval |= SP3[(work >> 16) & 0x3fL]
        fval |= SP1[(work >> 24) & 0x3fL]
        work = right ^ keys[i+1]
        fval |= SP8[work & 0x3fL]
        fval |= SP6[(work >> 8) & 0x3fL]
        fval |= SP4[(work >> 16) & 0x3fL]
        fval |= SP2[(work >> 24) & 0x3fL]
        leftt ^= fval
        work = (leftt << 28) | (leftt >> 4)
        work ^= keys[i+2]
        fval = SP7[work & 0x3fL]
        fval |= SP5[(work >> 8) & 0x3fL]
        fval |= SP3[(work >> 16) & 0x3fL]
        fval |= SP1[(work >> 24) & 0x3fL]
        work = leftt ^ keys[i+3]
        fval |= SP8[work & 0x3fL]
        fval |= SP6[(work >> 8) & 0x3fL]
        fval |= SP4[(work >> 16) & 0x3fL]
        fval |= SP2[(work >> 24) & 0x3fL]
        right ^= fval

    right = (right << 31) | (right >> 1)
    work = (leftt ^ right) & 0xaaaaaaaaL
    leftt ^= work
    right ^= work
    leftt = (leftt << 31) | (leftt >> 1)
    work = ((leftt >> 8) ^ right) & 0x00ff00ffL
    right ^= work
    leftt ^= (work << 8)
    work = ((leftt >> 2) ^ right) & 0x33333333L
    right ^= work
    leftt ^= (work << 2)
    work = ((right >> 16) ^ leftt) & 0x0000ffffL
    leftt ^= work
    right ^= (work << 16)
    work = ((right >> 4) ^ leftt) & 0x0f0f0f0fL
    leftt ^= work
    right ^= (work << 4)

    leftt &= 0xffffffffL
    right &= 0xffffffffL
    return pack('>II', right, leftt)


def get_vnc_enc(password):
    passpadd = (password + '\x00'*8)[:8]
    strkey = ''.join([chr(x) for x in vnckey])
    ekey = deskey(strkey, False)

    ctext = desfunc(passpadd, ekey)
    return ctext.encode('hex')


class ForkedPdb(pdb.Pdb):
    """A Pdb subclass that may be used
    from a forked multiprocessing child

    """
    def interaction(self, *args, **kwargs):
        _stdin = sys.stdin
        try:
            sys.stdin = file('/dev/stdin')
            pdb.Pdb.interaction(self, *args, **kwargs)
        finally:
            sys.stdin = _stdin
