# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-18 05:39


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0961_auto_20160714_1638'),
    ]

    operations = [
        migrations.AddField(
            model_name='dvs_allowed_names',
            name='description',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='device',
            name='name',
            field=models.CharField(default=b'', max_length=192),
        ),
    ]
