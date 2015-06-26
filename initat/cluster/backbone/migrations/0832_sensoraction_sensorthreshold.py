# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0831_add_mvvalue_entry_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorAction',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=64)),
                ('description', models.CharField(default=b'', max_length=256)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SensorThreshold',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', max_length=64)),
                ('value', models.FloatField(default=0.0)),
                ('hysteresis', models.FloatField(default=0.0)),
                ('limit_class', models.CharField(max_length=2, choices=[(b'u', b'upper'), (b'l', b'lower')])),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('action', models.ForeignKey(to='backbone.SensorAction')),
                ('mv_value_entry', models.ForeignKey(to='backbone.MVValueEntry')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
