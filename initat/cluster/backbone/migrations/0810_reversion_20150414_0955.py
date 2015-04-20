# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('backbone', '0801_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='icsw_deletion_record',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('object_id_int', models.IntegerField()),
                ('serialized_data', models.TextField()),
                ('object_repr', models.TextField()),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'verbose_name': 'Category'},
        ),
        migrations.AlterModelOptions(
            name='config',
            options={'ordering': ['name', 'config_catalog__name'], 'verbose_name': 'Configuration'},
        ),
        migrations.AlterModelOptions(
            name='config_blob',
            options={'verbose_name': 'Configuration variable (blob)'},
        ),
        migrations.AlterModelOptions(
            name='config_bool',
            options={'verbose_name': 'Configuration variable (boolean)'},
        ),
        migrations.AlterModelOptions(
            name='config_catalog',
            options={'verbose_name': 'Configuration catalog'},
        ),
        migrations.AlterModelOptions(
            name='config_int',
            options={'verbose_name': 'Configuration variable (integer)'},
        ),
        migrations.AlterModelOptions(
            name='config_script',
            options={'ordering': ('priority', 'name'), 'verbose_name': 'Configuration script'},
        ),
        migrations.AlterModelOptions(
            name='config_str',
            options={'ordering': ('name',), 'verbose_name': 'Configuration variable (string)'},
        ),
        migrations.AlterModelOptions(
            name='csw_object_permission',
            options={'verbose_name': 'Object permission'},
        ),
        migrations.AlterModelOptions(
            name='csw_permission',
            options={'ordering': ('content_type__app_label', 'content_type__name', 'name'), 'verbose_name': 'Global permission'},
        ),
        migrations.AlterModelOptions(
            name='device',
            options={'ordering': ('name',), 'verbose_name': 'Device'},
        ),
        migrations.AlterModelOptions(
            name='device_config',
            options={'verbose_name': 'Device configuration'},
        ),
        migrations.AlterModelOptions(
            name='device_group',
            options={'ordering': ('-cluster_device_group', 'name'), 'verbose_name': 'Device group'},
        ),
        migrations.AlterModelOptions(
            name='device_variable',
            options={'ordering': ('name',), 'verbose_name': 'Device variable'},
        ),
        migrations.AlterModelOptions(
            name='group',
            options={'ordering': ('groupname',), 'verbose_name': 'Group'},
        ),
        migrations.AlterModelOptions(
            name='mon_check_command',
            options={'verbose_name': 'Check command'},
        ),
        migrations.AlterModelOptions(
            name='mon_check_command_special',
            options={'verbose_name': 'Special check command'},
        ),
        migrations.AlterModelOptions(
            name='net_ip',
            options={'verbose_name': 'IP address'},
        ),
        migrations.AlterModelOptions(
            name='netdevice',
            options={'ordering': ('snmp_idx', 'devname'), 'verbose_name': 'Netdevice'},
        ),
        migrations.AlterModelOptions(
            name='peer_information',
            options={'verbose_name': 'Peer information'},
        ),
        migrations.AlterModelOptions(
            name='user',
            options={'ordering': ('login', 'group__groupname'), 'verbose_name': 'User'},
        ),
        migrations.AlterModelOptions(
            name='user_object_permission',
            options={'verbose_name': 'Object permissions of users'},
        ),
        migrations.AlterModelOptions(
            name='user_permission',
            options={'verbose_name': 'Global permissions of users'},
        ),
    ]
