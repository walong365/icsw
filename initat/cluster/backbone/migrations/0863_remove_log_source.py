# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0862_to_new_device_log'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='devicelog',
            name='device',
        ),
        migrations.RemoveField(
            model_name='devicelog',
            name='log_source',
        ),
        migrations.RemoveField(
            model_name='devicelog',
            name='log_status',
        ),
        migrations.RemoveField(
            model_name='devicelog',
            name='user',
        ),
        migrations.RemoveField(
            model_name='log_source',
            name='device',
        ),
        migrations.RemoveField(
            model_name='background_job_run',
            name='log_source',
        ),
        migrations.RemoveField(
            model_name='macbootlog',
            name='log_source',
        ),
        migrations.DeleteModel(
            name='devicelog',
        ),
        migrations.DeleteModel(
            name='log_source',
        ),
    ]
