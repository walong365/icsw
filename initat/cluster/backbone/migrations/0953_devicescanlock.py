# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-03 19:08


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0952_assetrun_generate_duration'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceScanLock',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('uuid', models.TextField(default=b'', max_length=64)),
                ('description', models.CharField(default=b'', max_length=255)),
                ('active', models.BooleanField(default=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('config', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='config_lock', to='backbone.config')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.device')),
                ('server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_lock', to='backbone.device')),
            ],
        ),
    ]
