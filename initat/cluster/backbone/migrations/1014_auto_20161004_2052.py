# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-04 18:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1013_auto_20161004_1600'),
    ]

    operations = [
        migrations.AddField(
            model_name='mon_dist_master',
            name='livestatus_version',
            field=models.CharField(default=b'', max_length=128),
        ),
        migrations.AddField(
            model_name='mon_dist_slave',
            name='livestatus_version',
            field=models.CharField(default=b'', max_length=128),
        ),
    ]