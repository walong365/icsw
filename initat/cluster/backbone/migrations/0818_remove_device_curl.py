# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0817_rewrite_curl'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='curl',
        ),
    ]
