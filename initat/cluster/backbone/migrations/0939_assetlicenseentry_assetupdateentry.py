# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-24 07:56
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0938_staticassettemplate_parent_template'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetLicenseEntry',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default=b'', max_length=255)),
                ('license_key', models.CharField(default=b'', max_length=255)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('asset_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetRun')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='AssetUpdateEntry',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default=b'', max_length=255)),
                ('version', models.CharField(default=b'', max_length=255)),
                ('release', models.CharField(default=b'', max_length=255)),
                ('kb_idx', models.IntegerField(default=0)),
                ('install_date', models.DateTimeField(null=True)),
                ('status', models.CharField(default=b'', max_length=128)),
                ('optional', models.BooleanField(default=True)),
                ('installed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('asset_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetRun')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
    ]