# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-13 05:18


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0995_auto_20160912_2051'),
    ]

    operations = [
        migrations.RenameField(
            model_name='config_catalog',
            old_name='priorty',
            new_name='priority',
        ),
    ]
