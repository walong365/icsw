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

class RunStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    ENDED = 2


class AssetRun(models.Model):
    idx = models.AutoField(primary_key=True)

    run_index = models.IntegerField(default=1)

    run_status = models.IntegerField(choices=[(status.value, status.name) for status in RunStatus])

    run_start_time = models.DateTimeField(auto_now_add=True)

    run_end_time = models.DateTimeField()

    asset_batch = models.ForeignKey("AssetBatch")

    device = models.ForeignKey("backbone.models.device")


class AssetBatch(models.Model):
    idx = models.AutoField(primary_key=True)


