# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-05 14:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1042_auto_20170205_1537'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='mon_check_command',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='mon_check_command',
            name='config',
        ),
    ]