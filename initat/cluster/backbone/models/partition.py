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
""" model definitions, partitions """

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_integer
import logging_tools
import re

__all__ = [
    "partition_fs",
    "sys_partition",
    "lvm_lv",
    "lvm_vg",
    "partition",
    "partition_disc",
    "partition_table",
]


class partition_fs(models.Model):
    # mix of partition and fs info, not perfect ...
    idx = models.AutoField(db_column="partition_fs_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=48)
    identifier = models.CharField(max_length=3)
    descr = models.CharField(max_length=765, blank=True)
    hexid = models.CharField(max_length=6)
    # none, one or more (space sepearted) kernel modules needed for ths fs
    kernel_module = models.CharField(max_length=128, default="")
    # flags
    date = models.DateTimeField(auto_now_add=True)

    def need_mountpoint(self):
        return True if self.hexid in ["83"] else False

    def __unicode__(self):
        return self.descr

    class CSW_Meta:
        permissions = (
            ("modify_paritions", "modify partitions", False),
        )
        fk_ignore_list = ["initrd_build", "kernel_build"]

    class Meta:
        db_table = u'partition_fs'
        ordering = ("name",)


class sys_partition(models.Model):
    idx = models.AutoField(db_column="sys_partition_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    name = models.CharField(max_length=192)
    mountpoint = models.CharField(max_length=192, default="/")
    mount_options = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'sys_partition'


class lvm_lv(models.Model):
    idx = models.AutoField(db_column="lvm_lv_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    lvm_vg = models.ForeignKey("backbone.lvm_vg")
    size = models.BigIntegerField(null=True, blank=True)
    mountpoint = models.CharField(max_length=192, default="/")
    mount_options = models.CharField(max_length=384, blank=True)
    fs_freq = models.IntegerField(null=True, blank=True)
    fs_passno = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192)
    partition_fs = models.ForeignKey("backbone.partition_fs")
    warn_threshold = models.IntegerField(null=True, blank=True, default=85)
    crit_threshold = models.IntegerField(null=True, blank=True, default=95)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'lvm_lv'
        ordering = ("name",)


@receiver(signals.pre_save, sender=lvm_lv)
def lvm_lv_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "warn_threshold", none_to_zero=True, min_val=0, max_val=100)
        _check_integer(cur_inst, "crit_threshold", none_to_zero=True, min_val=0, max_val=100)
        # fs_freq
        _check_integer(cur_inst, "fs_freq", min_val=0, max_val=1)
        # fs_passno
        _check_integer(cur_inst, "fs_passno", min_val=0, max_val=2)


class lvm_vg(models.Model):
    idx = models.AutoField(db_column="lvm_vg_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    name = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'lvm_vg'
        ordering = ("name",)


class partition(models.Model):
    idx = models.AutoField(db_column="partition_idx", primary_key=True)
    partition_disc = models.ForeignKey("backbone.partition_disc")
    mountpoint = models.CharField(max_length=192, default="/", blank=True)
    partition_hex = models.CharField(max_length=6, blank=True)
    size = models.IntegerField(null=True, blank=True, default=100)
    mount_options = models.CharField(max_length=255, blank=True, default="defaults")
    pnum = models.IntegerField()
    bootable = models.BooleanField(default=False)
    fs_freq = models.IntegerField(null=True, blank=True, default=0)
    fs_passno = models.IntegerField(null=True, blank=True, default=0)
    partition_fs = models.ForeignKey("backbone.partition_fs")
    # lut_blob = models.TextField(blank=True, null=True)
    # comma-delimited list of /dev/disk/by-* entries
    disk_by_info = models.TextField(default="", blank=True)
    warn_threshold = models.IntegerField(null=True, blank=True, default=85)
    crit_threshold = models.IntegerField(null=True, blank=True, default=95)
    date = models.DateTimeField(auto_now_add=True)

    def _validate(self, p_disc):
        p_list = []
        p_name = "{}{:d}".format(p_disc, self.pnum)
        if not self.partition_fs_id:
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "no partition_fs set ({})".format(p_name), False))
        else:
            if self.partition_fs.hexid == "0" and self.partition_fs.name == "empty":
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "empty partitionf_fs ({})".format(p_name), False))
            if self.partition_fs.need_mountpoint():
                if not self.mountpoint.startswith("/"):
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no mountpoint defined for {}".format(p_name), False))
                if not self.mount_options.strip():
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no mount_options given for {}".format(p_name), False))
        return p_list

    class Meta:
        db_table = u'partition'
        ordering = ("pnum",)


