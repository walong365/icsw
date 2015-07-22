# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0848_sensorthresholdaction_triggered'),
    ]

    operations = [
        migrations.AddField(
            model_name='background_job',
            name='num_objects',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='background_job',
            name='result',
            field=models.IntegerField(default=4),
        ),
    ]
