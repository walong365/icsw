# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-31 16:11


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0987_auto_20161019_0927'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticassettemplate',
            name='multi',
            field=models.BooleanField(default=False),
        ),
    ]
