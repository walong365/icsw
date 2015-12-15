# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0893_syslogcheck_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='network',
            name='preferred_domain_tree_node',
            field=models.ForeignKey(blank=True, to='backbone.domain_tree_node', null=True),
        ),
    ]
