# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0834_auto_20150621_1232'),
    ]

    operations = [
        migrations.CreateModel(
            name='DispatchSetting',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('source', models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI')])),
                ('duration_amount', models.IntegerField(default=1)),
                ('duration_unit', models.IntegerField(choices=[(1, b'months'), (2, b'weeks'), (3, b'days'), (4, b'hours'), (5, b'minutes')])),
                ('run_now', models.BooleanField(default=False)),
                ('device', models.ForeignKey(to='backbone.device')),
            ],
        ),
        migrations.CreateModel(
            name='ScanHistory',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('source', models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI')])),
                ('duration', models.IntegerField()),
                ('success', models.BooleanField(default=True)),
                ('device', models.ForeignKey(to='backbone.device')),
            ],
        ),
        migrations.AddField(
            model_name='netdevice',
            name='wmi_interface_index',
            field=models.IntegerField(default=None, null=True, blank=True),
        ),
    ]
