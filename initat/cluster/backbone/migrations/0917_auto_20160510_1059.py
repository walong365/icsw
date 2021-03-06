# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-10 08:59


import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0916_scheduleitem_run_now'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetPackageVersion',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.TextField()),
                ('size', models.IntegerField(default=0)),
                ('version', models.TextField(blank=True, default=b'')),
                ('release', models.TextField(blank=True, default=b'')),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='StaticAsset',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.device')),
            ],
        ),
        migrations.CreateModel(
            name='StaticAssetFieldValue',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('value_str', models.CharField(blank=True, default=None, max_length=255, null=True)),
                ('value_int', models.IntegerField(blank=True, default=None, null=True)),
                ('value_date', models.DateField(blank=True, default=None, null=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('static_asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.StaticAsset')),
            ],
        ),
        migrations.CreateModel(
            name='StaticAssetTemplate',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('type', models.IntegerField(choices=[(1, b'LICENSE'), (2, b'CONTRACT'), (3, b'HARDWARE')])),
                ('name', models.CharField(max_length=128, unique=True)),
                ('consumable', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='StaticAssetTemplateField',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('field_type', models.IntegerField(choices=[(1, b'INTEGER'), (2, b'STRING'), (3, b'DATE')])),
                ('optional', models.BooleanField(default=False)),
                ('default_value_str', models.CharField(blank=True, default=b'', max_length=255)),
                ('default_value_int', models.IntegerField(default=0)),
                ('default_value_date', models.DateField(default=django.utils.timezone.now)),
                ('has_bounds', models.BooleanField(default=False)),
                ('value_int_lower_bound', models.IntegerField(default=0)),
                ('value_int_upper_bound', models.IntegerField(default=0)),
                ('monitor', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('static_asset_template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.StaticAssetTemplate')),
            ],
        ),
        migrations.RemoveField(
            model_name='assetpackage',
            name='release',
        ),
        migrations.RemoveField(
            model_name='assetpackage',
            name='version',
        ),
        migrations.AddField(
            model_name='assetpackage',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='staticassetfieldvalue',
            name='static_asset_template_field',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.StaticAssetTemplateField'),
        ),
        migrations.AddField(
            model_name='staticassetfieldvalue',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='staticasset',
            name='static_asset_template',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.StaticAssetTemplate'),
        ),
        migrations.AddField(
            model_name='assetpackageversion',
            name='asset_package',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetPackage'),
        ),
    ]
