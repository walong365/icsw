# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0850_background_job_options'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='architecture',
            options={'verbose_name': 'Architecture'},
        ),
        migrations.AlterModelOptions(
            name='image',
            options={'ordering': ('name',), 'verbose_name': 'Image'},
        ),
        migrations.AlterModelOptions(
            name='kernel',
            options={'verbose_name': 'Kernel'},
        ),
        migrations.AlterModelOptions(
            name='lvm_lv',
            options={'ordering': ('name',), 'verbose_name': 'Partition: LVM Logical Volume'},
        ),
        migrations.AlterModelOptions(
            name='lvm_vg',
            options={'ordering': ('name',), 'verbose_name': 'Partition: LVM Volume Group'},
        ),
        migrations.AlterModelOptions(
            name='partition',
            options={'ordering': ('pnum',), 'verbose_name': 'Partition'},
        ),
        migrations.AlterModelOptions(
            name='partition_disc',
            options={'ordering': ('priority', 'disc'), 'verbose_name': 'Partition: Disc'},
        ),
        migrations.AlterModelOptions(
            name='partition_fs',
            options={'ordering': ('name',), 'verbose_name': 'Partition: File System'},
        ),
        migrations.AlterModelOptions(
            name='partition_table',
            options={'verbose_name': 'Partition: Table'},
        ),
        migrations.AlterModelOptions(
            name='sys_partition',
            options={'verbose_name': 'Partition: System Partition'},
        ),
    ]
