# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0864_ensure_cluster_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='network_device_type',
            name='auto_created',
            field=models.BooleanField(default=False),
        ),
    ]
