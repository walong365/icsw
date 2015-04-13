# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
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
""" setup models (kernel, image, architecture) for NOCTUA and CORVUS """

from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
import logging_tools

__all__ = [
    "architecture",
    "image",
    "kernel",
    "initrd_build",
    "kernel_build",
    "kernel_local_info",
    "kernel_log",
]


class architecture(models.Model):
    idx = models.AutoField(db_column="architecture_idx", primary_key=True)
    architecture = models.CharField(default="", unique=True, max_length=128)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'architecture'


class image(models.Model):
    idx = models.AutoField(db_column="image_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=True, unique=True)
    source = models.CharField(max_length=384, blank=True)
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=0)
    builds = models.IntegerField(null=True, blank=True, default=0)
    build_machine = models.CharField(max_length=192, blank=True, default="")
    # not a foreign key to break cyclic dependencies
    # device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    # size in Byte
    size = models.BigIntegerField(default=0)
    size_string = models.TextField(blank=True, default="")
    sys_vendor = models.CharField(max_length=192, blank=True)
    sys_version = models.CharField(max_length=192, blank=True)
    sys_release = models.CharField(max_length=192, blank=True)
    bitcount = models.IntegerField(null=True, blank=True)
    architecture = models.ForeignKey("architecture")
    full_build = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = u'image'
        ordering = ("name",)


class kernel(models.Model):
    idx = models.AutoField(db_column="kernel_idx", primary_key=True)
    name = models.CharField(max_length=384)
    kernel_version = models.CharField(max_length=384)
    major = models.CharField(max_length=192, blank=True)
    minor = models.CharField(max_length=192, blank=True)
    patchlevel = models.CharField(max_length=192, blank=True)
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=1)
    builds = models.IntegerField(null=True, blank=True, default=0)
    build_machine = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    # master_server = models.ForeignKey("device", null=True, related_name="master_server")
    master_server = models.IntegerField(null=True)
    master_role = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    # device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    config_name = models.CharField(max_length=192, blank=True)
    cpu_arch = models.CharField(max_length=192, blank=True)
    sub_cpu_arch = models.CharField(max_length=192, blank=True)
    target_dir = models.CharField(max_length=765, blank=True)
    comment = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=False)
    initrd_version = models.IntegerField(null=True, blank=True)
    initrd_built = models.DateTimeField(null=True, blank=True)
    # which modules are actually built into initrd
    module_list = models.TextField(blank=True)
    # which modules are requested
    target_module_list = models.TextField(blank=True, default="")
    xen_host_kernel = models.NullBooleanField(default=False)
    xen_guest_kernel = models.NullBooleanField(default=False)
    bitcount = models.IntegerField(null=True, blank=True)
    stage1_lo_present = models.BooleanField(default=False)
    stage1_cpio_present = models.BooleanField(default=False)
    stage1_cramfs_present = models.BooleanField(default=False)
    stage2_present = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel'


class initrd_build(models.Model):
    idx = models.AutoField(primary_key=True)
    kernel = models.ForeignKey("kernel")
    user_name = models.CharField(max_length=128, default="root")
    # run_time in seconds
    run_time = models.IntegerField(default=0)
    success = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class kernel_build(models.Model):
    idx = models.AutoField(db_column="kernel_build_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    build_machine = models.CharField(max_length=192, blank=True)
    device = models.ForeignKey("device", null=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel_build'


class kernel_local_info(models.Model):
    idx = models.AutoField(db_column="kernel_local_info_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    info_blob = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel_local_info'


class kernel_log(models.Model):
    idx = models.AutoField(db_column="kernel_log_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    log_str = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel_log'
