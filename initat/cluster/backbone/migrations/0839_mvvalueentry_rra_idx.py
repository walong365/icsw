# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0838_update_threshold_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='mvvalueentry',
            name='rra_idx',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
    ]
