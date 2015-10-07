# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0873_auto_20151007_1507'),
    ]

    operations = [
        migrations.AlterField(
            model_name='graphsetting',
            name='graph_setting_size',
            field=models.ForeignKey(to='backbone.GraphSettingSize'),
        ),
        migrations.AlterField(
            model_name='graphsetting',
            name='graph_setting_timeshift',
            field=models.ForeignKey(blank=True, to='backbone.GraphSettingTimeshift', null=True),
        ),
    ]
