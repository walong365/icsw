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
import pickle

from collections import Counter

class BaseAssetProcess:
    def __init__(self, name, pid):
        self.name = name
        self.pid = pid

    def __repr__(self):
        s = "Name: {} Pid: {}".format(self.name, self.pid)
        return s

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.name == other.name \
               and self.pid == other.pid


    def __hash__(self):
        return hash((self.name, self.pid))

class BaseAssetPackage:
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

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.name == other.name \
               and self.version == other.version \
               and self.size == other.size \
               and self.install_date == other.install_date

    def __hash__(self):
        return hash((self.name, self.version, self.size, self.install_date))

class BaseAssetHardware:
    def __init__(self, type):
        self.type = type
        self.info_dict = {}

    def __repr__(self):
        s = "Type: %s" % self.type
        return s

class BaseAssetLicense:
    def __init__(self, name, license_key):
        self.name = name
        self.license_key = license_key

    def __repr__(self):
        s = "Name: %s Key: %s" % (self.name, self.license_key)

        return s

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.name == other.name \
               and self.license_key == other.license_key

    def __hash__(self):
        return hash((self.type, self.license_key))

class BaseAssetUpdate:
    def __init__(self, name, install_date = None, status = None):
        self.name = name
        self.install_date = install_date
        self.status = status

    def __repr__(self):
        s = "Name: %s" % self.name
        if self.install_date:
            s += " InstallDate: %s" % self.install_date
        if self.status:
            s += " InstallStatus: %s" % self.status

        return s

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.name == other.name \
               and self.install_date == other.install_date \
               and self.status == other.status

    def __hash__(self):
        return hash((self.name, self.install_date, self.status))

class BaseAssetSoftwareVersion:
    pass


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2
    LICENSE = 3
    UPDATE = 4
    SOFTWARE_VERSION = 5
    PROCESS = 6


class Asset(models.Model):
    idx = models.AutoField(primary_key=True)

    type = models.IntegerField(choices=[(_type.value, _type.name) for _type in AssetType])

    value = models.TextField()

    name = models.UUIDField(default=uuid.uuid4)

    asset_run = models.ForeignKey("AssetRun")

    def getAssetInstance(self):
        return pickle.loads(self.value)

class RunStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    ENDED = 3

W32_SCAN_TYPE_PREFIX = "w32"

from lxml import etree

#flatten xml into bahlist
def generate_bahs(root, bahlist):
    bah = BaseAssetHardware(root.get("type"))
    bahlist.append(bah)
    for elem in root.iterchildren("info"):
        bah.info_dict[elem.get("name")] = elem.get("value")
    for elem in root.iterchildren("object"):
        generate_bahs(elem, bahlist)

def get_base_assets_from_raw_result(blob, runtype):
    assets = []
    if runtype == AssetType.PACKAGE:
        if str(blob[:3]) == W32_SCAN_TYPE_PREFIX:
            l = json.loads(blob[3:])
            for (name, version, size, date) in l:
                assets.append(BaseAssetPackage(name, version=version, size=size, install_date=date))
        #todo check/interpret different scan types

    elif runtype == AssetType.HARDWARE:
        if str(blob[:3]) == W32_SCAN_TYPE_PREFIX:
            root = etree.fromstring(blob[5:-4].encode("ascii"))
            assert(root.tag == "topology")

            for _child in root.iterchildren():
                generate_bahs(_child, assets)
        #todo check/interpret different scan types

    elif runtype == AssetType.LICENSE:
        if str(blob[:3]) == W32_SCAN_TYPE_PREFIX:
            l = json.loads(blob[3:])
            for (name, licensekey) in l:
                assets.append(BaseAssetLicense(name, license_key=licensekey))
        #todo check/interpret different scan types

    elif runtype == AssetType.UPDATE:
        if str(blob[:3]) == W32_SCAN_TYPE_PREFIX:
            l = json.loads(blob[3:])
            for (name, date, status) in l:
                assets.append(BaseAssetUpdate(name, install_date = date, status=status))
        #todo check/interpret different scan types

    elif runtype == AssetType.SOFTWARE_VERSION:
        #todo interpret value blob
        pass

    elif runtype == AssetType.PROCESS:
        if str(blob[:3]) == W32_SCAN_TYPE_PREFIX:
            l = json.loads(blob[3:])
            for (name, pid) in l:
                assets.append(BaseAssetProcess(name, pid))

    return assets

class AssetRun(models.Model):
    idx = models.AutoField(primary_key=True)

    run_index = models.IntegerField(default=1)

    run_status = models.IntegerField(choices=[(status.value, status.name) for status in RunStatus], null=True)

    run_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in AssetType], null=True)

    run_start_time = models.DateTimeField(null=True, blank=True)

    run_end_time = models.DateTimeField(null=True, blank=True)

    asset_batch = models.ForeignKey("AssetBatch", null=True)

    device = models.ForeignKey("backbone.device", null=True)

    raw_result_str = models.TextField(null=True)

    raw_result_interpreted = models.BooleanField(default=False)


    def generate_assets(self):
        if self.raw_result_interpreted or not self.raw_result_str:
            return False
        self.raw_result_interpreted = True

        for _base_asset in get_base_assets_from_raw_result(self.raw_result_str, self.run_type):
            _package_dump = pickle.dumps(_base_asset)
            self.asset_set.create(type=self.run_type, value=_package_dump)

        self.save()
        return True

    def get_asset_changeset(self, other_asset_run):
        self.generate_assets()
        other_asset_run.generate_assets()
        this_assets = [_asset.getAssetInstance() for _asset in self.asset_set.all()]
        other_assets = [_asset.getAssetInstance() for _asset in other_asset_run.asset_set.all()]

        return list(set(this_assets).symmetric_difference(set(other_assets)))

    def diff_to_prev_run(self):
        if self.run_index == 0:
            return []

        return self.get_asset_changeset(self.device.assetrun_set.get(run_index=self.run_index-1))

class AssetBatch(models.Model):
    idx = models.AutoField(primary_key=True)

    def completed(self):
        for assetrun in self.assetrun_set.all():
            if not assetrun.run_status == RunStatus.ENDED:
                return False
        return True