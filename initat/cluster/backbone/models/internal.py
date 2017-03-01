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

"""

model definitions for

  - internal stuff (database version, patch levels, ....)
  - stores for config files

"""

from enum import Enum

from django.db import models
from django.db.models import Q
from django.db.utils import ProgrammingError, DatabaseError

from initat.cluster.backbone.models.functions import memoize_with_expiry

__all__ = [
    "ICSWVersion",
    "VERSION_NAME_LIST",
    "BackendConfigFile",
    "BackendConfigFileTypeEnum",
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


class BackendConfigFileTypeEnum(Enum):
    # mon check command
    mcc_json = "mcc_json"


class BackendConfigFile(models.Model):
    idx = models.AutoField(primary_key=True)
    # size
    file_size = models.IntegerField(default=0)
    # file type
    file_type = models.CharField(
        max_length=16,
        default=BackendConfigFileTypeEnum.mcc_json.value,
        choices=[
            (
                ft.value, ft.name.replace("_", " ")
            ) for ft in BackendConfigFileTypeEnum
        ],
    )
    # install device
    install_device = models.ForeignKey("backbone.device", null=True)
    # most recent, only one for can be most recent for each type
    most_recent = models.BooleanField(default=False)
    # same uploads, increase by one for every upload try on same file
    same_uploads = models.IntegerField(default=0)
    # content, compressed base64
    content = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get(
        cls,
        file_type: enumerate,
    ) -> object:
        try:
            _current = cls.objects.get(
                Q(
                    file_type=file_type.name,
                    most_recent=True,
                )
            )
        except cls.DoesNotExist:
            print("No BackendConfigType {} found".format(file_type.name))
            _current = None
        return _current

    @classmethod
    def store(
        cls,
        structure: object,
        file_size: int,
        file_type: enumerate,
        install_device: object,
    ) -> object:
        from initat.tools import server_command
        _compr = server_command.compress(structure, json=True)
        try:
            cfile = cls.objects.get(Q(content=_compr))
        except cls.DoesNotExist:
            _create = True
        else:
            cfile.same_uploads += 1
            cfile.save(update_fields=["same_uploads"])
            _create = False
        if _create:
            cfile = BackendConfigFile(
                file_size=file_size,
                file_type=file_type.name,
                most_recent=True,
                content=_compr,
                install_device=install_device,
            )
            cfile.save()
            # remove most recent from other instances
            cls.objects.filter(
                Q(file_type=file_type.name, most_recent=True)
            ).exclude(
                Q(idx=cfile.idx)
            ).update(
                most_recent=False
            )
        return cfile

    @property
    def structure(self):
        from initat.tools import server_command
        return server_command.decompress(self.content, json=True)

    def __str__(self):
        return "BackendConfigFile {} (size={:d}, idx={:d}, su={:d})".format(
            BackendConfigFileTypeEnum(self.file_type).name,
            self.file_size,
            self.idx,
            self.same_uploads,
        )
