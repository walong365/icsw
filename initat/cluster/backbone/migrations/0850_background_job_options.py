# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0849_auto_20150722_1216'),
    ]

    operations = [
        migrations.AddField(
            model_name='background_job',
            name='options',
            field=models.CharField(default=b'', max_length=256),
        ),
    ]
