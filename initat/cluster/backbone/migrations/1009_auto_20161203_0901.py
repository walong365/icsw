# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-03 08:01


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1008_auto_20161203_0810'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='rms_accounting_record',
            name='aggregation_end',
        ),
        migrations.RemoveField(
            model_name='rms_accounting_record',
            name='aggregation_level',
        ),
        migrations.RemoveField(
            model_name='rms_accounting_record',
            name='aggregation_start',
        ),
        migrations.AddField(
            model_name='rms_accounting_run',
            name='aggregation_end',
            field=models.DateTimeField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='rms_accounting_run',
            name='aggregation_level',
            field=models.CharField(choices=[('d', b'day'), ('h', b'hour'), ('n', b'none')], default='n', max_length=1),
        ),
        migrations.AddField(
            model_name='rms_accounting_run',
            name='aggregation_start',
            field=models.DateTimeField(default=None, null=True),
        ),
    ]
