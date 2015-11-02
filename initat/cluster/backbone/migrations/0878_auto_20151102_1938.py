# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0877_auto_20151016_1007'),
    ]

    operations = [
        migrations.AddField(
            model_name='graphsetting',
            name='cf',
            field=models.CharField(default=b'AVERAGE', max_length=16, choices=[(b'AVERAGE', b'average'), (b'MAXIMUM', b'maximum'), (b'MINIMUM', b'minimum')]),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='password',
            field=models.CharField(default=b'', max_length=128, blank=True),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='username',
            field=models.CharField(default=b'', max_length=128, blank=True),
        ),
    ]
