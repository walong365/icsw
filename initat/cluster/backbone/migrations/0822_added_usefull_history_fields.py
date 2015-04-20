# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0821_remove_kernel_image_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='imagedevicehistory',
            options={'ordering': ('-pk',)},
        ),
        migrations.AlterModelOptions(
            name='kerneldevicehistory',
            options={'ordering': ('-pk',)},
        ),
        migrations.AddField(
            model_name='imagedevicehistory',
            name='end',
            field=models.DateTimeField(default=None, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagedevicehistory',
            name='start',
            field=models.DateTimeField(default=None, auto_now_add=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagedevicehistory',
            name='success',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kerneldevicehistory',
            name='end',
            field=models.DateTimeField(default=None, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kerneldevicehistory',
            name='start',
            field=models.DateTimeField(default=None, auto_now_add=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kerneldevicehistory',
            name='success',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
