# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-23 13:22
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0933_auto_20160523_1223'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetProcessEntry',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('pid', models.IntegerField(default=0)),
                ('name', models.CharField(default=b'', max_length=255)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('asset_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetRun')),
            ],
            options={
                'ordering': ('idx',),
            },
        ),
    ]
