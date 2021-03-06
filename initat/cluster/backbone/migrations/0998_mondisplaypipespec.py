# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-22 13:15


from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0997_device_dynamic_checks'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonDisplayPipeSpec',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128, unique=True)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('system_pipe', models.BooleanField(default=False)),
                ('public_pipe', models.BooleanField(default=True)),
                ('json_spec', models.TextField(default='')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('create_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
