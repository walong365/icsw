# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-11 12:13


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1024_auto_20170111_1057'),
    ]

    operations = [
        migrations.AddField(
            model_name='icsweggrequest',
            name='mult',
            field=models.IntegerField(default=1),
        ),
    ]
