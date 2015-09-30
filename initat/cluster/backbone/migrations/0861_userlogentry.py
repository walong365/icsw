# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0860_remove_device_log'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLogEntry',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('sent_via_digest', models.BooleanField(default=False)),
                ('viewed_via_webfrontend', models.BooleanField(default=False)),
                ('text', models.CharField(default=b'', max_length=765)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('devices', models.ManyToManyField(to='backbone.device')),
                ('level', models.ForeignKey(to='backbone.LogLevel')),
                ('source', models.ForeignKey(to='backbone.LogSource')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
