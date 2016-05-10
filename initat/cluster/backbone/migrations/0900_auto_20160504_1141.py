# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-04 09:41
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0899_auto_20160325_1240'),
    ]

    operations = [
        migrations.AlterField(
            model_name='monitoring_hint',
            name='value_blob',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.AlterField(
            model_name='sensorthreshold',
            name='notify_users',
            field=models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL),
        ),
    ]