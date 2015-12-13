# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0889_mon_check_command_special_group'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='mon_check_command_special',
            options={'ordering': ('group', 'name'), 'verbose_name': 'Special check command'},
        ),
        migrations.RemoveField(
            model_name='mon_check_command',
            name='mon_check_command_type',
        ),
        migrations.DeleteModel(
            name='mon_check_command_type',
        ),
    ]
