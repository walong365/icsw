# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import migrations, models


def db_limit_1():
    # return True if databases do not support some unique_together combinations
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


def add_graph_setting_size(apps, schema_editor):
    graph_setting_size = apps.get_model("backbone", "GraphSettingSize")
    graph_setting = apps.get_model("backbone", "GraphSetting")
    if graph_setting.objects.all().count():
        _default = graph_setting_size.objects.filter(models.Q(default=True))
        if len(_default):
            _default = _default[0]
        else:
            _default = graph_setting_size(
                name="normal",
                default=True,
                width=640,
                height=300,
            )
            _default.save()
        for _gs in graph_setting.objects.all():
            if not _gs.graph_setting_size_id:
                _gs.graph_setting_size = _default
                _gs.save()


def dummy_call(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0871_auto_20151006_1428'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphSettingSize',
            fields=[
                ('idx', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', unique=True, max_length=64)),
                ('default', models.BooleanField(default=False)),
                ('width', models.IntegerField(default=0)),
                ('height', models.IntegerField(default=0)),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        )
    ]
    if not db_limit_1():
        operations.append(
            migrations.AlterUniqueTogether(
                name='graphsettingsize',
                unique_together=set([('width', 'height')]),
            )
        )
    operations.extend(
        [
            migrations.AddField(
                model_name='graphsetting',
                name='graph_setting_size',
                field=models.ForeignKey(to='backbone.GraphSettingSize', null=True),
            ),
            migrations.RunPython(
                add_graph_setting_size,
                dummy_call,
            ),
        ]
    )
