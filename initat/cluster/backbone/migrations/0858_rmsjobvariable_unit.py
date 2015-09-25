# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0857_rmsjobvariableaction_rmsjobvariableactionrun'),
    ]

    operations = [
        migrations.AddField(
            model_name='rmsjobvariable',
            name='unit',
            field=models.CharField(default=b'', max_length=16),
        ),
    ]
