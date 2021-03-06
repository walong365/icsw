# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-29 11:21


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0946_auto_20160529_1151'),
    ]

    operations = [
        migrations.AddField(
            model_name='user_variable',
            name='description',
            field=models.CharField(blank=True, default=b'', max_length=255),
        ),
        migrations.AlterField(
            model_name='user_variable',
            name='json_value',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.AlterField(
            model_name='user_variable',
            name='value',
            field=models.CharField(blank=True, default=b'', max_length=512),
        ),
    ]
