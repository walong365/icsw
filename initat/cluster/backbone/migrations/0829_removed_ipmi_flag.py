# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import Q


def migrate_ipmi_flag(apps, schema_editor):
    device = apps.get_model("backbone", "device")
    comcap = apps.get_model("backbone", "ComCapability")
    try:
        _ipmi_com = comcap.objects.get(Q(matchcode="ipmi"))
    except:
        # creating missing comcap
        _ipmi_com = comcap(
            matchcode="ipmi",
            name="IPMI",
            info="Intelligent Platform Management Interface",
            port_spec="623/udp",
        )
        _ipmi_com.save()
    for _dev in device.objects.all():
        if _dev.ipmi_capable:
            _already_there = _dev.com_capability_list.filter(Q(matchcode="ipmi")).count()
            if not _already_there:
                _dev.com_capability_list.add(_ipmi_com)


def dummy_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    reversible = True

    dependencies = [
        ('backbone', '0828_added_com_capabilities'),
    ]

    operations = [
        migrations.RunPython(migrate_ipmi_flag, reverse_code=dummy_reverse),
        migrations.RemoveField(
            model_name='device',
            name='ipmi_capable',
        ),
        migrations.AlterField(
            model_name='device',
            name='active_scan',
            field=models.CharField(default=b'', max_length=16, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kpidatasourcetuple',
            name='kpi',
            field=models.ForeignKey(to='backbone.Kpi', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='kpistoredresult',
            name='kpi',
            field=models.OneToOneField(to='backbone.Kpi'),
            preserve_default=True,
        ),
    ]
