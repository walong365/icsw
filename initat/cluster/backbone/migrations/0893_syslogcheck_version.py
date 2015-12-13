# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0892_auto_20151213_2217'),
    ]

    operations = [
        migrations.AddField(
            model_name='syslogcheck',
            name='version',
            field=models.IntegerField(default=1),
        ),
    ]
