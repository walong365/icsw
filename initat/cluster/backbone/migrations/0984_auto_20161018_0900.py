# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-18 07:00


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0983_role_based_scheme_squashed_1021_auto_20161017_0830'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='mon_trace',
            new_name='MonHostTrace',
        ),
        migrations.AlterField(
            model_name='assetpackage',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='assetpackage',
            name='package_type',
            field=models.IntegerField(choices=[(1, b'WINDOWS'), (2, b'LINUX')]),
        ),
    ]
