# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-04 15:51

from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1038_auto_20170131_1920'),
    ]

    operations = [
        migrations.AddField(
            model_name='mon_check_command',
            name='is_special_command',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='mon_check_command',
            name='is_special_meta',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='mon_check_command',
            name='special_parent',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='special_child', to='backbone.mon_check_command'),
        ),
        migrations.AddField(
            model_name='mon_check_command',
            name='uuid',
            field=models.CharField(default="", max_length=64),
        ),
    ]
