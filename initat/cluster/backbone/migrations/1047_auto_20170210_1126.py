# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-10 10:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1046_fix_cmdline'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mon_check_command',
            name='exclude_devices',
        ),
    ]
