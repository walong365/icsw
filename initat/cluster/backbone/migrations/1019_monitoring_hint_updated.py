# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-08 07:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1018_devicelogentry_read_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='monitoring_hint',
            name='updated',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
