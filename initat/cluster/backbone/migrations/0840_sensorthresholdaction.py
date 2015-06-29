# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0839_mvvalueentry_rra_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorThresholdAction',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('action_type', models.CharField(max_length=12, choices=[(b'lower', b'lower'), (b'upper', b'upper')])),
                ('mail', models.BooleanField(default=False)),
                ('value', models.FloatField(default=0.0)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device_selection', models.ForeignKey(blank=True, to='backbone.DeviceSelection', null=True)),
                ('notify_users', models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
                ('sensor_action', models.ForeignKey(to='backbone.SensorAction')),
                ('sensor_threshold', models.ForeignKey(to='backbone.SensorThreshold')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
