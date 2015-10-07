# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0871_auto_20151006_1428'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphSettingSize',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', unique=True, max_length=64)),
                ('default', models.BooleanField(default=False)),
                ('width', models.IntegerField(default=0)),
                ('height', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='graphsettingsize',
            unique_together=set([('width', 'height')]),
        ),
        migrations.AddField(
            model_name='graphsetting',
            name='graph_setting_size',
            field=models.ForeignKey(to='backbone.GraphSettingSize', null=True),
        ),
    ]