@receiver(signals.pre_save, sender=partition)
def partition_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        p_num = cur_inst.pnum
        if isinstance(p_num, basestring):
            if not p_num.strip():
                p_num = "0"
        try:
            p_num = int(p_num)
        except:
            raise ValidationError("partition number '{}' not parseable".format(p_num))
        if p_num == 0:
            if partition.objects.filter(Q(partition_disc=cur_inst.partition_disc)).count() > 1:
                raise ValidationError("for pnum==0 only one partition is allowed")
        elif p_num < 1 or p_num > 32:
            raise ValidationError("partition number {:d} out of bounds [1, 32]".format(p_num))
        all_part_nums = partition.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_disc=cur_inst.partition_disc)).values_list("pnum", flat=True)
        if p_num in all_part_nums:
            raise ValidationError("partition number already used")
        cur_inst.pnum = p_num
        # size
        _check_integer(cur_inst, "size", min_val=0)
        _check_integer(cur_inst, "warn_threshold", none_to_zero=True, min_val=0, max_val=100)
        _check_integer(cur_inst, "crit_threshold", none_to_zero=True, min_val=0, max_val=100)
        # mountpoint
        if cur_inst.partition_fs.need_mountpoint():
            if cur_inst.mountpoint.strip() and not cur_inst.mountpoint.startswith("/"):
                raise ValidationError("mountpoint must start with '/'")
        # fs_freq
        _check_integer(cur_inst, "fs_freq", min_val=0, max_val=1)
        # fs_passno
        _check_integer(cur_inst, "fs_passno", min_val=0, max_val=2)
        if cur_inst.partition_fs_id:
            if cur_inst.partition_fs.name == "swap":
                cur_inst.mountpoint = "swap"
            if not cur_inst.partition_fs.need_mountpoint():
                cur_inst.mountpoint = ""
            cur_inst.partition_hex = cur_inst.partition_fs.hexid


class partition_disc(models.Model):
    idx = models.AutoField(db_column="partition_disc_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    disc = models.CharField(max_length=192)
    label_type = models.CharField(max_length=128, default="gpt", choices=[("gpt", "GPT"), ("msdos", "MSDOS")])
    priority = models.IntegerField(null=True, default=0)
    date = models.DateTimeField(auto_now_add=True)

    def _validate(self):
        my_parts = self.partition_set.all()
        p_list = sum([[(cur_lev, "*{:d} : {}".format(part.pnum, msg), flag) for cur_lev, msg, flag in part._validate(self)] for part in my_parts], [])
        all_mps = [cur_mp.mountpoint for cur_mp in my_parts if cur_mp.mountpoint.strip() and cur_mp.mountpoint.strip() != "swap"]
        if len(all_mps) != len(set(all_mps)):
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "mountpoints not unque", False))
        if all_mps:
            if "/usr" in all_mps:
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "cannot boot when /usr is on a separate partition", False))
        ext_parts = [cur_p for cur_p in my_parts if cur_p.partition_fs_id and cur_p.partition_fs.name == "ext"]
        if my_parts:
            max_pnum = max([cur_p.pnum for cur_p in my_parts])
            if self.label_type == "msdos":
                # msdos label validation path
                if len(ext_parts) == 0:
                    if max_pnum > 4:
                        p_list.append((logging_tools.LOG_LEVEL_ERROR, "too many partitions ({:d}), only 4 without ext allowed".format(max_pnum), False))
                elif len(ext_parts) > 1:
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "too many ext partitions ({:d}) defined".format(len(ext_parts)), False))
                else:
                    ext_part = ext_parts[0]
                    if ext_part.pnum != 4:
                        p_list.append((logging_tools.LOG_LEVEL_ERROR, "extended partition must have pnum 4", False))
            else:
                # gpt label validation path
                if len(ext_parts):
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no extended partitions allowed for GPT label", False))
        return p_list

    class Meta:
        db_table = u'partition_disc'
        ordering = ("priority", "disc",)

    def __unicode__(self):
        return self.disc


