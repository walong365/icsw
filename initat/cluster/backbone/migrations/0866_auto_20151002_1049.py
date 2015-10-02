# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0865_network_device_type_auto_created'),
    ]

    operations = [
        migrations.AddField(
            model_name='netdevice',
            name='bond_master',
            field=models.ForeignKey(related_name='bond_slaves', blank=True, to='backbone.netdevice', null=True),
        ),
        migrations.AddField(
            model_name='netdevice',
            name='is_bond',
            field=models.BooleanField(default=False),
        ),
    ]
