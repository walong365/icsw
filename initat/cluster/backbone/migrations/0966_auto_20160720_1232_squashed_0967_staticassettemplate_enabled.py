# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-07-20 18:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [(b'backbone', '0966_auto_20160720_1232'), (b'backbone', '0967_staticassettemplate_enabled')]

    dependencies = [
        ('backbone', '0965_auto_20160720_0812'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='fixed',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='staticassettemplate',
            name='description',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.AddField(
            model_name='staticassettemplate',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
    ]
