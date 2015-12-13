# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0891_syslogcheck'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='syslogcheck',
            name='version',
        ),
        migrations.AddField(
            model_name='syslogcheck',
            name='expressions',
            field=models.TextField(default=b''),
        ),
    ]
