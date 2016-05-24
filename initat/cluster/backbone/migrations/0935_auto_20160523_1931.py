# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-23 17:31
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0934_assetprocessentry'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='assetprocessentry',
            options={'ordering': ('pid',)},
        ),
        migrations.AddField(
            model_name='staticassettemplate',
            name='system_template',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='staticassettemplate',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='field_description',
            field=models.TextField(default=b''),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='name',
            field=models.CharField(default=b'', max_length=64),
        ),
        migrations.AlterUniqueTogether(
            name='staticassettemplatefield',
            unique_together=set([('static_asset_template', 'name')]),
        ),
    ]
