# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-08 07:37
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1019_monitoring_hint_updated'),
    ]

    operations = [
        migrations.RenameField(
            model_name='monitoring_hint',
            old_name='value_blob',
            new_name='value_json',
        ),
    ]
