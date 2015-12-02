# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


def db_limit_1():
    # return True if databases do not support some unique_together combinations
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0870_auto_20151006_1357'),
    ]

    operations = [
        migrations.AddField(
            model_name='graphsetting',
            name='name',
            field=models.CharField(default=b'', max_length=128),
        ),
    ]
    if not db_limit_1():
        operations.append(
            migrations.AlterUniqueTogether(
                name='graphsetting',
                unique_together=set([('user', 'name')]),
            )
        )
