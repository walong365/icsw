# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-05 13:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0990_deviceflagsandsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='device_variable_scope',
            name='fixed',
            field=models.BooleanField(default=False),
        ),
    ]
