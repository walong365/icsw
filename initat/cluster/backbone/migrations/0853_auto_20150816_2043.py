# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0852_log_times_unique_constraint'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kernel',
            options={'ordering': ('display_name', 'pk'), 'verbose_name': 'Kernel'},
        ),
        migrations.AddField(
            model_name='package_repo',
            name='password',
            field=models.CharField(default=b'', max_length=128),
        ),
        migrations.AddField(
            model_name='package_repo',
            name='username',
            field=models.CharField(default=b'', max_length=128),
        ),
    ]
