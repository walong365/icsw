# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0872_auto_20151007_1050'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphSettingTimeshift',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', unique=True, max_length=64)),
                ('seconds', models.IntegerField(default=0, unique=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterModelOptions(
            name='graphsettingsize',
            options={'ordering': ('width', 'height')},
        ),
        migrations.AddField(
            model_name='graphsetting',
            name='graph_setting_timeshift',
            field=models.ForeignKey(to='backbone.GraphSettingTimeshift', null=True),
        ),
    ]
