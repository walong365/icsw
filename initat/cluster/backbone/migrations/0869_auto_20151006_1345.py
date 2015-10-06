# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0868_graphsetting'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user_scan_result',
            name='full_name',
            field=models.TextField(default=b''),
        ),
    ]
