# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0818_remove_device_curl'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceBootHistory',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(to='backbone.device')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageDeviceHistory',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('version', models.IntegerField(default=1, null=True, blank=True)),
                ('release', models.IntegerField(default=1, null=True, blank=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(to='backbone.device')),
                ('device_boot_history', models.ForeignKey(to='backbone.DeviceBootHistory')),
                ('image', models.ForeignKey(to='backbone.image')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='KernelDeviceHistory',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('version', models.IntegerField(default=1, null=True, blank=True)),
                ('release', models.IntegerField(default=1, null=True, blank=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(to='backbone.device')),
                ('device_boot_history', models.ForeignKey(to='backbone.DeviceBootHistory')),
                ('kernel', models.ForeignKey(to='backbone.kernel')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='device',
            name='imageversion',
            field=models.CharField(default=b'', max_length=192, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='device',
            name='kernelversion',
            field=models.CharField(default=b'', max_length=192, blank=True),
            preserve_default=True,
        ),
    ]
