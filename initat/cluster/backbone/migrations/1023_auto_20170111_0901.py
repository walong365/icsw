# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-01-11 08:01


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1022_auto_20170109_0914'),
    ]

    operations = [
        migrations.AddField(
            model_name='nmapscan',
            name='error_string',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='nmapscan',
            name='in_progress',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='nmapscan',
            name='devices_found',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='nmapscan',
            name='devices_scanned',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='nmapscan',
            name='raw_result',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='nmapscan',
            name='runtime',
            field=models.FloatField(null=True),
        ),
    ]
