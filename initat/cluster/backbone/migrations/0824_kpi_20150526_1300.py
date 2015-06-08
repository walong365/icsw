# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0823_license'),
    ]

    operations = [
        migrations.CreateModel(
            name='KpiDataSourceTuple',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('device_category', models.ForeignKey(related_name='device_category', to='backbone.category')),
                ('kpi', models.ForeignKey(to='backbone.Kpi')),
                ('monitoring_category', models.ForeignKey(related_name='monitoring_category', to='backbone.category')),
            ],
            options={
                'verbose_name': 'KPI data sources',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='KpiStoredResult',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField()),
                ('result', models.TextField(null=True)),
                ('kpi', models.OneToOneField(to='backbone.Kpi')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='mon_icinga_log_raw_host_downtime_data',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('device_independent', models.BooleanField(default=False, db_index=True)),
                ('msg', models.TextField()),
                ('downtime_state', models.CharField(max_length=5, choices=[(b'START', b'START'), (b'STOP', b'STOP')])),
                ('device', models.ForeignKey(to='backbone.device', null=True)),
                ('logfile', models.ForeignKey(blank=True, to='backbone.mon_icinga_log_file', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='mon_icinga_log_raw_service_downtime_data',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('device_independent', models.BooleanField(default=False, db_index=True)),
                ('msg', models.TextField()),
                ('service_info', models.TextField(null=True, blank=True)),
                ('downtime_state', models.CharField(max_length=5, choices=[(b'START', b'START'), (b'STOP', b'STOP')])),
                ('device', models.ForeignKey(to='backbone.device', null=True)),
                ('logfile', models.ForeignKey(blank=True, to='backbone.mon_icinga_log_file', null=True)),
                ('service', models.ForeignKey(to='backbone.mon_check_command', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='kpi_selected_device_monitoring_category_tuple',
            name='device_category',
        ),
        migrations.RemoveField(
            model_name='kpi_selected_device_monitoring_category_tuple',
            name='kpi',
        ),
        migrations.RemoveField(
            model_name='kpi_selected_device_monitoring_category_tuple',
            name='monitoring_category',
        ),
        migrations.DeleteModel(
            name='kpi_selected_device_monitoring_category_tuple',
        ),
        migrations.AlterModelOptions(
            name='kpi',
            options={'ordering': ('idx',), 'verbose_name': 'KPI'},
        ),
        migrations.RemoveField(
            model_name='kpi',
            name='available_device_categories',
        ),
        migrations.RemoveField(
            model_name='kpi',
            name='available_monitoring_categories',
        ),
        migrations.AddField(
            model_name='kpi',
            name='date',
            field=models.DateTimeField(default=django.utils.timezone.now, auto_now_add=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kpi',
            name='enabled',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kpi',
            name='formula',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kpi',
            name='gui_selected_categories',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kpi',
            name='time_range',
            field=models.TextField(default=b'none', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='kpi',
            name='time_range_parameter',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='imagedevicehistory',
            name='start',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kerneldevicehistory',
            name='start',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_host_data',
            name='state',
            field=models.CharField(max_length=2, choices=[(b'UP', b'UP'), (b'D', b'DOWN'), (b'UR', b'UNREACHABLE'), (b'U', b'UNKNOWN'), (b'PD', b'PLANNED DOWN'), (b'UD', b'UNDETERMINED'), (b'FL', b'FLAPPING')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_host_data',
            name='state_type',
            field=models.CharField(max_length=2, choices=[(b'H', b'HARD'), (b'S', b'SOFT'), (b'UD', b'UD'), (b'PD', b'PLANNED DOWN'), (b'FL', b'FL')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_service_data',
            name='state',
            field=models.CharField(max_length=2, choices=[(b'O', b'OK'), (b'W', b'WARNING'), (b'U', b'UNKNOWN'), (b'C', b'CRITICAL'), (b'UD', b'UNDETERMINED'), (b'PD', b'PLANNED DOWN'), (b'FL', b'FLAPPING')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_service_data',
            name='state_type',
            field=models.CharField(max_length=2, choices=[(b'H', b'HARD'), (b'S', b'SOFT'), (b'UD', b'UD'), (b'PD', b'PLANNED DOWN'), (b'FL', b'FL')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_alert_data',
            name='state',
            field=models.CharField(max_length=2, choices=[(b'UP', b'UP'), (b'D', b'DOWN'), (b'UR', b'UNREACHABLE'), (b'U', b'UNKNOWN'), (b'PD', b'PLANNED DOWN'), (b'UD', b'UNDETERMINED')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_alert_data',
            name='state_type',
            field=models.CharField(max_length=2, choices=[(b'H', b'HARD'), (b'S', b'SOFT'), (b'UD', b'UD'), (b'PD', b'PLANNED DOWN')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_notification_data',
            name='state',
            field=models.CharField(max_length=2, choices=[(b'UP', b'UP'), (b'D', b'DOWN'), (b'UR', b'UNREACHABLE'), (b'U', b'UNKNOWN'), (b'PD', b'PLANNED DOWN'), (b'UD', b'UNDETERMINED')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_alert_data',
            name='state',
            field=models.CharField(max_length=2, choices=[(b'O', b'OK'), (b'W', b'WARNING'), (b'U', b'UNKNOWN'), (b'C', b'CRITICAL'), (b'UD', b'UNDETERMINED'), (b'PD', b'PLANNED DOWN')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_alert_data',
            name='state_type',
            field=models.CharField(max_length=2, choices=[(b'H', b'HARD'), (b'S', b'SOFT'), (b'UD', b'UD'), (b'PD', b'PLANNED DOWN')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_notification_data',
            name='state',
            field=models.CharField(max_length=2, choices=[(b'O', b'OK'), (b'W', b'WARNING'), (b'U', b'UNKNOWN'), (b'C', b'CRITICAL'), (b'UD', b'UNDETERMINED'), (b'PD', b'PLANNED DOWN')]),
            preserve_default=True,
        ),
    ]
