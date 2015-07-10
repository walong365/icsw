# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0845_data_migration_kernel_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='netdevice',
            name='speed',
            field=models.BigIntegerField(default=0, null=True, blank=True),
        ),
    ]
