# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-13 16:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1053_auto_20170213_1704'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='config',
            options={'ordering': ['name'], 'verbose_name': 'Configuration'},
        ),
        migrations.AlterField(
            model_name='assetbatch',
            name='error_string',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assetbatch',
            name='run_status',
            field=models.IntegerField(choices=[(1, 'PLANNED'), (2, 'RUNNING'), (3, 'FINISHED_RUNS'), (4, 'GENERATING_ASSETS'), (5, 'FINISHED')], default=1),
        ),
        migrations.AlterField(
            model_name='assetdmihandle',
            name='header',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='assetdmihead',
            name='version',
            field=models.CharField(default='', max_length=63),
        ),
        migrations.AlterField(
            model_name='assetdmivalue',
            name='key',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='assetdmivalue',
            name='value',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assethardwareentry',
            name='attributes',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assethardwareentry',
            name='info_list',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assethardwareentry',
            name='type',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assetlicenseentry',
            name='license_key',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetlicenseentry',
            name='name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetpackage',
            name='package_type',
            field=models.IntegerField(choices=[(1, 'WINDOWS'), (2, 'LINUX')]),
        ),
        migrations.AlterField(
            model_name='assetpackageversion',
            name='info',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assetpackageversion',
            name='release',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='assetpackageversion',
            name='version',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='assetpcientry',
            name='devicename',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetpcientry',
            name='pci_classname',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetpcientry',
            name='subclassname',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetpcientry',
            name='vendorname',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetprocessentry',
            name='name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='error_string',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='interpret_error_string',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_result',
            field=models.IntegerField(choices=[(1, 'UNKNOWN'), (2, 'SUCCESS'), (3, 'WARNING'), (4, 'FAILED'), (5, 'CANCELED')], default=1),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_status',
            field=models.IntegerField(choices=[(1, 'PLANNED'), (2, 'SCANNING'), (3, 'FINISHED_SCANNING'), (4, 'GENERATING_ASSETS'), (5, 'FINISHED')], default=1),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, 'PACKAGE'), (2, 'HARDWARE'), (3, 'LICENSE'), (4, 'UPDATE'), (5, 'LSHW'), (6, 'PROCESS'), (7, 'PENDING_UPDATE'), (8, 'DMI'), (9, 'PCI'), (10, 'PRETTYWINHW'), (11, 'PARTITION'), (12, 'LSBLK'), (13, 'XRANDR')], default=1),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='scan_type',
            field=models.IntegerField(choices=[(1, 'HM'), (2, 'NRPE')], null=True),
        ),
        migrations.AlterField(
            model_name='assetupdateentry',
            name='name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetupdateentry',
            name='new_version',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='assetupdateentry',
            name='release',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='assetupdateentry',
            name='status',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='assetupdateentry',
            name='version',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='backendconfigfile',
            name='same_uploads',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='background_job',
            name='options',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AlterField(
            model_name='category',
            name='full_name',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='comcapability',
            name='port_spec',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AlterField(
            model_name='configserviceenum',
            name='enum_name',
            field=models.CharField(default='', max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='configserviceenum',
            name='info',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='configserviceenum',
            name='name',
            field=models.CharField(default='', max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='device',
            name='alias',
            field=models.CharField(blank=True, default='', max_length=384),
        ),
        migrations.AlterField(
            model_name='device',
            name='comment',
            field=models.CharField(blank=True, default='', max_length=384),
        ),
        migrations.AlterField(
            model_name='device',
            name='enable_perfdata',
            field=models.BooleanField(default=True, verbose_name='enable perfdata, check IPMI, SNMP and WMI'),
        ),
        migrations.AlterField(
            model_name='device',
            name='name',
            field=models.CharField(default='', max_length=192),
        ),
        migrations.AlterField(
            model_name='device',
            name='stage1_flavour',
            field=models.CharField(blank=True, default='cpio', max_length=48),
        ),
        migrations.AlterField(
            model_name='device_group',
            name='description',
            field=models.CharField(blank=True, default='', max_length=384),
        ),
        migrations.AlterField(
            model_name='device_mon_location',
            name='comment',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='device_variable',
            name='uuid',
            field=models.TextField(blank=True, default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='device_variable',
            name='var_type',
            field=models.CharField(choices=[('i', 'integer'), ('s', 'string'), ('d', 'datetime'), ('D', 'date'), ('t', 'time'), ('b', 'blob'), ('?', 'guess')], max_length=3),
        ),
        migrations.AlterField(
            model_name='device_variable_scope',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='deviceclass',
            name='description',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='deviceclass',
            name='limitations',
            field=models.TextField(default='', null=True),
        ),
        migrations.AlterField(
            model_name='deviceclass',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='deviceinventory',
            name='inventory_type',
            field=models.CharField(choices=[('lstopo', 'LSTopo'), ('dmi', 'DMI'), ('pci', 'PCI')], max_length=255),
        ),
        migrations.AlterField(
            model_name='devicescanlock',
            name='description',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='devicescanlock',
            name='uuid',
            field=models.TextField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='deviceselection',
            name='name',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='dispatchersetting',
            name='description',
            field=models.CharField(blank=True, default='', max_length=256),
        ),
        migrations.AlterField(
            model_name='dispatchersetting',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='dispatchersettingschedule',
            name='baseline',
            field=models.IntegerField(choices=[(0, 'year'), (1, 'month'), (2, 'week'), (3, 'day'), (4, 'hour'), (5, 'minute'), (6, 'second')]),
        ),
        migrations.AlterField(
            model_name='dispatchersettingschedule',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='dispatchsetting',
            name='duration_unit',
            field=models.IntegerField(choices=[(1, 'months'), (2, 'weeks'), (3, 'days'), (4, 'hours'), (5, 'minutes')]),
        ),
        migrations.AlterField(
            model_name='dispatchsetting',
            name='source',
            field=models.IntegerField(choices=[(1, 'SNMP'), (2, 'ASU'), (3, 'IPMI'), (4, 'PACKAGE'), (5, 'HARDWARE'), (6, 'LICENSE'), (7, 'UPDATE'), (8, 'SOFTWARE_VERSION'), (9, 'PROCESS'), (10, 'PENDING_UPDATE')]),
        ),
        migrations.AlterField(
            model_name='dvs_allowed_name',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='dvs_allowed_name',
            name='forced_type',
            field=models.CharField(choices=[('', 'ignore'), ('i', 'integer'), ('s', 'string'), ('d', 'datetime'), ('D', 'date'), ('t', 'time'), ('b', 'blob')], default='', max_length=3),
        ),
        migrations.AlterField(
            model_name='dvs_allowed_name',
            name='group',
            field=models.CharField(blank=True, default='', max_length=127),
        ),
        migrations.AlterField(
            model_name='graphsetting',
            name='cf',
            field=models.CharField(choices=[('MIN', 'minimum'), ('AVERAGE', 'average'), ('MAX', 'maximum')], default='AVERAGE', max_length=16),
        ),
        migrations.AlterField(
            model_name='graphsetting',
            name='legend_mode',
            field=models.CharField(choices=[('f', 'full with values'), ('t', 'only text'), ('n', 'nothing')], default='f', max_length=4),
        ),
        migrations.AlterField(
            model_name='graphsetting',
            name='name',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='graphsetting',
            name='scale_mode',
            field=models.CharField(choices=[('l', 'level'), ('n', 'none'), ('t', 'to100')], default='l', max_length=4),
        ),
        migrations.AlterField(
            model_name='graphsettingforecast',
            name='mode',
            field=models.CharField(choices=[('sl', 'simple linear')], default='sl', max_length=4),
        ),
        migrations.AlterField(
            model_name='graphsettingforecast',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='graphsettingsize',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='graphsettingtimeshift',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='graphtimeframe',
            name='base_timeframe',
            field=models.CharField(choices=[('h', 'hour'), ('d', 'day'), ('w', 'week'), ('m', 'month'), ('y', 'year'), ('D', 'decade')], default='d', max_length=4),
        ),
        migrations.AlterField(
            model_name='graphtimeframe',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='hardwarefingerprint',
            name='fingerprint',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='icsweggconsumer',
            name='action',
            field=models.CharField(default='', max_length=63),
        ),
        migrations.AlterField(
            model_name='icsweggconsumer',
            name='xml_node_reference',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='icsweggevaluationdef',
            name='content',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='icswversion',
            name='name',
            field=models.CharField(choices=[('database', 'Database scheme'), ('software', 'Software package version'), ('models', 'Models version')], max_length=63),
        ),
        migrations.AlterField(
            model_name='kernel',
            name='display_name',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='kernel',
            name='name',
            field=models.CharField(default='', max_length=384),
        ),
        migrations.AlterField(
            model_name='kpi',
            name='time_range',
            field=models.TextField(blank=True, default='none'),
        ),
        migrations.AlterField(
            model_name='location_gfx',
            name='comment',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='mon_check_command',
            name='config_rel',
            field=models.ManyToManyField(blank=True, related_name='mcc_rel', to='backbone.config'),
        ),
        migrations.AlterField(
            model_name='mon_check_command',
            name='description',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name='mon_check_command',
            name='uuid',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='mon_dist_master',
            name='livestatus_version',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='mon_dist_slave',
            name='livestatus_version',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_host_data',
            name='state',
            field=models.CharField(choices=[('UP', 'UP'), ('D', 'DOWN'), ('UR', 'UNREACHABLE'), ('U', 'UNKNOWN'), ('PD', 'PLANNED DOWN'), ('UD', 'UNDETERMINED'), ('FL', 'FLAPPING')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_host_data',
            name='state_type',
            field=models.CharField(choices=[('H', 'HARD'), ('S', 'SOFT'), ('UD', 'UD'), ('PD', 'PLANNED DOWN'), ('FL', 'FL')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_service_data',
            name='state',
            field=models.CharField(choices=[('O', 'OK'), ('W', 'WARNING'), ('U', 'UNKNOWN'), ('C', 'CRITICAL'), ('UD', 'UNDETERMINED'), ('PD', 'PLANNED DOWN'), ('FL', 'FLAPPING')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_aggregated_service_data',
            name='state_type',
            field=models.CharField(choices=[('H', 'HARD'), ('S', 'SOFT'), ('UD', 'UD'), ('PD', 'PLANNED DOWN'), ('FL', 'FL')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_alert_data',
            name='state',
            field=models.CharField(choices=[('UP', 'UP'), ('D', 'DOWN'), ('UR', 'UNREACHABLE'), ('U', 'UNKNOWN'), ('PD', 'PLANNED DOWN'), ('UD', 'UNDETERMINED')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_alert_data',
            name='state_type',
            field=models.CharField(choices=[('H', 'HARD'), ('S', 'SOFT'), ('UD', 'UD'), ('PD', 'PLANNED DOWN')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_downtime_data',
            name='downtime_state',
            field=models.CharField(choices=[('START', 'START'), ('STOP', 'STOP')], max_length=5),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_host_notification_data',
            name='state',
            field=models.CharField(choices=[('UP', 'UP'), ('D', 'DOWN'), ('UR', 'UNREACHABLE'), ('U', 'UNKNOWN'), ('PD', 'PLANNED DOWN'), ('UD', 'UNDETERMINED')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_alert_data',
            name='state',
            field=models.CharField(choices=[('O', 'OK'), ('W', 'WARNING'), ('U', 'UNKNOWN'), ('C', 'CRITICAL'), ('UD', 'UNDETERMINED'), ('PD', 'PLANNED DOWN')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_alert_data',
            name='state_type',
            field=models.CharField(choices=[('H', 'HARD'), ('S', 'SOFT'), ('UD', 'UD'), ('PD', 'PLANNED DOWN')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_downtime_data',
            name='downtime_state',
            field=models.CharField(choices=[('START', 'START'), ('STOP', 'STOP')], max_length=5),
        ),
        migrations.AlterField(
            model_name='mon_icinga_log_raw_service_notification_data',
            name='state',
            field=models.CharField(choices=[('O', 'OK'), ('W', 'WARNING'), ('U', 'UNKNOWN'), ('C', 'CRITICAL'), ('UD', 'UNDETERMINED'), ('PD', 'PLANNED DOWN')], max_length=2),
        ),
        migrations.AlterField(
            model_name='mon_notification',
            name='content',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='monhosttracegeneration',
            name='fingerprint',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='monitoring_hint',
            name='value_json',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='mvstructentry',
            name='type_instance',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='mvvalueentry',
            name='name',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='netdevice',
            name='desired_status',
            field=models.CharField(choices=[('i', 'ignore'), ('u', 'up'), ('d', 'down')], default='i', max_length=4),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='alias',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='deb_components',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='deb_distribution',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='password',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='repo_type',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='package_repo',
            name='username',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='package_service',
            name='alias',
            field=models.CharField(default='', max_length=128),
        ),
        migrations.AlterField(
            model_name='partition_disc',
            name='serial',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='populateramdiskcmdline',
            name='cmdline',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='populateramdiskcmdline',
            name='machine',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AlterField(
            model_name='populateramdiskcmdline',
            name='user',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AlterField(
            model_name='rms_accounting_run',
            name='aggregation_level',
            field=models.CharField(choices=[('n', 'none'), ('h', 'hour'), ('d', 'day'), ('m', 'month'), ('y', 'year')], default='n', max_length=1),
        ),
        migrations.AlterField(
            model_name='rmsjobvariable',
            name='name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='rmsjobvariable',
            name='parsed_type',
            field=models.CharField(choices=[('i', 'Integer'), ('f', 'Float'), ('s', 'String')], default='s', max_length=2),
        ),
        migrations.AlterField(
            model_name='rmsjobvariable',
            name='raw_value',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='rmsjobvariable',
            name='unit',
            field=models.CharField(default='', max_length=16),
        ),
        migrations.AlterField(
            model_name='rmsjobvariableaction',
            name='code',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='rmsjobvariableaction',
            name='name',
            field=models.CharField(default='', max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='role',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='role',
            name='name',
            field=models.CharField(default='', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='routetrace',
            name='session_id',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='scanhistory',
            name='source',
            field=models.IntegerField(choices=[(1, 'SNMP'), (2, 'ASU'), (3, 'IPMI'), (4, 'PACKAGE'), (5, 'HARDWARE'), (6, 'LICENSE'), (7, 'UPDATE'), (8, 'SOFTWARE_VERSION'), (9, 'PROCESS'), (10, 'PENDING_UPDATE')]),
        ),
        migrations.AlterField(
            model_name='sensoraction',
            name='action',
            field=models.CharField(choices=[('none', 'do nothing'), ('reboot', 'restart device'), ('halt', 'halt device'), ('poweroff', 'poweroff device'), ('poweron', 'turn on device')], default='none', max_length=64),
        ),
        migrations.AlterField(
            model_name='sensoraction',
            name='description',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AlterField(
            model_name='sensorthreshold',
            name='name',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='sensorthresholdaction',
            name='action_type',
            field=models.CharField(choices=[('lower', 'lower'), ('upper', 'upper')], max_length=12),
        ),
        migrations.AlterField(
            model_name='staticassettemplate',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='default_value_str',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='default_value_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='field_description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='field_type',
            field=models.IntegerField(choices=[(1, 'INTEGER'), (2, 'STRING'), (3, 'DATE'), (4, 'TEXT')]),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='name',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='syslogcheck',
            name='expressions',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='syslogcheck',
            name='xml_source',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='user_scan_result',
            name='full_name',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='user_variable',
            name='description',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='user_variable',
            name='json_value',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='user_variable',
            name='value',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
        migrations.AlterField(
            model_name='user_variable',
            name='var_type',
            field=models.CharField(choices=[('s', 'string'), ('i', 'integer'), ('b', 'boolean'), ('j', 'json-encoded'), ('n', 'none')], max_length=2),
        ),
        migrations.AlterField(
            model_name='userlogentry',
            name='text',
            field=models.CharField(default='', max_length=765),
        ),
        migrations.AlterField(
            model_name='writtenconfigfile',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='writtenconfigfile',
            name='dest',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='writtenconfigfile',
            name='dest_type',
            field=models.CharField(choices=[('f', 'file'), ('l', 'link'), ('d', 'directory'), ('e', 'erase'), ('c', 'copy'), ('i', 'internal')], max_length=8),
        ),
        migrations.AlterField(
            model_name='writtenconfigfile',
            name='source',
            field=models.TextField(default=''),
        ),
        migrations.AlterUniqueTogether(
            name='config',
            unique_together=set([('name',)]),
        ),
        migrations.RemoveField(
            model_name='config',
            name='config_catalog',
        ),
        migrations.DeleteModel(
            name='config_catalog',
        ),
    ]