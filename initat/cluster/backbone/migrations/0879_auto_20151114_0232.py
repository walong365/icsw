# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0878_auto_20151102_1938'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='login_fail_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='graphsetting',
            name='cf',
            field=models.CharField(default=b'AVERAGE', max_length=16, choices=[(b'AVERAGE', b'average'), (b'MAX', b'maximum'), (b'MIN', b'minimum')]),
        ),
    ]
