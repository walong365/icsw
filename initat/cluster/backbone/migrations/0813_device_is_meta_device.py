# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0812_add_power_control_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='is_meta_device',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
