# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0895_netdevice_desired_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='netdevice',
            name='ignore_netdevice_speed',
            field=models.BooleanField(default=False),
        ),
    ]
