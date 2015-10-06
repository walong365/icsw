# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0869_auto_20151006_1345'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='full_name',
            field=models.TextField(default=b'', blank=True),
        ),
        migrations.AlterField(
            model_name='device_mon_location',
            name='comment',
            field=models.TextField(default=b'', blank=True),
        ),
        migrations.AlterField(
            model_name='location_gfx',
            name='comment',
            field=models.TextField(default=b'', blank=True),
        ),
        migrations.AlterField(
            model_name='mon_notification',
            name='content',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='populateramdiskcmdline',
            name='cmdline',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='wc_files',
            name='dest',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='wc_files',
            name='source',
            field=models.TextField(default=b''),
        ),
    ]
