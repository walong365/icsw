# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0840_sensorthresholdaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensorthreshold',
            name='lower_enabled',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='upper_enabled',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
    ]
