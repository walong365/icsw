# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0845_data_migration_kernel_name'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='csw_permission',
            options={'ordering': ('content_type__app_label', 'name'), 'verbose_name': 'Global permission'},
        ),
        migrations.RemoveField(
            model_name='config',
            name='parent_config',
        ),
        migrations.AddField(
            model_name='config_catalog',
            name='system_catalog',
            field=models.BooleanField(default=False),
        ),
    ]
