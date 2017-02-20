# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-17 13:48


import functools

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


# Functions from the following migrations need manual copying.
# Move them and any dependencies into this file, then update the
# RunPython operations to refer to the local versions:
# initat.cluster.backbone.migrations.0983_role_based_scheme
# initat.cluster.backbone.migrations.0990_auto_20160905_1048
# initat.cluster.backbone.migrations.1004_auto_20160927_1017
# initat.cluster.backbone.migrations.1008_auto_20160929_1537
# initat.cluster.backbone.migrations.1009_auto_20160930_1457

def migrate_to_role_based_auth_model(apps, schema_editor):
    Role = apps.get_model("backbone", "role")
    user = apps.get_model("backbone", "user")
    group = apps.get_model("backbone", "group")
    csw_perm = apps.get_model("backbone", "csw_permission")
    csw_obj_perm = apps.get_model("backbone", "csw_object_permission")
    content_type = apps.get_model("contenttypes", "contenttype")

    g_perm, o_perm = (
        apps.get_model("backbone", "RolePermission"),
        apps.get_model("backbone", "RoleObjectPermission"),
    )
    _ac_dict = {
        "user": (
            apps.get_model("backbone", "user_permission"),
            apps.get_model("backbone", "user_object_permission"),
        ),
        "group": (
            apps.get_model("backbone", "group_permission"),
            apps.get_model("backbone", "group_object_permission"),
        ),
    }
    # add perm for allowed_device_groups
    try:
        adg = csw_perm.objects.get(Q(codename="access_device_group"))
    except csw_perm.DoesNotExist:
        # fake creation
        adg = csw_perm.objects.create(
            codename="access_device_group",
            name="Allow access to device group",
            valid_for_object_level=True,
            content_type=content_type.objects.get(Q(model="device_group")),
        )
    for _src, _type in [(user, "user"), (group, "group")]:
        for entry in _src.objects.all():
            if _type == "user":
                _id_str = entry.login
            else:
                _id_str = entry.groupname
            if entry.allowed_device_groups.all().count():
                # new roles for allowed device groups
                adg_role = Role.objects.create(
                    name="{}Role_GroupAccess_{}".format(
                        _type,
                        _id_str,
                    )
                )
                entry.roles.add(adg_role)
                for group in entry.allowed_device_groups.all():
                    obj_right = csw_obj_perm.objects.create(
                        csw_permission=adg,
                        object_pk=group.idx,
                    )
                    o_perm.objects.create(
                        role=adg_role,
                        csw_object_permission=obj_right,
                        level=0,
                    )
            new_role = None
            for _obj_type, _model in zip(["global", "object"], _ac_dict[_type]):
                if _model.objects.filter(Q(**{_type: entry})).count():
                    if new_role is None:
                        # create new role
                        new_role = Role.objects.create(
                            name="{}Role_{}".format(_type, _id_str),
                            description="auto created",
                        )
                        entry.roles.add(new_role)
                        # entry.save(update_fields=["roles"])
                    # add objects
                    for _right in _model.objects.filter(Q(**{_type: entry})):
                        if _obj_type == "global":
                            new_g = g_perm.objects.create(
                                role=new_role,
                                csw_permission=_right.csw_permission,
                                level=_right.level,
                            )
                        else:
                            new_o = o_perm.objects.create(
                                role=new_role,
                                csw_object_permission=_right.csw_object_permission,
                                level=_right.level,
                            )
                    # print _obj_type, _model, _model.objects.filter(Q(**{_type: entry})).count()


def convert_size(apps, schema_editor, factor):
    Partition = apps.get_model("backbone", "partition")
    for partition in Partition.objects.all():
        if partition.size:
            partition.size *= factor
            partition.save()


def fix_assetbatch_and_assetrun(apps, schema_editor):
    AssetBatch = apps.get_model("backbone", "AssetBatch")
    AssetRun = apps.get_model("backbone", "AssetRun")

    for ab in AssetBatch.objects.all():
        ab.run_status = 5
        ab.save()

    for ar in AssetRun.objects.all():
        ar.run_status = 5
        ar.save()


def rename_staticassettemplate_type(apps, schema_editor):
    StaticAssetTemplate = apps.get_model("backbone", "StaticAssetTemplate")

    for static_asset_template in StaticAssetTemplate.objects.all():
        if int(static_asset_template.type) == 1:
            static_asset_template.type = "License"
        elif int(static_asset_template.type) == 2:
            static_asset_template.type = "Contract"
        elif int(static_asset_template.type) == 3:
            static_asset_template.type = "Hardware"

        static_asset_template.save()


