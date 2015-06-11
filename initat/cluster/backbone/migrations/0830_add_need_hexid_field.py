# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0829_removed_ipmi_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='partition_fs',
            name='need_hexid',
            field=models.BooleanField(default=True),
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
