# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-01-07 13:20


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0897_auto_20160105_1407'),
    ]

    operations = [
        migrations.AddField(
            model_name='monitoring_hint',
            name='value_blob',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='monitoring_hint',
            name='v_type',
            field=models.CharField(choices=[(b'f', b'float'), (b'i', b'integer'), (b'b', b'boolean'), (b's', b'string'), (b'B', b'blob')], default=b'f', max_length=6),
        ),
    ]
