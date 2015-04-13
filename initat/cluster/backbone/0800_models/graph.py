# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" graph models for NOCTUA, CORVUS and NESTOR """

from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
import logging_tools

__all__ = [
    "MachineVector",
    "MVStructEntry",
    "MVValueEntry",
]


class MachineVector(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to device
    device = models.ForeignKey("device")
    # src_file name, for later reference
    src_file_name = models.CharField(max_length=256, default="", blank=True)
    # directory under cache_dir, in most cases the UUID
    dir_name = models.CharField(max_length=128, default="")
    date = models.DateTimeField(auto_now_add=True)


class MVStructEntry(models.Model):
    # structural entry for machine_vector, references an RRD-file on disk
    idx = models.AutoField(primary_key=True)
    machine_vector = models.ForeignKey("MachineVector")
    file_name = models.CharField(max_length=256, default="")
    # needed ?
    se_type = models.CharField(
        max_length=6,
        choices=[
            ("pde", "pde"),
            ("mvl", "mvl"),
            ("mve", "mve"),
        ],
    )
    # we ignore the 'host' field for pdes because it seems to be a relict from the original PerformanceData sent from icinga
    # info is set for mvl structural entries, is now ignored
    # info = models.CharField(max_length=256, default="")
    # type instance is set for certains PDEs (for instance windows disk [C,D,E,...], SNMP netifaces [eth0,eth1,...])
    type_instance = models.CharField(max_length=16, default="")
    # position in RRD-tree this nodes resides in, was name
    key = models.CharField(max_length=256)
    # is active
    is_active = models.BooleanField(default=True)
    # last update
    last_update = models.DateTimeField(auto_now=True)
    # was init_time
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("key",)


class MVValueEntry(models.Model):
    # value entry for machine_vector
    idx = models.AutoField(primary_key=True)
    mv_struct_entry = models.ForeignKey("MVStructEntry")
    # base for generating {k,M,G,T} values, in most cases 1000 or 1024
    base = models.IntegerField(default=1024)
    # factor, a simple multiplicator to get to a sane value (in most cases 1)
    factor = models.IntegerField(default=1)
    # unit
    unit = models.CharField(max_length=16, default="")
    # variable type
    v_type = models.CharField(max_length=3, choices=[("i", "int"), ("f", "float")], default="f")
    # info string
    info = models.CharField(max_length=256, default="")
    # key, string describing the last part of the position (was also called name), not necessarily a single value
    # (for instance request.time.connect for HTTP perfdata)
    # the full key is mv_struct_entry.key + "." + mv_value.key
    # may be empty in case of mve entries (full key is stored in mv_struct_entry)
    key = models.CharField(max_length=128, default="")
    # full key for this value, stored for faster reference
    full_key = models.CharField(max_length=128, default="")
    # we don't store the name which was the last part of key
    # we also don't store the index because this fields was omitted some time ago (still present in some XMLs)
    # full is also not stored because full is always equal to name
    # sane_name is also ignored because this is handled by collectd to generate filesystem-safe filenames ('/' -> '_sl_')
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("key",)
