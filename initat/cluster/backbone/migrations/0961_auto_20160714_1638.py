# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-14 14:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0960_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='ui_theme_selection',
            field=models.CharField(default=b'default', max_length=64),
        ),
    ]
