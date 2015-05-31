# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0824_kpi_20150526_1300'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='csw_permission',
            options={'ordering': ('content_type__app_label', 'content_type__model', 'name'), 'verbose_name': 'Global permission'},
        ),
        migrations.RemoveField(
            model_name='device',
            name='recvstate',
        ),
        migrations.RemoveField(
            model_name='device',
            name='recvstate_timestamp',
        ),
        migrations.RemoveField(
            model_name='device',
            name='reqstate',
        ),
        migrations.RemoveField(
            model_name='device',
            name='reqstate_timestamp',
        ),
        migrations.RemoveField(
            model_name='device',
            name='uptime',
        ),
        migrations.RemoveField(
            model_name='device',
            name='uptime_timestamp',
        ),
        migrations.AlterField(
            model_name='kpi',
            name='date',
            field=models.DateTimeField(auto_now_add=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kpidatasourcetuple',
            name='kpi',
            field=models.ForeignKey(to='backbone.Kpi', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kpistoredresult',
            name='kpi',
            field=models.OneToOneField(to='backbone.Kpi'),
            preserve_default=True,
        ),
    ]
