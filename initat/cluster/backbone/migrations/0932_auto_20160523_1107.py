# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-23 09:07


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0931_assetbatch_created'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetHardwareEntry',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('type', models.TextField(default=b'')),
                ('attributes', models.TextField(default=b'')),
                ('info_list', models.TextField(default=b'')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('asset_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetRun')),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetHardwareEntry')),
            ],
        ),
        migrations.RemoveField(
            model_name='asset',
            name='asset_run',
        ),
        migrations.DeleteModel(
            name='Asset',
        ),
    ]
