# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-12 09:02


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1018_remove_assethwdisplayentry_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='assetbatch',
            name='cpus_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='displays_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='gpus_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='installed_updates_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='memory_modules_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='network_devices_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='packages_install_times_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='packages_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='partition_table_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='pending_updates_status',
            field=models.IntegerField(default=0),
        ),
    ]
