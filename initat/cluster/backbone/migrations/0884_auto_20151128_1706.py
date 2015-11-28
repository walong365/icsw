# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0883_auto_20151124_1447'),
    ]

    operations = [
        migrations.CreateModel(
            name='ICSWVersion',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=63, choices=[(b'database', b'Database scheme'), (b'software', b'Software package version'), (b'models', b'Models version')])),
                ('version', models.CharField(max_length=128)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='alias',
            field=models.CharField(default=b'', max_length=128, blank=True),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='repo_type',
            field=models.CharField(default=b'', max_length=128, blank=True),
        ),
    ]
