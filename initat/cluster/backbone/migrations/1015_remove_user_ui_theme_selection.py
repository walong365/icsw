# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-14 14:48
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1014_auto_20161213_1340'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='ui_theme_selection',
        ),
    ]