# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-02 09:48


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('backbone', '1009_auto_20160930_1457'),
    ]

    operations = [
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
    ]