@receiver(signals.pre_save, sender=partition_disc)
def partition_disc_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        disc_re = re.compile("^/dev/([shv]d[a-z]|dm-(\d+)|mapper/.*|ida/(.*)|cciss/(.*))$")
        cur_inst = kwargs["instance"]
        d_name = cur_inst.disc.strip().lower()
        if not d_name:
            raise ValidationError("name must not be zero")
        if not disc_re.match(d_name):
            raise ValidationError("illegal name '{}'".format(d_name))
        all_discs = partition_disc.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_table=cur_inst.partition_table)).values_list("disc", flat=True)
        if d_name in all_discs:
            raise ValidationError("disc name '{}' already used".format(d_name))
        cur_inst.disc = d_name


class partition_table(models.Model):
    idx = models.AutoField(db_column="partition_table_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=255, blank=True, default="")
    enabled = models.BooleanField(default=True)
    valid = models.BooleanField(default=False)
    modify_bootloader = models.IntegerField(default=0)
    nodeboot = models.BooleanField(default=False)
    # non users-created partition tables can be deleted automatically
    user_created = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    def _msg_merge(self, parent, msg):
        if msg.startswith("*"):
            return "{}{}".format(parent, msg[1:])
        else:
            return "{}: {}".format(parent, msg)

    def validate(self):
        # problem list, format is level, problem, global (always True for partition_table)
        prob_list = []
        if not self.partition_disc_set.all():
            prob_list.append((logging_tools.LOG_LEVEL_ERROR, "no discs defined", True))
        prob_list.extend(
            sum([
                [
                    (cur_lev, self._msg_merge(p_disc.disc, msg), flag) for cur_lev, msg, flag in p_disc._validate()
                ] for p_disc in self.partition_disc_set.all()
            ], [])
        )
        all_mps = sum(
            [
                [
                    cur_p.mountpoint for cur_p in p_disc.partition_set.all() if cur_p.mountpoint.strip() and (
                        cur_p.partition_fs_id and cur_p.partition_fs.need_mountpoint()
                    )
                ] for p_disc in self.partition_disc_set.all()
            ],
            []
        )
        all_mps.extend([sys_p.mountpoint for sys_p in self.sys_partition_set.all()])
        unique_mps = set(all_mps)
        for non_unique_mp in sorted([name for name in unique_mps if all_mps.count(name) > 1]):
            prob_list.append(
                (logging_tools.LOG_LEVEL_ERROR, "mountpoint '{}' is not unique ({:d})".format(
                    non_unique_mp,
                    all_mps.count(name),
                ), True)
                )
        if u"/" not in all_mps:
            prob_list.append(
                (logging_tools.LOG_LEVEL_ERROR, "no '/' mountpoint defined", True)
                )
        new_valid = not any([log_level in [
            logging_tools.LOG_LEVEL_ERROR,
            logging_tools.LOG_LEVEL_CRITICAL] for log_level, _what, _is_global in prob_list])
        # validate
        if new_valid != self.valid:
            self.valid = new_valid
            self.save()
        return prob_list

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'partition_table'

    class CSW_Meta:
        fk_ignore_list = ["partition_disc", "sys_partition", "lvm_lv", "lvm_vg"]


@receiver(signals.pre_save, sender=partition_table)
def partition_table_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
