# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-03 19:26


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0953_devicescanlock'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicescanlock',
            name='run_time',
            field=models.IntegerField(default=0),
        ),
    ]
