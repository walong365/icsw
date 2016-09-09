# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-09-01 08:50
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0986_auto_20160831_1109'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetPackageVersionInstallTime',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('install_time', models.DateTimeField(null=True)),
                ('package_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetPackageVersion')),
            ],
        ),
        migrations.CreateModel(
            name='ReportHistory',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('created_at_time', models.DateTimeField(null=True)),
                ('number_of_pages', models.IntegerField(default=0)),
                ('number_of_downloads', models.IntegerField(default=0)),
                ('size', models.BigIntegerField(default=0)),
                ('b64_size', models.BigIntegerField(default=0)),
                ('type', models.TextField(null=True)),
                ('filename', models.TextField(null=True)),
                ('created_by_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='assetrun',
            name='packages_install_times',
            field=models.ManyToManyField(to='backbone.AssetPackageVersionInstallTime'),
        ),
    ]