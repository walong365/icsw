# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-17 13:54


import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [('backbone', '0968_staticassettemplatefield_hidden'), ('backbone', '0969_auto_20160728_1328'), ('backbone', '0970_auto_20160728_1707'),
                ('backbone', '0971_auto_20160808_1435'), ('backbone', '0972_staticassettemplatefield_show_in_overview'),
                ('backbone', '0973_auto_20160809_1348'), ('backbone', '0974_auto_20160810_1606'), ('backbone', '0975_auto_20160811_0840'),
                ('backbone', '0976_auto_20160811_0949'), ('backbone', '0977_auto_20160811_2043'), ('backbone', '0978_device_variable_dvs_allowed_name'),
                ('backbone', '0979_auto_20160812_1819'), ('backbone', '0980_device_variable_scope_priority'), ('backbone', '0981_auto_20160824_2011')]

    dependencies = [
        ('backbone', '0967_category_asset'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='hidden',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='DeviceClass',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default=b'', max_length=64, unique=True)),
                ('description', models.CharField(default=b'', max_length=128)),
                ('limitations', models.TextField(default=b'', null=True)),
                ('system_class', models.BooleanField(default=False)),
                ('default_system_class', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('create_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='device',
            name='device_class',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.DeviceClass'),
        ),
        migrations.RenameField(
            model_name='staticassetfieldvalue',
            old_name='user',
            new_name='change_user',
        ),
        migrations.AddField(
            model_name='staticasset',
            name='create_user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='show_in_overview',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='consumable_critical_value',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='consumable_start_value',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='consumable_warn_value',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staticassetfieldvalue',
            name='value_text',
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='default_value_text',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='field_type',
            field=models.IntegerField(choices=[(1, b'INTEGER'), (2, b'STRING'), (3, b'DATE'), (4, b'TEXT')]),
        ),
        migrations.AlterModelOptions(
            name='staticassettemplatefield',
            options={'ordering': ['ordering']},
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='ordering',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='date_check',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='date_critical_value',
            field=models.IntegerField(default=30),
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='date_warn_value',
            field=models.IntegerField(default=60),
        ),
        migrations.AlterField(
            model_name='staticassettemplatefield',
            name='default_value_text',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.RenameModel(
            old_name='dvs_allowed_names',
            new_name='dvs_allowed_name',
        ),
        migrations.AddField(
            model_name='device_variable',
            name='dvs_allowed_name',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.dvs_allowed_name'),
        ),
        migrations.AddField(
            model_name='device_variable_scope',
            name='description',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.AddField(
            model_name='dvs_allowed_name',
            name='editable',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='dvs_allowed_name',
            name='description',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.AlterField(
            model_name='dvs_allowed_name',
            name='group',
            field=models.CharField(blank=True, default=b'', max_length=127),
        ),
        migrations.AddField(
            model_name='device_variable_scope',
            name='priority',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default=b'', max_length=64, unique=True)),
                ('description', models.TextField(default=b'')),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='RoleObjectPermission',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('level', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('csw_object_permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.csw_object_permission')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.Role')),
            ],
            options={
                'verbose_name': 'Global Ooject permissions of Role',
            },
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('level', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('csw_permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.csw_permission')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.Role')),
            ],
            options={
                'verbose_name': 'Global permissions of Role',
            },
        ),
        migrations.RemoveField(
            model_name='group',
            name='object_permissions',
        ),
        migrations.RemoveField(
            model_name='group',
            name='permissions',
        ),
        migrations.RemoveField(
            model_name='user',
            name='object_permissions',
        ),
        migrations.RemoveField(
            model_name='user',
            name='permissions',
        ),
        migrations.AddField(
            model_name='role',
            name='create_user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='role',
            name='object_perms',
            field=models.ManyToManyField(blank=True, related_name='role_perms', through='backbone.RoleObjectPermission', to='backbone.csw_object_permission'),
        ),
        migrations.AddField(
            model_name='role',
            name='perms',
            field=models.ManyToManyField(blank=True, related_name='role_perms', through='backbone.RolePermission', to='backbone.csw_permission'),
        ),
        migrations.AddField(
            model_name='group',
            name='roles',
            field=models.ManyToManyField(blank=True, related_name='role_groups', to='backbone.Role'),
        ),
        migrations.AddField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(blank=True, related_name='role_users', to='backbone.Role'),
        ),
    ]
