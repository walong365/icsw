# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0813_device_is_meta_device'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='actimage',
        ),
        migrations.RemoveField(
            model_name='device',
            name='actkernel',
        ),
        migrations.RemoveField(
            model_name='device',
            name='newimage',
        ),
        migrations.RemoveField(
            model_name='device',
            name='newkernel',
        ),
        migrations.AlterField(
            model_name='config_script',
            name='description',
            field=models.CharField(max_length=765, db_column=b'descr', blank=True),
            preserve_default=True,
        ),
    ]
