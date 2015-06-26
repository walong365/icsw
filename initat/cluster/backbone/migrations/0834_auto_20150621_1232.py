# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0833_added_sensoraction_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='sensoraction',
            old_name='device_action',
            new_name='action',
        ),
        migrations.RenameField(
            model_name='sensorthreshold',
            old_name='action',
            new_name='sensor_action',
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='notify_users',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
