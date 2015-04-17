# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.db import migrations
from initat.cluster.backbone.models import device


def migrate_kernel_image(apps, schema_editor):
    VERS_RE = re.compile("^(?P<version>\d+)\.(?P<release>\d+)$")
    for _dev in device.objects.all():
        if _dev.act_kernel_id and _dev.act_image_id:
            # only handle cases where act_image and act_kernel are set
            dbh = _dev.create_boot_history()
            _kh = _dev.act_kernel.create_history_entry(dbh)
            kvm = VERS_RE.match(_dev.kernelversion)
            if kvm:
                _kh.version = int(kvm.group("version"))
                _kh.release = int(kvm.group("release"))
                _kh.save()
            _ih = _dev.act_image.create_history_entry(dbh)
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
