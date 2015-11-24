# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0882_deviceinventory'),
    ]

    operations = [
        migrations.AddField(
            model_name='package_repo',
            name='deb_components',
            field=models.CharField(default=b'', max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='package_repo',
            name='deb_distribution',
            field=models.CharField(default=b'', max_length=128, blank=True),
        ),
    ]
