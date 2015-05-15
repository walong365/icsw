# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
from django.utils.timezone import utc
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0822_added_usefull_history_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='LicenseLockListDeviceService',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('device', models.ForeignKey(to='backbone.device')),
                ('service', models.ForeignKey(blank=True, to='backbone.mon_check_command', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LicenseLockListExtLicense',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('ext_license', models.ForeignKey(to='backbone.ext_license')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LicenseLockListUser',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LicenseUsageDeviceService',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('device', models.ForeignKey(to='backbone.device')),
                ('service', models.ForeignKey(blank=True, to='backbone.mon_check_command', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LicenseUsageExtLicense',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('ext_license', models.ForeignKey(to='backbone.ext_license')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LicenseUsageUser',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LicenseViolation',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('license', models.CharField(max_length=30, db_index=True)),
                ('hard', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.DeleteModel(
            name='cluster_license',
        ),
        migrations.AlterModelOptions(
            name='license',
            options={'verbose_name': 'License'},
        ),
        migrations.AddField(
            model_name='license',
            name='date',
            field=models.DateTimeField(default=datetime.datetime(2015, 5, 12, 14, 9, 41, 272359, tzinfo=utc), auto_now_add=True),
            preserve_default=False,
        ),
    ]
