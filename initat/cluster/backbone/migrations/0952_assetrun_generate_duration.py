# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-03 14:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0951_auto_20160607_1355'),
    ]

    operations = [
        migrations.AddField(
            model_name='assetrun',
            name='generate_duration',
            field=models.FloatField(default=0.0),
        ),
    ]