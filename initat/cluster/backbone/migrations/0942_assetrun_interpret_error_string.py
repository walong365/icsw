# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-24 14:29


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0941_assetupdateentry_new_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='assetrun',
            name='interpret_error_string',
            field=models.TextField(default=b''),
        ),
    ]
