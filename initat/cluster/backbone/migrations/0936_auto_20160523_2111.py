# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-23 19:11


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0935_auto_20160523_1931'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='staticassettemplate',
            name='consumable',
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='consumable',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='optional',
            field=models.BooleanField(default=True),
        ),
    ]
