# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-11 10:38


from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0994_auto_20161106_1012'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scheduleitem',
            name='source',
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='scheduleitem',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
