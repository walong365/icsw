# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-01 08:41


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1004_auto_20161130_1323'),
    ]

    operations = [
        migrations.AddField(
            model_name='dispatcherlink',
            name='schedule_handler_data',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='scheduleitem',
            name='schedule_handler_data',
            field=models.TextField(null=True),
        ),
    ]
