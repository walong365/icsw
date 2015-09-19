# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0855_auto_20150830_0849'),
    ]

    operations = [
        migrations.CreateModel(
            name='RMSJobVariable',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', max_length=255)),
                ('raw_value', models.TextField(default=b'')),
                ('parsed_type', models.CharField(default=b's', max_length=2, choices=[(b'i', b'Integer'), (b'f', b'Float'), (b's', b'String')])),
                ('parsed_integer', models.IntegerField(default=None, null=True)),
                ('parsed_float', models.FloatField(default=None, null=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('rms_job', models.ForeignKey(to='backbone.rms_job')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='rmsjobvariable',
            unique_together=set([('name', 'rms_job')]),
        ),
    ]
