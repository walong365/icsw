# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def remove_device_type(apps, schema_editor):
    device = apps.get_model("backbone", "device")
    for _dev in device.objects.all().select_related("device_type"):
        if _dev.device_type.identifier == "MD" and not _dev.is_meta_device:
            _dev.is_meta_device = True
            _dev.save()


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0814_remove_old_image_and_kernel_fields'),
    ]

    operations = [
        migrations.RunPython(remove_device_type)
    ]
