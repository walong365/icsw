# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0874_auto_20151007_1524'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphSettingForecast',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', unique=True, max_length=64)),
                ('seconds', models.IntegerField(default=0, unique=True)),
                ('mode', models.CharField(default=b'sl', max_length=4, choices=[(b'sl', b'simple linear')])),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='graphsetting',
            name='graph_setting_forecast',
            field=models.ForeignKey(blank=True, to='backbone.GraphSettingForecast', null=True),
        ),
    ]
