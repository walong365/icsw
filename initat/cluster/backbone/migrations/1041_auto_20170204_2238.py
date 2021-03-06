# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-04 15:51

from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1040_auto_20170204_2236'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mon_check_command_special',
            name='dummy_mcc',
        ),
        migrations.RemoveField(
            model_name='mon_check_command_special',
            name='parent',
        ),
        migrations.AlterModelOptions(
            name='icsweggbasket',
            options={'ordering': ('dummy', 'is_valid', 'license', 'license_id_name')},
        ),
        migrations.RemoveField(
            model_name='mon_check_command',
            name='mon_check_command_special',
        ),
        migrations.RemoveField(
            model_name='mon_check_command',
            name='tcp_coverage',
        ),
        migrations.RemoveField(
            model_name='mon_check_command',
            name='special_shadow',
        ),
        migrations.DeleteModel(
            name='mon_check_command_special',
        ),
    ]
