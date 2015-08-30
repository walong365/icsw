# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0854_populateramdiskdcmdline'),
    ]

    operations = [
        migrations.CreateModel(
            name='PopulateRamdiskCmdLine',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True, db_column=b'kernel_log_idx')),
                ('user', models.CharField(default=b'', max_length=256)),
                ('machine', models.CharField(default=b'', max_length=256)),
                ('cmdline', models.CharField(max_length=1024)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('kernel', models.ForeignKey(to='backbone.kernel')),
            ],
        ),
        migrations.RemoveField(
            model_name='populateramdiskdcmdline',
            name='kernel',
        ),
        migrations.DeleteModel(
            name='PopulateRamdiskdCmdLine',
        ),
    ]
