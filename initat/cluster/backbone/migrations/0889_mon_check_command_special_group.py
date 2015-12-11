# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0888_auto_20151202_2227'),
    ]

    operations = [
        migrations.AddField(
            model_name='mon_check_command_special',
            name='group',
            field=models.CharField(default=b'', max_length=64),
        ),
    ]
