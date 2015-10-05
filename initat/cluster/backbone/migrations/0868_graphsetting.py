# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0867_network_preferred_domain_tree_node'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphSetting',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('hide_empty', models.BooleanField(default=True)),
                ('include_zero', models.BooleanField(default=True)),
                ('scale_mode', models.CharField(default=b'l', max_length=4, choices=[(b'l', b'level'), (b'n', b'none'), (b't', b'to100')])),
                ('legend_mode', models.CharField(default=b'f', max_length=4, choices=[(b'f', b'full with values'), (b'n', b'nothing'), (b't', b'only text')])),
                ('merge_devices', models.BooleanField(default=False)),
                ('merge_graphs', models.BooleanField(default=False)),
                ('merge_controlling_devices', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
