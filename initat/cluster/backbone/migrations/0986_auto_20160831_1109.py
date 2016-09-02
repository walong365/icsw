# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-31 09:09
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0985_remove_assetrun_device'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetHWNetworkDevice',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('manufacturer', models.TextField(null=True)),
                ('product_name', models.TextField(null=True)),
                ('device_name', models.TextField(null=True)),
                ('speed', models.IntegerField(null=True)),
                ('mac_address', models.TextField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='network_devices',
            field=models.ManyToManyField(to='backbone.AssetHWNetworkDevice'),
        ),
    ]
