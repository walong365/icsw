# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0875_auto_20151009_0807'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphTimeFrame',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', unique=True, max_length=64)),
                ('relative_to_now', models.BooleanField(default=False)),
                ('auto_refresh', models.BooleanField(default=False)),
                ('seconds', models.IntegerField(default=0)),
                ('base_timeframe', models.CharField(default=b'd', max_length=4, choices=[(b'h', b'hour'), (b'd', b'day'), (b'w', b'week'), (b'm', b'month'), (b'y', b'year'), (b'D', b'decade')])),
                ('timeframe_offset', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
