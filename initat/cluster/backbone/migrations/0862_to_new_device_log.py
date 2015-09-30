# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import Q


def revert_to_old_format(apps, schema_editor):
    pass


def to_new_log_format(apps, schema_editor):
    log_status = apps.get_model("backbone", "log_status")
    devicelog = apps.get_model("backbone", "devicelog")
    log_source = apps.get_model("backbone", "log_source")
    LogLevel = apps.get_model("backbone", "LogLevel")
    LogSource = apps.get_model("backbone", "LogSource")
    DeviceLogEntry = apps.get_model("backbone", "DeviceLogEntry")
    background_job_run = apps.get_model("backbone", "background_job_run")
    cur_c = DeviceLogEntry.objects.all().count()
    if not cur_c:
        print("migrating to new logging scheme, logs to handle: {:d}".format(devicelog.objects.all().count()))
        # old to new log_source dict
        _ls_dict = {}
        for _ls in log_source.objects.all():
            _ls_dict[_ls.pk] = LogSource(
                identifier=_ls.identifier,
                description=_ls.description,
                device=_ls.device,
            )
            _ls_dict[_ls.pk].save()
        # old to new log_status (Level) dict
        _ll_dict = {}
        for _ls in log_status.objects.all():
            _ll_dict[_ls.pk] = LogLevel.objects.get(
                Q(identifier={
                    "c": "c",
                    "w": "w",
                    "e": "e"
                }.get(_ls.identifier, "o"))
            )
        _user_ls = {}
        for _le in devicelog.objects.all().select_related("user", "device", "log_source"):
            _source = _ls_dict[_le.log_source_id]
            _new_le = DeviceLogEntry.objects.create(
                device=_le.device,
                source=_source,
                user=_le.user,
                level=_ll_dict[_le.log_status_id],
                text=_le.text,
            )
            # to preserve date
            _new_le.date = _le.date
            _new_le.save()
        # rewrite job runs
        _runs = background_job_run.objects.exclude(Q(log_source=None))
        print("background_runs to migrate: {:d}".format(_runs.count()))
        for _run in _runs:
            if _run.log_source_id in _ls_dict:
                _run.source = _ls_dict[_run.log_source_id]
            _run.log_source = None
            _run.save()
    else:
        print("new logging_scheme already in use")


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0861_userlogentry'),
    ]

    operations = [
        migrations.RunPython(
            to_new_log_format,
            revert_to_old_format
        ),
    ]
