# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0880_auto_20151115_0252'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigTreeNode',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('is_dir', models.BooleanField(default=False)),
                ('is_link', models.BooleanField(default=False)),
                ('intermediate', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(default=None, to='backbone.device')),
                ('parent', models.ForeignKey(default=None, to='backbone.ConfigTreeNode', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='WrittenConfigFile',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('run_number', models.IntegerField(default=0)),
                ('uid', models.IntegerField(default=0, blank=True)),
                ('gid', models.IntegerField(default=0, blank=True)),
                ('mode', models.IntegerField(default=493, blank=True)),
                ('dest_type', models.CharField(max_length=8, choices=[(b'f', b'file'), (b'l', b'link'), (b'd', b'directory'), (b'e', b'erase'), (b'c', b'copy'), (b'i', b'internal')])),
                ('source', models.TextField(default=b'')),
                ('dest', models.TextField(default=b'')),
                ('error_flag', models.BooleanField(default=False)),
                ('content', models.TextField(default=b'', blank=True)),
                ('binary', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('config', models.ManyToManyField(to='backbone.config')),
                ('config_tree_node', models.OneToOneField(null=True, default=None, to='backbone.ConfigTreeNode')),
                ('device', models.ForeignKey(to='backbone.device')),
            ],
        ),
        migrations.RemoveField(
            model_name='tree_node',
            name='device',
        ),
        migrations.RemoveField(
            model_name='tree_node',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='wc_files',
            name='config',
        ),
        migrations.RemoveField(
            model_name='wc_files',
            name='device',
        ),
        migrations.RemoveField(
            model_name='wc_files',
            name='tree_node',
        ),
        migrations.DeleteModel(
            name='tree_node',
        ),
        migrations.DeleteModel(
            name='wc_files',
        ),
    ]
