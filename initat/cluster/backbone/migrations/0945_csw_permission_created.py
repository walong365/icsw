# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-27 09:00
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0944_auto_20160526_0841'),
    ]

    operations = [
        migrations.AddField(
            model_name='csw_permission',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2016, 5, 27, 9, 0, 9, 367781, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
