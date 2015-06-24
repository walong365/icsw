# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0836_deviceselection'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='deviceselection',
            options={'ordering': ('-date',)},
        ),
        migrations.AddField(
            model_name='sensorthreshold',
            name='device_selection',
            field=models.ForeignKey(to='backbone.DeviceSelection', null=True),
            preserve_default=True,
        ),
    ]
