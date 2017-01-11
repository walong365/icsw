# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-15 08:08


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0997_auto_20160914_1438'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assetupdateentry',
            name='asset_run',
        ),
        migrations.RemoveField(
            model_name='assetupdateentry',
            name='created',
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='installed_updates',
            field=models.ManyToManyField(related_name='assetbatch_installed_updates', to='backbone.AssetUpdateEntry'),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='pending_updates',
            field=models.ManyToManyField(related_name='assetbatch_pending_updates', to='backbone.AssetUpdateEntry'),
        ),
    ]
