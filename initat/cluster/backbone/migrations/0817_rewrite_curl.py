# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def rewrite_curl(apps, schema_editor):
    device = apps.get_model("backbone", "device")
    for _dev in device.objects.all():
        if _dev.curl.lower().startswith("ipmi://") and not _dev.ipmi_capable:
            _dev.curl = ""
            _dev.ipmi_capable = True
            _dev.save()


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0816_remove_device_type'),
    ]

    operations = [
        migrations.RunPython(rewrite_curl)
    ]
