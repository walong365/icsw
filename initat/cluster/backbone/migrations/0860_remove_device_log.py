# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0859_rmsjobvariable_rms_job_run'),
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
        migrations.DeleteModel(
            name='devicelog',
        ),
    ]
