# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0835_added_wmi_and_discovery_dispatch_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceSelection',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', max_length=64)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('categories', models.ManyToManyField(to='backbone.category')),
                ('device_groups', models.ManyToManyField(to='backbone.device_group')),
                ('devices', models.ManyToManyField(to='backbone.device')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
