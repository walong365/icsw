# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0843_sensorthresholdaction_create_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='kernel',
            name='display_name',
            field=models.CharField(default=b'', max_length=128),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kernel',
            name='name',
            field=models.CharField(default=b'', max_length=384),
            preserve_default=True,
        ),
    ]
