# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0856_auto_20150919_0919'),
    ]

    operations = [
        migrations.CreateModel(
            name='RMSJobVariableAction',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', unique=True, max_length=255)),
                ('code', models.TextField(default=b'')),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='RMSJobVariableActionRun',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('run_time', models.FloatField(default=0.0)),
                ('success', models.BooleanField(default=False)),
                ('vars_created', models.IntegerField(default=0)),
                ('triggered_run', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('rms_job', models.ForeignKey(to='backbone.rms_job')),
                ('rms_job_variable_action_run', models.ForeignKey(to='backbone.RMSJobVariableAction')),
            ],
        ),
    ]
