# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-14 05:02
from __future__ import unicode_literals

from django.db import migrations
import json
import uuid


def add_device_variable_uuids(apps, schema_editor):
    device_variable = apps.get_model("backbone", "device_variable")
    for entry in device_variable.objects.all():
        # create uuid (signals not working here)
        # entry.prefix = "normal"
        entry.uuid = str(uuid.uuid4())
        entry.save()


def dummy_reverse(apps, schema_editor):
    pass


def add_device_variable_scopes(apps, schema_editor):
    device_variable_scope = apps.get_model("backbone", "device_variable_scope")
    device_variable_scope.objects.create(
        name="normal",
        prefix="",
    )
    device_variable_scope.objects.create(
        name="inventory",
        prefix="__$$ICSW_INV$__",
        forced_flags=json.dumps(
            {
                "local_copy_ok": False,
                "inherit": False,
            }
        )
    )


def remove_device_variable_scopes(apps, schema_editor):
    device_variable_scope = apps.get_model("backbone", "device_variable_scope")
    device_variable_scope.objects.all().delete()


def set_default_scopes(apps, schema_editor):
    device_variable = apps.get_model("backbone", "device_variable")
    device_variable_scope = apps.get_model("backbone", "device_variable_scope")
    _norm = device_variable_scope.objects.get(name="normal")
    for _dev in device_variable.objects.all():
        if not _dev.device_variable_scope_id:
            _dev.device_variable_scope = _norm
            _dev.save()


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0956_device_variable_uuid'),
    ]

    operations = [
        migrations.RunPython(add_device_variable_uuids, reverse_code=dummy_reverse),
        migrations.RunPython(add_device_variable_scopes, reverse_code=remove_device_variable_scopes),
        migrations.RunPython(set_default_scopes, reverse_code=dummy_reverse),
    ]