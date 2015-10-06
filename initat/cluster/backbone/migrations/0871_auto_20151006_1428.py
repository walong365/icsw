# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0870_auto_20151006_1357'),
    ]

    operations = [
        migrations.AddField(
            model_name='graphsetting',
            name='name',
            field=models.CharField(default=b'', max_length=128),
        ),
        migrations.AlterUniqueTogether(
            name='graphsetting',
            unique_together=set([('user', 'name')]),
        ),
    ]
