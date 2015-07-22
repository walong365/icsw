# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0847_increase_netdevice_speed_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensorthresholdaction',
            name='triggered',
            field=models.BooleanField(default=False),
        ),
    ]
