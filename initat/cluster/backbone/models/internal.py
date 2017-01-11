# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#

""" model definitions, internal stuff (database version, patch levels, ....) """



from django.db import models
from django.db.models import Q
from django.db.utils import ProgrammingError, DatabaseError
from initat.cluster.backbone.models.functions import memoize_with_expiry


__all__ = [
    "ICSWVersion",
    "VERSION_NAME_LIST",
]


VERSION_NAME_LIST = ["database", "software", "models"]


class ICSWVersion(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=63,
        choices=[
            ("database", "Database scheme"),
            ("software", "Software package version"),
            ("models", "Models version"),
        ]
    )
    version = models.CharField(max_length=128)
    # to group version entries
    insert_idx = models.IntegerField(default=1)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    @memoize_with_expiry(5)
    def get_latest_db_dict():
        try:
            if ICSWVersion.objects.all().count():
                _latest_idx = ICSWVersion.objects.all().order_by("-idx")[0].insert_idx
                return {
                    _db.name: _db.version for _db in ICSWVersion.objects.filter(
                        Q(insert_idx=_latest_idx)
                    )
                }
            else:
                return {}
        except (ProgrammingError, DatabaseError):
            # model not defined
            return {}
