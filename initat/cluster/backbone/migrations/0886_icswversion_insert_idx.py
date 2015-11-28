# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0885_auto_20151128_1707'),
    ]

    operations = [
        migrations.AddField(
            model_name='icswversion',
            name='insert_idx',
            field=models.IntegerField(default=1),
        ),
    ]
