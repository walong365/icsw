# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0827_auto_20150602_1011'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComCapability',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('matchcode', models.CharField(unique=True, max_length=16)),
                ('name', models.CharField(unique=True, max_length=16)),
                ('info', models.CharField(max_length=64)),
                ('port_spec', models.CharField(default=b'', max_length=256)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='device',
            name='capability_list',
        ),
        migrations.DeleteModel(
            name='capability',
        ),
        migrations.AddField(
            model_name='device',
            name='com_capability_list',
            field=models.ManyToManyField(to='backbone.ComCapability'),
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
