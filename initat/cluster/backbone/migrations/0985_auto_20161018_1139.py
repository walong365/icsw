# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-18 09:39
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0984_auto_20161018_0900'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonHostTraceGeneration',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('fingerprint', models.CharField(default=b'', max_length=255)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='monhosttrace',
            name='generation',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.MonHostTraceGeneration'),
        ),
    ]
