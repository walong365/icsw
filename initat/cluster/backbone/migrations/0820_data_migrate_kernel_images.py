# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.db import migrations


def create_history_entry(obj, dbh):
    _dh = obj(
        device=dbh.device,
        device_boot_history=dbh,
    )
    return _dh


def migrate_kernel_image(apps, schema_editor):
    device = apps.get_model("backbone", "device")
    boot_history = apps.get_model("backbone", "DeviceBootHistory")
    kernel = apps.get_model("backbone", "kernel")
    kernel_hist = apps.get_model("backbone", "KernelDeviceHistory")
    image = apps.get_model("backbone", "image")
    image_hist = apps.get_model("backbone", "ImageDeviceHistory")
    VERS_RE = re.compile("^(?P<version>\d+)\.(?P<release>\d+)$")
    for _dev in device.objects.all():
        if _dev.act_kernel_id and _dev.act_image_id:
            # only handle cases where act_image and act_kernel are set
            dbh = boot_history.objects.create(device=_dev)
            _kh = create_history_entry(kernel_hist, dbh)
            _kh.kernel = _dev.act_kernel
            kvm = VERS_RE.match(_dev.kernelversion)
            if kvm:
                _kh.version = int(kvm.group("version"))
                _kh.release = int(kvm.group("release"))
            _kh.save()
            _ih = create_history_entry(image_hist, dbh)
            _ih.image = _dev.act_image
            ivm = VERS_RE.match(_dev.imageversion)
            if ivm:
                _ih.version = int(ivm.group("version"))
                _ih.release = int(ivm.group("release"))
            _ih.save()


def dummy_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    reversible = True

    dependencies = [
        ('backbone', '0819_add_device_image_history'),
    ]

    operations = [
        migrations.RunPython(migrate_kernel_image, reverse_code=dummy_reverse)
    ]
