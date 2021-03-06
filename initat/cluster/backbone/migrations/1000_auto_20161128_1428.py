# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-28 13:28


from django.db import migrations, models
from django.db.transaction import atomic


@atomic
def forwards_func(apps, schema_editor):
    DeviceLogEntry = apps.get_model("backbone", "DeviceLogEntry")

    count_per_device = {}
    for entry in DeviceLogEntry.objects.all().order_by('date'):
        if entry.device.idx not in count_per_device:
            count_per_device[entry.device.idx] = 0

        count_per_device[entry.device.idx] += 1

        entry.entry_counter = count_per_device[entry.device.idx]
        entry.save()


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('backbone', '0999_mondisplaypipespec_def_user_var_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicelogentry',
            name='entry_counter',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
        migrations.RunPython(forwards_func, reverse_func)
    ]
