# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0891_syslogcheck'),
    ]

    operations = [
        migrations.AddField(
            model_name='syslogcheck',
            name='expressions',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='syslogcheck',
            name='version',
            field=models.IntegerField(default=1),
        ),
    ]
