# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0884_auto_20151128_1706'),
    ]

    operations = [
        migrations.AlterField(
            model_name='package_service',
            name='alias',
            field=models.CharField(default=b'', max_length=128),
        ),
    ]
