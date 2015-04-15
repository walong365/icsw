# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0815_migrate_device_type_to_flags'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='device_type',
        ),
        migrations.DeleteModel(
            name='device_type',
        ),
    ]
