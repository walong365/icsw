# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0810_reversion_20150414_0955'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='ipmi_capable',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
