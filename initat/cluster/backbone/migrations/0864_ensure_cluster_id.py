# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def ensure_cluster_id(apps, schema_editor):
    device = apps.get_model("backbone", "device")
    try:
        _cdd = device.objects.get(models.Q(device_group__cluster_device_group=True))
    except device.DoesNotExist:
        pass
    else:
        _cdd.save()


def dummy_call(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0863_remove_log_source'),
    ]

    operations = [
        migrations.RunPython(
            ensure_cluster_id,
            dummy_call,
        ),
    ]
