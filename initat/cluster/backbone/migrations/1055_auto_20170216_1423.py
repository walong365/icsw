# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-16 13:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1054_auto_20170213_1723'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='netdevice',
            name='force_network_device_type_match',
        ),
        migrations.RemoveField(
            model_name='netdevice',
            name='network_device_type',
        ),
        migrations.RemoveField(
            model_name='network',
            name='network_device_type',
        ),
        migrations.AddField(
            model_name='snmp_network_type',
            name='description',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AddField(
            model_name='snmp_network_type',
            name='mac_bytes',
            field=models.PositiveIntegerField(default=6),
        ),
        migrations.AddField(
            model_name='snmp_network_type',
            name='regex',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.DeleteModel(
            name='network_device_type',
        ),
    ]
