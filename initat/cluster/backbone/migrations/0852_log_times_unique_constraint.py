# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0851_verbose_names_for_setup_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mon_icinga_log_full_system_dump',
            name='date',
            field=models.DateTimeField(unique=True, db_index=True),
        ),
    ]
