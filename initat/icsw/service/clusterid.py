#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-client
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from initat.constants import GEN_CS_NAME
from initat.tools import config_store


def get_safe_cluster_var(var_name, default=None):
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

    var_value = default
    try:
        from django.conf import settings
    except:
        pass
    else:
        from django.db import connection
        _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
        try:
            _sm = _cs["mode.is.satellite"]
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
                from initat.cluster.backbone.models import device_variable
                if var_name == "name":
                    var_value = device_variable.objects.get_cluster_name(default)
                elif var_name == "id":
                    var_value = device_variable.objects.get_cluster_id(default)
                else:
                    var_value = "unknown attribute '{}'".format(var_name)
    return var_value


def get_safe_cluster_id(default=None):
    return get_safe_cluster_var("id", default)


def get_safe_cluster_name(default=None):
    return get_safe_cluster_var("name", default)
