# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-16 14:51
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1019_auto_20161012_1102'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='licenselocklistdeviceservice',
            name='device',
        ),
        migrations.RemoveField(
            model_name='licenselocklistdeviceservice',
            name='service',
        ),
        migrations.RemoveField(
            model_name='licenselocklistextlicense',
            name='ext_license',
        ),
        migrations.RemoveField(
            model_name='licenselocklistuser',
            name='user',
        ),
        migrations.RemoveField(
            model_name='licenseusagedeviceservice',
            name='device',
        ),
        migrations.RemoveField(
            model_name='licenseusagedeviceservice',
            name='service',
        ),
        migrations.RemoveField(
            model_name='licenseusageextlicense',
            name='ext_license',
        ),
        migrations.RemoveField(
            model_name='licenseusageuser',
            name='user',
        ),
        migrations.DeleteModel(
            name='LicenseViolation',
        ),
        migrations.DeleteModel(
            name='LicenseLockListDeviceService',
        ),
        migrations.DeleteModel(
            name='LicenseLockListExtLicense',
        ),
        migrations.DeleteModel(
            name='LicenseLockListUser',
        ),
        migrations.DeleteModel(
            name='LicenseUsageDeviceService',
        ),
        migrations.DeleteModel(
            name='LicenseUsageExtLicense',
        ),
        migrations.DeleteModel(
            name='LicenseUsageUser',
        ),
    ]
