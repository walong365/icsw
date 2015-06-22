# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0832_sensoraction_sensorthreshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensoraction',
            name='device_action',
            field=models.CharField(default=b'none', max_length=64, choices=[(b'none', b'do nothing'), (b'reboot', b'restart device'), (b'halt', b'halt device')]),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sensoraction',
            name='hard_control',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sensoraction',
            name='send_email',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
