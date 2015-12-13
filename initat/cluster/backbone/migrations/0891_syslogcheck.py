# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0890_auto_20151213_0819'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyslogCheck',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=64)),
                ('xml_source', models.TextField(default=b'')),
                ('version', models.ImageField(default=1, upload_to=b'')),
                ('enabled', models.BooleanField(default=True)),
                ('minutes_to_consider', models.IntegerField(default=5)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
    ]
