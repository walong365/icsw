# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-06 11:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1043_auto_20170205_1544'),
    ]

    operations = [
        migrations.AddField(
            model_name='mon_check_command',
            name='parent_uuid',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
