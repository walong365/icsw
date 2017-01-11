# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-13 17:37


import uuid

from django.db import migrations, models


def add_device_variable_uuids(apps, schema_editor):
    device_variable = apps.get_model("backbone", "device_variable")
    for entry in device_variable.objects.all():
        # create uuid (signals not working here)
        # entry.prefix = "normal"
        entry.uuid = str(uuid.uuid4())
        entry.save()


def dummy_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0955_remove_device_active_scan'),
    ]

    operations = [
        migrations.CreateModel(
            name='device_variable_scope',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=32, unique=True)),
                ('prefix', models.CharField(default=b'', max_length=127)),
                ('forced_flags', models.CharField(default=b'', max_length=127)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='device_variable',
            name='uuid',
            field=models.TextField(default=b'', max_length=64),
        ),
        migrations.AddField(
            model_name='device_variable',
            name='device_variable_scope',
            field=models.ForeignKey(null=True, on_delete=models.deletion.CASCADE, to='backbone.device_variable_scope'),
        ),
        migrations.AlterUniqueTogether(
            name='device_variable',
            unique_together=set([('name', 'device', "device_variable_scope")]),
        ),
    ]
