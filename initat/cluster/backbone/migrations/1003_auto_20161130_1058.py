# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-30 09:58
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def forwards_func(apps, schema_editor):
    ScheduleItem = apps.get_model("backbone", "ScheduleItem")

    for schedule_item in ScheduleItem.objects.all():
        schedule_item.model_name = "device"
        schedule_item.object_id = schedule_item.device.idx
        schedule_item.save()

    DeviceDispatcherLink = apps.get_model("backbone", "DeviceDispatcherLink")
    DispatcherLink = apps.get_model("backbone", "DispatcherLink")

    for link in DeviceDispatcherLink.objects.all():
        new_dispatcher_link = DispatcherLink(
            model_name="device",
            object_id=link.device.idx,
            dispatcher_setting=link.dispatcher_setting,
            schedule_handler="asset_schedule_handler",
            user=link.user)
        new_dispatcher_link.save()

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1002_remove_devicelogentry_entry_counter'),
    ]

    operations = [
        migrations.CreateModel(
            name='DispatcherLink',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('model_name', models.TextField()),
                ('object_id', models.IntegerField()),
                ('schedule_handler', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('dispatcher_setting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.DispatcherSetting')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='scheduleitem',
            name='model_name',
            field=models.TextField(default='device'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='scheduleitem',
            name='object_id',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='scheduleitem',
            name='schedule_handler',
            field=models.TextField(default="asset_schedule_handler"),
        ),
        migrations.RunPython(forwards_func, reverse_func)
    ]