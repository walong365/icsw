# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0894_auto_20151215_1002'),
    ]

    operations = [
        migrations.AddField(
            model_name='netdevice',
            name='desired_status',
            field=models.CharField(default=b'i', max_length=4, choices=[(b'd', b'down'), (b'i', b'ignore'), (b'u', b'up')]),
        ),
    ]
