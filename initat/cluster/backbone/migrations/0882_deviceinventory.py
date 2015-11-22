# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0881_auto_20151122_1319'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceInventory',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('inventory_type', models.CharField(max_length=255, choices=[(b'lstopo', b'LSTopo'), (b'dmi', b'DMI'), (b'pci', b'PCI')])),
                ('run_idx', models.IntegerField(default=0)),
                ('value', models.TextField()),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(to='backbone.device')),
            ],
        ),
    ]
