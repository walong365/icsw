# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-04 15:51

from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def dummy_reverse(apps, schema_editor):
    pass


def migrate_special_commands(apps, schema_editor):
    mcc = apps.get_model("backbone", "mon_check_command")
    mccs = apps.get_model("backbone", "mon_check_command_special")
    # delete all one-to-one relations
    # mapping for meta specials
    _m_map = {}
    meta_check_command = None
    _conv_1 = 0
    _conv_2 = 0
    for _obj in mccs.objects.filter(Q(dummy_mcc__isnull=False)):
        _conv_1 += 1
        # shadow already created
        # copy command line and other values to obj
        _obj.dummy_mcc.command_line = _obj.command_line,strip() or "/bin/true",
        _obj.dummy_mcc.description = _obj.description
        _obj.dummy_mcc.name = _obj.name
        _obj.dummy_mcc.uuid = ""
        _obj.dummy_mcc.is_special_command = True
        _obj.dummy_mcc.is_special_meta = _obj.meta
        if _obj.parent_id:
            _m_map[_obj.idx] = _obj.dummy_mcc_id
        if _obj.meta:
            meta_check_command = _obj.dummy_mcc
        _obj.dummy_mcc.save(
            update_fields=[
                "command_line", "is_special_command", "is_special_meta",
                "description", "name",
            ]
        )
    for _obj in mccs.objects.filter(Q(dummy_mcc__isnull=True)):
        _conv_2 += 1
        # no shadow created, create mcc from mccs
        # create command
        # print("*", _obj.name)
        mcc_obj = mcc(
            name=_obj.name,
            command_line=_obj.command_line.strip() or "/bin/true",
            description=_obj.description,
            is_special_command=True,
            is_special_meta=_obj.meta,
        )
        mcc_obj.save()
        if _obj.parent_id:
            _m_map[_obj.idx] = mcc_obj.idx
        if _obj.meta:
            meta_check_command = mcc_obj
        # print("Q", _obj)
    if meta_check_command is not None:
        for _cc_idx in _m_map.values():
            _mcc = mcc.objects.get(Q(idx=_cc_idx))
            _mcc.special_parent = meta_check_command
            _mcc.save(update_fields=["special_parent"])
    print(
        "MCC convertion: {:d} (shadow), {:d} (direct)".format(
            _conv_1,
            _conv_2
        )
    )
    # sys.exit(0)
    # print(mcc.objects.all().count())
    # print(mccs.objects.all().count())


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1039_auto_20170204_1651'),
    ]

    operations = [
        migrations.RunPython(migrate_special_commands, reverse_code=dummy_reverse),
    ]
