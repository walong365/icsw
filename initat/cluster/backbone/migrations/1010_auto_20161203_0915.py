# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-03 08:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1009_auto_20161203_0901'),
    ]

    operations = [
        migrations.AddField(
            model_name='rms_accounting_run',
            name='weight',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='rms_accounting_run',
            name='aggregation_level',
            field=models.CharField(choices=[('d', b'day'), ('h', b'hour'), ('m', b'week'), ('n', b'none')], default='n', max_length=1),
        ),
    ]