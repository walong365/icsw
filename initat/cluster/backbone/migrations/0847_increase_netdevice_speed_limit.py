# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0846_auto_20150714_1650'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='enable_perfdata',
            field=models.BooleanField(default=True, verbose_name=b'enable perfdata, check IPMI, SNMP and WMI'),
        ),
        migrations.AlterField(
            model_name='netdevice',
            name='speed',
            field=models.BigIntegerField(default=0, null=True, blank=True),
        ),
    ]