def fix_noneditable_dvs_scopes(apps, schema_editor):
    dvs_allowed_name = apps.get_model("backbone", "dvs_allowed_name")

    for dvs in dvs_allowed_name.objects.all():
        if dvs.device_variable_scope.name == "inventory":
            dvs.editable = True
            dvs.save()


def dummy_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    replaces = [('backbone', '0983_role_based_scheme'), ('backbone', '0984_auto_20160830_1502'), ('backbone', '0985_remove_assetrun_device'),
                ('backbone', '0986_auto_20160831_1109'), ('backbone', '0986_auto_20160901_1050'), ('backbone', '0987_auto_20160902_1335'),
                ('backbone', '0988_reporthistory_progress'), ('backbone', '0989_auto_20160905_1047'), ('backbone', '0990_auto_20160905_1048'),
                ('backbone', '0991_auto_20160905_1250'), ('backbone', '0992_logicaldisc'), ('backbone', '0993_auto_20160912_0827'),
                ('backbone', '0994_configserviceenum_root_service'), ('backbone', '0995_auto_20160912_2051'), ('backbone', '0996_auto_20160913_0718'),
                ('backbone', '0997_auto_20160914_1438'), ('backbone', '0998_auto_20160915_1008'), ('backbone', '0999_remove_mon_dist_master_md_version'),
                ('backbone', '1000_hardwarefingerprint'), ('backbone', '1001_hardwarefingerprint_changecount'), ('backbone', '1002_routetrace'),
                ('backbone', '1003_auto_20160927_0907'), ('backbone', '1004_auto_20160927_1017'), ('backbone', '1005_delete_assethwhddentry'),
                ('backbone', '1006_auto_20160929_0852'), ('backbone', '1007_auto_20160929_1342'), ('backbone', '1008_auto_20160929_1537'),
                ('backbone', '1009_auto_20160930_1457'), ('backbone', '1010_auto_20161002_1148'), ('backbone', '1011_icsweggconsumer_consumed'),
                ('backbone', '1012_auto_20161004_1553'), ('backbone', '1013_auto_20161004_1600'), ('backbone', '1014_auto_20161004_2052'),
                ('backbone', '1015_auto_20161005_1916'), ('backbone', '1016_auto_20161010_1221'), ('backbone', '1017_auto_20161010_1554'),
                ('backbone', '1017_delete_assethwlogicalentry'), ('backbone', '1018_remove_assethwdisplayentry_type'),
                ('backbone', '1019_auto_20161012_1102'), ('backbone', '1020_auto_20161016_1651'), ('backbone', '1021_auto_20161017_0830')]

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('backbone', '0982_role_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='description',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.RunPython(
            code=migrate_to_role_based_auth_model,
            reverse_code=dummy_reverse,
        ),
        migrations.AlterModelOptions(
            name='roleobjectpermission',
            options={'verbose_name': 'Global Object permissions of Role'},
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='cpu_count',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='cpus',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='displays',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='gpus',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='hdds',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='memory_count',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='memory_modules',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='packages',
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='partitions',
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='cpus',
            field=models.ManyToManyField(to='backbone.AssetHWCPUEntry'),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='displays',
            field=models.ManyToManyField(to='backbone.AssetHWDisplayEntry'),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='gpus',
            field=models.ManyToManyField(to='backbone.AssetHWGPUEntry'),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='memory_modules',
            field=models.ManyToManyField(to='backbone.AssetHWMemoryEntry'),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, b'PACKAGE'), (2, b'HARDWARE'), (3, b'LICENSE'), (4, b'UPDATE'), (5, b'LSHW'), (6, b'PROCESS'),
                                               (7, b'PENDING_UPDATE'), (8, b'DMI'), (9, b'PCI'), (10, b'PRETTYWINHW')], default=1),
        ),
        migrations.RemoveField(
            model_name='assetrun',
            name='device',
        ),
        migrations.CreateModel(
            name='AssetHWNetworkDevice',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('manufacturer', models.TextField(null=True)),
                ('product_name', models.TextField(null=True)),
                ('device_name', models.TextField(null=True)),
                ('speed', models.IntegerField(null=True)),
                ('mac_address', models.TextField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='network_devices',
            field=models.ManyToManyField(to='backbone.AssetHWNetworkDevice'),
        ),
        migrations.CreateModel(
            name='ReportHistory',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('created_at_time', models.DateTimeField(null=True)),
                ('number_of_pages', models.IntegerField(default=0)),
                ('number_of_downloads', models.IntegerField(default=0)),
                ('size', models.BigIntegerField(default=0)),
                ('b64_size', models.BigIntegerField(default=0)),
                ('type', models.TextField(null=True)),
                ('filename', models.TextField(null=True)),
                ('created_by_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('progress', models.IntegerField(default=0)),
            ],
        ),
        migrations.AlterField(
            model_name='partition',
            name='size',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(
            code=functools.partial(convert_size, *(), **{'factor': 1048576}),
            reverse_code=functools.partial(convert_size, *(), **{'factor': 9.5367431640625e-07}),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='partition_table',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='backbone.partition_table'),
        ),
        migrations.CreateModel(
            name='LogicalDisc',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('device_name', models.CharField(max_length=128)),
                ('size', models.BigIntegerField(null=True)),
                ('free_space', models.BigIntegerField(null=True)),
                ('partition_fs', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.partition_fs')),
                ('partitions', models.ManyToManyField(to='backbone.partition')),
            ],
        ),
        migrations.CreateModel(
            name='ConfigServiceEnum',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('enum_name', models.CharField(default=b'', max_length=255, unique=True)),
                ('name', models.CharField(default=b'', max_length=255, unique=True)),
                ('info', models.TextField(blank=True, default=b'')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('root_service', models.BooleanField(default=True)),
            ],
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, b'PACKAGE'), (2, b'HARDWARE'), (3, b'LICENSE'), (4, b'UPDATE'), (5, b'LSHW'), (6, b'PROCESS'),
                                               (7, b'PENDING_UPDATE'), (8, b'DMI'), (9, b'PCI'), (10, b'PRETTYWINHW'), (11, b'PARTITION')], default=1),
        ),
        migrations.AlterField(
            model_name='device',
            name='act_partition_table',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='act_partition_table',
                to='backbone.partition_table'
            ),
        ),
        migrations.AlterField(
            model_name='device',
            name='partition_table',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='new_partition_table', to='backbone.partition_table'),
        ),
        migrations.AddField(
            model_name='config',
            name='config_service_enum',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.ConfigServiceEnum'),
        ),
        migrations.RemoveField(
            model_name='config',
            name='system_config',
        ),
        migrations.AddField(
            model_name='config_catalog',
            name='priority',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='reporthistory',
            name='file_hash',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='reporthistory',
            name='hash_algorithm',
            field=models.TextField(null=True),
        ),
        migrations.RemoveField(
            model_name='assetupdateentry',
            name='asset_run',
        ),
        migrations.RemoveField(
            model_name='assetupdateentry',
            name='created',
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='installed_updates',
            field=models.ManyToManyField(related_name='assetbatch_installed_updates', to='backbone.AssetUpdateEntry'),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='pending_updates',
            field=models.ManyToManyField(related_name='assetbatch_pending_updates', to='backbone.AssetUpdateEntry'),
        ),
        migrations.RemoveField(
            model_name='mon_dist_master',
            name='md_version',
        ),
        migrations.CreateModel(
            name='HardwareFingerPrint',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('fingerprint', models.TextField(default=b'')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.device')),
                ('changecount', models.IntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name='RouteTrace',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('session_id', models.CharField(default=b'', max_length=64)),
                ('user_id', models.IntegerField(default=0)),
                ('from_name', models.CharField(max_length=64)),
                ('to_name', models.CharField(max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_completed',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_runs',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_runs_error',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_runs_ok',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='run_result',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='run_time',
        ),
        migrations.AlterField(
            model_name='assetbatch',
            name='run_status',
            field=models.IntegerField(
                choices=[(1, b'PLANNED'), (2, b'RUNNING'), (3, b'FINISHED_RUNS'), (4, b'GENERATING_ASSETS'), (5, b'FINISHED')],
                default=1
            ),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_status',
            field=models.IntegerField(
                choices=[(1, b'PLANNED'), (2, b'SCANNING'), (3, b'FINISHED_SCANNING'), (4, b'GENERATING_ASSETS'), (5, b'FINISHED')],
                default=1
            ),
        ),
        migrations.RunPython(
            code=fix_assetbatch_and_assetrun,
        ),
        migrations.DeleteModel(
            name='AssetHWHDDEntry',
        ),
        migrations.RenameField(
            model_name='assethwcpuentry',
            old_name='cpuname',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='assethwgpuentry',
            old_name='gpuname',
            new_name='name',
        ),
        migrations.RemoveField(
            model_name='assethwgpuentry',
            name='driverversion',
        ),
        migrations.AddField(
            model_name='partition_disc',
            name='serial',
            field=models.TextField(default=b''),
        ),
        migrations.AddField(
            model_name='partition_disc',
            name='size',
            field=models.BigIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='staticassettemplate',
            name='type',
            field=models.CharField(max_length=256),
        ),
        migrations.RunPython(
            code=rename_staticassettemplate_type,
        ),
        migrations.RunPython(
            code=fix_noneditable_dvs_scopes,
        ),
        migrations.CreateModel(
            name='icswEggBasket',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('dummy', models.BooleanField(default=False)),
                ('valid_from', models.DateField()),
                ('valid_to', models.DateField()),
                ('is_valid', models.BooleanField(default=True)),
                ('eggs', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='icswEggConsumer',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('xml_node_reference', models.TextField(default=b'')),
                ('action', models.CharField(default=b'', max_length=63)),
                ('multiplier', models.IntegerField(default=1)),
                ('dynamic_multiplier', models.BooleanField(default=False)),
                ('valid', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('config_service_enum', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.ConfigServiceEnum')),
                ('content_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
            ],
            options={
                'ordering': ('content_type__model', 'config_service_enum__enum_name', 'action'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='icswEggCradle',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('system_cradle', models.BooleanField(default=True)),
                ('installed', models.IntegerField(default=0)),
                ('available', models.IntegerField(default=0)),
                ('grace_days', models.IntegerField(default=14)),
                ('grace_start', models.DateTimeField(null=True)),
                ('limit_grace', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='icswEggEvaluationDef',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('content', models.TextField(default=b'')),
                ('dummy', models.BooleanField(default=False)),
                ('active', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('egg_cradle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.icswEggCradle')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='icswEggRequest',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('object_id', models.IntegerField(null=True)),
                ('weight', models.IntegerField(default=0)),
                ('is_lock', models.BooleanField(default=False)),
                ('valid', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('egg_consumer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.icswEggConsumer')),
                ('valid_until', models.DateTimeField(default=None, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='icsweggconsumer',
            name='egg_cradle',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.icswEggCradle'),
        ),
        migrations.AddField(
            model_name='icsweggconsumer',
            name='egg_evaluation_def',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.icswEggEvaluationDef'),
        ),
        migrations.AddField(
            model_name='icsweggbasket',
            name='egg_cradle',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.icswEggCradle'),
        ),
        migrations.AddField(
            model_name='icsweggbasket',
            name='license',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.License'),
        ),
        migrations.AddField(
            model_name='icsweggconsumer',
            name='consumed',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='license',
            options={'ordering': ('idx',), 'verbose_name': 'License'},
        ),
        migrations.AddField(
            model_name='logicaldisc',
            name='partition_table',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.partition_table'),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, b'PACKAGE'), (2, b'HARDWARE'), (3, b'LICENSE'), (4, b'UPDATE'), (5, b'LSHW'),
                                               (6, b'PROCESS'), (7, b'PENDING_UPDATE'), (8, b'DMI'), (9, b'PCI'), (10, b'PRETTYWINHW'),
                                               (11, b'PARTITION'), (12, b'LSBLK')], default=1),
        ),
        migrations.AddField(
            model_name='mon_dist_master',
            name='livestatus_version',
            field=models.CharField(default=b'', max_length=128),
        ),
        migrations.AddField(
            model_name='mon_dist_slave',
            name='livestatus_version',
            field=models.CharField(default=b'', max_length=128),
        ),
        migrations.AddField(
            model_name='icsweggconsumer',
            name='timeframe_secs',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, b'PACKAGE'), (2, b'HARDWARE'), (3, b'LICENSE'), (4, b'UPDATE'), (5, b'LSHW'),
                                               (6, b'PROCESS'), (7, b'PENDING_UPDATE'), (8, b'DMI'), (9, b'PCI'), (10, b'PRETTYWINHW'),
                                               (11, b'PARTITION'), (12, b'LSBLK'), (13, b'XRANDR')], default=1),
        ),
        migrations.AddField(
            model_name='mon_dist_master',
            name='full_build',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='mon_dist_slave',
            name='full_build',
            field=models.BooleanField(default=True),
        ),
        migrations.DeleteModel(
            name='AssetHWLogicalEntry',
        ),
        migrations.RemoveField(
            model_name='assethwdisplayentry',
            name='type',
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='cpus_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='displays_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='gpus_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='installed_updates_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='memory_modules_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='network_devices_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='partition_table_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='pending_updates_status',
            field=models.IntegerField(default=0),
        ),
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
        migrations.CreateModel(
            name='AssetPackageVersionInstallInfo',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('timestamp', models.BigIntegerField(null=True)),
                ('size', models.BigIntegerField(null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='assetpackageversion',
            name='size',
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='installed_packages_status',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='assetpackageversioninstallinfo',
            name='package_version',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.AssetPackageVersion'),
        ),
        migrations.AddField(
            model_name='assetbatch',
            name='installed_packages',
            field=models.ManyToManyField(to='backbone.AssetPackageVersionInstallInfo'),
        ),
    ]
