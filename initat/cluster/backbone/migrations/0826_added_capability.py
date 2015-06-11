# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0825_removed_reqrecvstate_and_kpi'),
    ]

    operations = [
        migrations.CreateModel(
            name='capability',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=16)),
                ('info', models.CharField(unique=True, max_length=64)),
                ('port_spec', models.CharField(default=b'', max_length=256)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='device',
            name='capability_list',
            field=models.ManyToManyField(to='backbone.capability'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kpidatasourcetuple',
            name='kpi',
            field=models.ForeignKey(to='backbone.Kpi', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kpistoredresult',
            name='kpi',
            field=models.OneToOneField(to='backbone.Kpi'),
            preserve_default=True,
        ),
    ]
