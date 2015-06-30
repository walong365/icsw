# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0841_added_enabled_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensorthreshold',
            name='create_user',
            field=models.ForeignKey(related_name='sensor_threshold_create_user', blank=True, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
    ]
