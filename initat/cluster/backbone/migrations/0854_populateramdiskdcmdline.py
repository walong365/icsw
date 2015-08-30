# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0853_auto_20150816_2043'),
    ]

    operations = [
        migrations.CreateModel(
            name='PopulateRamdiskdCmdLine',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True, db_column=b'kernel_log_idx')),
                ('user', models.CharField(default=b'', max_length=256)),
                ('machine', models.CharField(default=b'', max_length=256)),
                ('cmdline', models.CharField(max_length=1024)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('kernel', models.ForeignKey(to='backbone.kernel')),
            ],
        ),
    ]
