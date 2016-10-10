# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-10 10:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1015_auto_20161005_1916'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, b'PACKAGE'), (2, b'HARDWARE'), (3, b'LICENSE'), (4, b'UPDATE'), (5, b'LSHW'), (6, b'PROCESS'), (7, b'PENDING_UPDATE'), (8, b'DMI'), (9, b'PCI'), (10, b'PRETTYWINHW'), (11, b'PARTITION'), (12, b'LSBLK'), (13, b'XRANDR')], default=1),
        ),
    ]
