# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-24 05:18


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0937_staticassettemplate_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticassettemplate',
            name='parent_template',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.StaticAssetTemplate'),
        ),
    ]
