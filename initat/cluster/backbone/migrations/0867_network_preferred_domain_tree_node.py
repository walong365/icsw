# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0866_auto_20151002_1049'),
    ]

    operations = [
        migrations.AddField(
            model_name='network',
            name='preferred_domain_tree_node',
            field=models.ForeignKey(to='backbone.domain_tree_node', null=True),
        ),
    ]
