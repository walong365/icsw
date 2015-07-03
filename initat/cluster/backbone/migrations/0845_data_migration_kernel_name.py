# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.db import migrations


def copy_kernel_name(apps, schema_editor):
    kernel = apps.get_model("backbone", "kernel")
    _names = set()
    for _kern in kernel.objects.all():
        if not _kern.display_name:
            new_name = _kern.name
            while True:
                if new_name in _names:
                    new_name = "{}X".format(new_name)
                else:
                    break
            _names.add(new_name)
            _kern.display_name = new_name
            _kern.save()


def dummy_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    reversible = True

    dependencies = [
        ('backbone', '0844_alter_kernel_model'),
    ]

    operations = [
        migrations.RunPython(copy_kernel_name, reverse_code=dummy_reverse)
    ]
