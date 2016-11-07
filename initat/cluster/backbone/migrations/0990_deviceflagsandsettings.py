# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-03 12:36
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0989_auto_20161031_2005'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceFlagsAndSettings',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('graph_enslavement_start', models.DateTimeField(null=True)),
                ('device', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='flags_and_settings', to='backbone.device')),
            ],
        ),
    ]