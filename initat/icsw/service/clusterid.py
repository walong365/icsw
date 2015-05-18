#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

""" return ClusterID if DB is present """


def get_cluster_id():
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

    cluster_id = None
    try:
        from django.conf import settings
    except:
        pass
    else:
        from django.db import connection
        try:
            _sm = settings.SATELLITE_MODE
        except:
            _sm = False
        if _sm:
            pass
        else:
            import django
            try:
                django.setup()
            except:
                pass
            else:
                from django.db.models import Q
                from initat.cluster.backbone.models import device_variable
                _vars = device_variable.objects.values_list("val_str", flat=True).filter(
                    Q(name="CLUSTER_ID") &
                    Q(device__device_group__cluster_device_group=True)
                )
                if len(_vars):
                    cluster_id = _vars[0]
    return cluster_id