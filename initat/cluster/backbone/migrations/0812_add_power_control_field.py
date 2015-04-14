# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0811_add_ipmi_capable_flag_to_device'),
    ]

    operations = [
        migrations.AddField(
            model_name='snmp_scheme',
            name='power_control',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='device',
            name='curl',
            field=models.CharField(default=b'ssh://', max_length=512),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='device',
            name='ipmi_capable',
            field=models.BooleanField(default=False, verbose_name=b'IPMI cabaple'),
            preserve_default=True,
        ),
    ]
