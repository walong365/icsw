# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" setup models (kernel, image, architecture) for NOCTUA and CORVUS """

from __future__ import unicode_literals, print_function

import datetime
import os

from django.db import models
from django.db.models import signals, Q
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import cluster_timezone
from initat.tools import logging_tools, process_tools

__all__ = [
    b"architecture",
    b"image",
    b"kernel",
    b"initrd_build",
    b"kernel_build",
    b"kernel_local_info",
    b"kernel_log",
    b"KernelDeviceHistory",
    b"ImageDeviceHistory",
    b"PopulateRamdiskCmdLine",
]


class architecture(models.Model):
    idx = models.AutoField(db_column="architecture_idx", primary_key=True)
    architecture = models.CharField(default="", unique=True, max_length=128)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'architecture'
        verbose_name = u"Architecture"

    def __unicode__(self):
        return self.architecture


class HistoryObject(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    device_boot_history = models.ForeignKey("backbone.DeviceBootHistory")
    # copy from kernel / image field
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=1)
    success = models.BooleanField(default=False)
    start = models.DateTimeField(auto_now_add=True, null=True)
    end = models.DateTimeField(default=None, null=True)
    date = models.DateTimeField(auto_now_add=True)

    @property
    def full_version(self):
        return "{:d}.{:d}".format(self.version, self.release)

    @property
    def timespan(self):
        if self.start and self.end:
            return logging_tools.get_diff_time_str((self.end - self.start).total_seconds())
        else:
            return "---"

    def ok(self):
        self.end = cluster_timezone.localize(datetime.datetime.now())
        self.success = True
        self.save(update_fields=["end", "success"])

    class Meta:
        abstract = True
        ordering = ("-pk",)


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

    @property
    def full_version(self):
        return "{:d}.{:d}".format(self.version, self.release)

    def create_history_entry(self, _dbh):
        _kdh = ImageDeviceHistory.objects.create(
            image=self,
            device=_dbh.device,
            device_boot_history=_dbh,
            version=self.version,
            release=self.release,
        )
        return _kdh

    class CSW_Meta:
        permissions = (
            ("modify_images", "modify images", False),
        )

    @staticmethod
    def take_image(xml_wrapper, srv_result, img_name, logger=None):
        if srv_result is None:
            xml_wrapper.error("invalid server response")
            return
        try:
            _cur_img = image.objects.get(Q(name=img_name))
        except image.DoesNotExist:
            img_xml = srv_result.xpath(".//ns:image[text() = '{}']".format(img_name), smart_strings=False)
            if len(img_xml):
                img_xml = img_xml[0]
                if "arch" not in img_xml.attrib:
                    xml_wrapper.error(
                        "no architecture-attribute found in image",
                        logger
                    )
                else:
                    try:
                        img_arch = architecture.objects.get(Q(architecture=img_xml.attrib["arch"]))
                    except architecture.DoesNotExist:
                        img_arch = architecture(
                            architecture=img_xml.attrib["arch"])
                        img_arch.save()
                    img_source = srv_result.xpath(".//ns:image_list/@image_dir", smart_strings=False)[0]
                    version_tuple = img_xml.attrib["version"].split(".", 1)
                    if len(version_tuple) == 2:
                        sys_version, sys_release = version_tuple
                    else:
                        sys_version, sys_release = "", ""
                    new_img = image(
                        name=img_xml.text,
                        source=os.path.join(img_source, img_xml.text),
                        sys_vendor=img_xml.attrib["vendor"],
                        sys_version=sys_version,
                        sys_release=sys_release,
                        bitcount=img_xml.attrib["bitcount"],
                        architecture=img_arch,
                    )
                    try:
                        new_img.save()
                    except:
                        xml_wrapper.error(
                            "cannot create image: {}".format(process_tools.get_except_info()),
                            logger
                        )
                    else:
                        xml_wrapper.info("image taken", logger)
            else:
                xml_wrapper.error("image has vanished ?", logger)
        else:
            xml_wrapper.error("image already exists", logger)

    def __unicode__(self):
        return "Image {} ({}, arch={})".format(self.name, self.full_version, unicode(self.architecture))

    class Meta:
        db_table = u'image'
        ordering = ("name",)
        verbose_name = u"Image"


class ImageDeviceHistory(HistoryObject):
    image = models.ForeignKey("backbone.image")


@receiver(signals.pre_save, sender=image)
def image_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.size_string = logging_tools.get_size_str(cur_inst.size)


class kernel(models.Model):
    idx = models.AutoField(db_column="kernel_idx", primary_key=True)
    # display (and directory name), should be unique
    display_name = models.CharField(max_length=128, default="")
    # real kernel name (== subdir in lib/modules)
    name = models.CharField(max_length=384, default="")
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

    def get_usecount(self):
        return 0

    def create_history_entry(self, _dbh):
        _kdh = KernelDeviceHistory.objects.create(
            kernel=self,
            device=_dbh.device,
            device_boot_history=_dbh,
            version=self.version,
            release=self.release,
        )
        return _kdh

    class Meta:
        db_table = u'kernel'
        verbose_name = u"Kernel"
        ordering = ("display_name", "pk",)

    @property
    def full_version(self):
        return "{:d}.{:d}".format(self.version, self.release)

    def __unicode__(self):
        return "Kernel {} (is {}, {})".format(self.display_name, self.name, self.full_version)

    class CSW_Meta:
        permissions = (
            ("modify_kernels", "modify kernels", False),
        )
        fk_ignore_list = ["initrd_build", "kernel_build"]


class KernelDeviceHistory(HistoryObject):
    kernel = models.ForeignKey("backbone.kernel")


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


class PopulateRamdiskCmdLine(models.Model):
    idx = models.AutoField(db_column="kernel_log_idx", primary_key=True)
    # calling user
    user = models.CharField(max_length=256, default="")
    # device
    machine = models.CharField(max_length=256, default="")
    # command line
    cmdline = models.TextField(default="")
    kernel = models.ForeignKey("backbone.kernel")
    date = models.DateTimeField(auto_now_add=True)
