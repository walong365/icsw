# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0820_data_migrate_kernel_images'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='act_image',
        ),
        migrations.RemoveField(
            model_name='device',
            name='act_kernel',
        ),
        migrations.RemoveField(
            model_name='device',
            name='act_kernel_build',
        ),
        migrations.RemoveField(
            model_name='device',
            name='imageversion',
        ),
        migrations.RemoveField(
            model_name='device',
            name='kernelversion',
        ),
    ]
