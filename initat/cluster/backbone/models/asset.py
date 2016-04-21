#
# Copyright (C) 2016 Gregor Kaufmann, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <kaufmann@init.at>
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

from django.db import models
from enum import IntEnum
import uuid
import json

class Package:
    def __init__(self, name, version = None, size = None, install_date = None):
        self.name = name
        self.version = version
        self.size = size
        self.install_date = install_date

    def __repr__(self):
        s = "Name: %s" % self.name
        if self.version:
            s += " Version: %s" % self.version
        if self.size:
            s += " Size: %s" % self.size
        if self.install_date:
            s += " InstallDate: %s" % self.install_date

        return s

def get_packages_from_blob(blob):
    packages = []
    if str(blob[:3]) == "w32":
        l = json.loads(blob[:3])
        for (name, version, size, date) in l:
            packages.append(Package(name, version=version, size=size, install_date=date))

    return packages

class Hardware:
    pass

class License:
    pass

class Update:
    pass

class Software_Version:
    pass


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2
    LICENSE = 3
    UPDATE = 4
    SOFTWARE_VERSION = 5


class Asset(models.Model):
    idx = models.AutoField(primary_key=True)

    type = models.IntegerField(choices=[(_type.value, _type.name) for _type in AssetType])

    value = models.BinaryField()

    name = models.UUIDField(default=uuid.uuid4)

    asset_run = models.ForeignKey("AssetRun")

    def getAssetInstance(self):
        if self.type == AssetType.PACKAGE:
            return get_packages_from_blob(self.value)
        elif self.type == AssetType.HARDWARE:
            # todo interpret value blob
            return Hardware()
        elif self.type == AssetType.LICENSE:
            # todo interpret value blob
            return License()
        elif self.type == AssetType.UPDATE:
            # todo interpret value blob
            return Update()
        elif self.type == AssetType.SOFTWARE_VERSION:
            # todo interpret value blob
            return Software_Version()


class RunStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    ENDED = 3


class AssetRun(models.Model):
    idx = models.AutoField(primary_key=True)

    run_index = models.IntegerField(default=1)

    run_status = models.IntegerField(choices=[(status.value, status.name) for status in RunStatus], null=True)

    run_start_time = models.DateTimeField(null=True, blank=True)

    run_end_time = models.DateTimeField(null=True, blank=True)

    asset_batch = models.ForeignKey("AssetBatch", null=True)

    device = models.ForeignKey("backbone.device", null=True)


class AssetBatch(models.Model):
    idx = models.AutoField(primary_key=True)