# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0826_added_capability'),
    ]

    operations = [
        migrations.AddField(
            model_name='kpi',
            name='soft_states_as_hard_states',
            field=models.BooleanField(default=True),
        ),
    ]
