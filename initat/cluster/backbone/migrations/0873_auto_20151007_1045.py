# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0872_auto_20151007_1033'),
    ]

    operations = [
        migrations.RenameField(
            model_name='graphsetting',
            old_name='size',
            new_name='graph_setting_size',
        ),
    ]
