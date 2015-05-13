#!/bin/bash -ex

export DJANGO_SETTINGS_MODULE=initat.cluster.settings
CLUSTER=./initat/cluster/
MANAGE=${CLUSTER}/manage.py
MIGRATIONS=${CLUSTER}/backbone/migrations

rm -rf ${MIGRATIONS}
$MANAGE migrate

python-init << END
import django
django.setup()

from django.contrib.contenttypes.models import ContentType
ContentType.objects.all().delete()
END

$MANAGE loaddata baca-dump.json
