# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0837_added_device_selection_to_sensorthreshold'),
    ]

    operations = [
        migrations.RenameField(
            model_name='sensorthreshold',
            old_name='hysteresis',
            new_name='lower_value',
        ),
        migrations.RenameField(
            model_name='sensorthreshold',
            old_name='value',
            new_name='upper_value',
        ),
        migrations.RemoveField(
            model_name='sensoraction',
            name='send_email',
        ),
        migrations.RemoveField(
            model_name='sensorthreshold',
            name='limit_class',
        ),
        migrations.RemoveField(
            model_name='sensorthreshold',
            name='sensor_action',
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='lower_mail',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='lower_sensor_action',
            field=models.ForeignKey(related_name='lower_sensor_action', blank=True, to='backbone.SensorAction', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='upper_mail',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='upper_sensor_action',
            field=models.ForeignKey(related_name='upper_sensor_action', blank=True, to='backbone.SensorAction', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='sensoraction',
            name='action',
            field=models.CharField(default=b'none', max_length=64, choices=[(b'none', b'do nothing'), (b'reboot', b'restart device'), (b'halt', b'halt device'), (b'poweron', b'turn on device')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='sensorthreshold',
            name='device_selection',
            field=models.ForeignKey(blank=True, to='backbone.DeviceSelection', null=True),
            preserve_default=True,
        ),
    ]
