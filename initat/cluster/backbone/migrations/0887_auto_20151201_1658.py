# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0886_icswversion_insert_idx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sensoraction',
            name='action',
            field=models.CharField(default=b'none', max_length=64, choices=[(b'none', b'do nothing'), (b'reboot', b'restart device'), (b'halt', b'halt device'), (b'poweroff', b'poweroff device'), (b'poweron', b'turn on device')]),
        ),
    ]
