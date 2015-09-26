# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import Q


def link_job_vars(apps, schema_editor):
    from initat.cluster.backbone.models import RMSJobVariable
    unset_vars = RMSJobVariable.objects.filter(Q(rms_job_run=None))
    if unset_vars.count():
        print("Migrating {:d} RMSJobVariables".format(unset_vars.count()))
        for unset_var in unset_vars:
            unset_var.rms_job_run = unset_var.rms_job.rms_job_run_set.all()[0]
            unset_var.save()


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0858_rmsjobvariable_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='rmsjobvariable',
            name='rms_job_run',
            field=models.ForeignKey(to='backbone.rms_job_run', null=True),
        ),
        migrations.RunPython(link_job_vars),
    ]
