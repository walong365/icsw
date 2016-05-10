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

import uuid
import json
import pickle
import base64
import marshal
import datetime
import bz2

from lxml import etree
from django.db import models
from enum import IntEnum
from rest_framework import serializers
import django.utils.timezone

########################################################################################################################
# Functions
########################################################################################################################


# flatten xml into bahlist
def generate_bahs(root, bahlist):
    bah = BaseAssetHardware(root.get("type"))
    bahlist.append(bah)
    for elem in root.iterchildren("info"):
        bah.info_dict[elem.get("name")] = elem.get("value")
    for elem in root.iterchildren("object"):
        generate_bahs(elem, bahlist)


def get_base_assets_from_raw_result(blob, runtype, scantype):
    assets = []

    if not blob:
        return assets

    if runtype == AssetType.PACKAGE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, version, size, date) in l:
                assets.append(BaseAssetPackage(name,
                                               version=version,
                                               size=size,
                                               install_date=date))
        elif scantype == ScanType.HM:
            package_dict = pickle.loads(bz2.decompress(base64.b64decode(blob)))
            for package_name in package_dict:
                for versions_dict in package_dict[package_name]:
                    assets.append(BaseAssetPackage(package_name,
                                                   version=versions_dict['version'],
                                                   size=versions_dict['size'],
                                                   release=versions_dict['release']))
    elif runtype == AssetType.HARDWARE:
        s = blob
        if scantype == ScanType.NRPE:
            s = blob[2:-4].encode('ascii')
        elif scantype == ScanType.HM:
            s = bz2.decompress(base64.b64decode(blob))

        root = etree.fromstring(s)
        assert (root.tag == "topology")

        for _child in root.iterchildren():
            generate_bahs(_child, assets)

    elif runtype == AssetType.LICENSE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, licensekey) in l:
                assets.append(BaseAssetLicense(name, license_key=licensekey))
        elif scantype == ScanType.HM:
            # todo implement me (--> what do we want to gather/display here?)
            pass

    elif runtype == AssetType.UPDATE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, date, status) in l:
                assets.append(BaseAssetUpdate(name, install_date=date, status=status))
        elif scantype == ScanType.HM:
            # todo implement me (--> what do we want to gather/display here?)
            pass

    elif runtype == AssetType.SOFTWARE_VERSION:
        # todo implement me
        pass

    elif runtype == AssetType.PROCESS:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, pid) in l:
                assets.append(BaseAssetProcess(name, pid))
        elif scantype == ScanType.HM:
            process_dict = eval(bz2.decompress(base64.b64decode(blob)))
            for pid in process_dict:
                assets.append(BaseAssetProcess(process_dict[pid]['name'], pid))

    elif runtype == AssetType.PENDING_UPDATE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, optional) in l:
                assets.append(BaseAssetPendingUpdate(name, optional=optional))
        elif scantype == ScanType.HM:
            l = pickle.loads(bz2.decompress(base64.b64decode(blob)))
            for (name, version) in l:
                assets.append(BaseAssetPendingUpdate(name, version=version))

    return assets

########################################################################################################################
# Base Asset Classes
########################################################################################################################


class BaseAssetProcess(object):
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


class BaseAssetPackage(object):
    def __init__(self, name, version=None, release=None, size=None, install_date=None):
        self.name = name
        self.version = version
        self.release = release
        self.size = size
        self.install_date = install_date

    def __repr__(self):
        s = "Name: %s" % self.name
        if self.version:
            s += " Version: %s" % self.version
        if self.release:
            s += " Release: %s" % self.release
        if self.size:
            s += " Size: %s" % self.size
        if self.install_date:
            s += " InstallDate: %s" % self.install_date

        return s

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
            and self.name == other.name \
            and self.version == other.version \
            and self.release == other.release \
            and self.size == other.size \
            and self.install_date == other.install_date

    def __hash__(self):
        return hash((self.name, self.version, self.release, self.size, self.install_date))


class BaseAssetHardware(object):
    def __init__(self, type):
        self.type = type
        self.info_dict = {}

    def __repr__(self):
        s = "Type: %s" % self.type
        return s


class BaseAssetLicense(object):
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


class BaseAssetUpdate(object):
    def __init__(self, name, install_date=None, status=None):
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


class BaseAssetSoftwareVersion(object):
    pass


class BaseAssetPendingUpdate(object):
    def __init__(self, name, version=None, optional=None):
        self.name = name
        self.version = version
        self.optional = optional

    def __repr__(self):
        s = "Name: %s" % self.name
        if self.version:
            s += " Version: %s" % self.version
        if self.optional:
            s += " Optional: %s" % self.optional

        return s

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
            and self.name == other.name \
            and self.version == other.version \
            and self.optional == other.optional

    def __hash__(self):
        return hash((self.name, self.version, self.optional))

########################################################################################################################
# Enums
########################################################################################################################


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2
    LICENSE = 3
    UPDATE = 4
    SOFTWARE_VERSION = 5
    PROCESS = 6
    PENDING_UPDATE = 7


class ScanType(IntEnum):
    HM = 1
    NRPE = 2


class RunStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    ENDED = 3

########################################################################################################################
# (Django Database) Classes
########################################################################################################################


class Asset(models.Model):
    idx = models.AutoField(primary_key=True)

    type = models.IntegerField(choices=[(_type.value, _type.name) for _type in AssetType])

    value = models.TextField()

    name = models.UUIDField(default=uuid.uuid4)

    asset_run = models.ForeignKey("AssetRun")

    def getAssetInstance(self):
        return pickle.loads(self.value)


class AssetPackage(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.name == other.name

    def __hash__(self):
        return hash((self.name,))


class AssetPackageVersion(models.Model):
    idx = models.AutoField(primary_key=True)
    asset_package = models.ForeignKey("backbone.AssetPackage")
    size = models.IntegerField(default=0)
    version = models.TextField(default="", blank=True)
    release = models.TextField(default="", blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.version == other.version \
            and self.release == other.release

    def __hash__(self):
        return hash((self.version, self.release, self.size))


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

    scan_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in ScanType], null=True)

    packages = models.ManyToManyField(AssetPackageVersion)

    def generate_assets(self):
        if self.raw_result_interpreted or not self.raw_result_str:
            return get_base_assets_from_raw_result(self.raw_result_str, self.run_type, self.scan_type)
        self.raw_result_interpreted = True

        base_assets = get_base_assets_from_raw_result(self.raw_result_str, self.run_type, self.scan_type)
        for _base_asset in base_assets:
            _package_dump = pickle.dumps(_base_asset)
            self.asset_set.create(type=self.run_type, value=_package_dump)

        self.save()
        return base_assets

    def generate_assets_no_save(self):
        l = get_base_assets_from_raw_result(self.raw_result_str, self.run_type, self.scan_type)
        l.sort()
        return l

    def generate_assets_new(self):
        base_assets = get_base_assets_from_raw_result(self.raw_result_str, self.run_type, self.scan_type)
        for ba in base_assets:
            kwfilterdict = {}
            if self.run_type == AssetType.PACKAGE:
                name = ba.name
                version = ba.version if ba.version else ""
                release = ba.release if ba.release else ""
                size = ba.size if ba.size else 0

                #kwfilterdict['name'] = ba.name
                #kwfilterdict['version'] = ba.version
                #kwfilterdict['release'] = ba.release
                aps = AssetPackage.objects.filter(name=name)
                assert (len(aps) < 2)

                if aps:
                    ap = aps[0]

                    versions = ap.assetpackageversion_set.filter(version=version, release=release, size=size)
                    assert (len(versions) < 2)

                    if versions:
                        apv = versions[0]
                    else:
                        apv = AssetPackageVersion(asset_package=ap, version=version, release=release, size=size)
                        apv.save()

                    self.packages.add(apv)
                else:
                    ap = AssetPackage(name=name)
                    ap.save()
                    apv = AssetPackageVersion(asset_package=ap, version=version, release=release, size=size)
                    apv.save()
                    self.packages.add(apv)


            # elif self.run_type == AssetType.HARDWARE:
            #     # todo implement me
            #     break
            # elif self.run_type == AssetType.LICENSE:
            #     # todo implement me
            #     break
            # elif self.run_type == AssetType.UPDATE:
            #     # todo implement me
            #     break
            # elif self.run_type == AssetType.SOFTWARE_VERSION:
            #     # todo implement me
            #     break
            # elif self.run_type == AssetType.PROCESS:
            #     # todo implement me
            #     break
            # elif self.run_type == AssetType.PENDING_UPDATE:
            #     # todo implement me
            #     break
            # else:
            #     break
            #
            # assets = AssetPackage.objects.filter(**kwfilterdict)
            # assert(len(assets) < 2)
            #
            # if assets:
            #     asset = assets[0]
            #     if self.packages.filter(**kwfilterdict):
            #         continue
            # else:
            #     asset = AssetPackage(**kwfilterdict)
            #     asset.save()
            #
            # self.packages.add(asset)

        self.save()

    def get_asset_changeset(self, other_asset_run):
        # self.generate_assets()
        # other_asset_run.generate_assets()
        # this_assets = [_asset.getAssetInstance() for _asset in self.asset_set.all()]
        # other_assets = [_asset.getAssetInstance() for _asset in other_asset_run.asset_set.all()]
        this_assets = self.generate_assets_no_save()
        other_assets = other_asset_run.generate_assets_no_save()

        return set(this_assets).difference(other_assets)

    def diff_to_prev_run(self):
        if self.run_index == 0:
            return []

        return self.get_asset_changeset(self.device.assetrun_set.get(run_index=self.run_index - 1))


class AssetBatch(models.Model):
    idx = models.AutoField(primary_key=True)

    def completed(self):
        for assetrun in self.assetrun_set.all():
            if not assetrun.run_status == RunStatus.ENDED:
                return False
        return True

########################################################################################################################
# Serializers
########################################################################################################################


class AssetSerializer(serializers.ModelSerializer):
    assetstr = serializers.SerializerMethodField()

    def get_assetstr(self, obj):
        return str(obj.getAssetInstance())

    class Meta:
        model = Asset

class AssetPackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPackageVersion
        fields = ("idx", "size", "version", "release")


class AssetPackageSerializer(serializers.ModelSerializer):
    versions = AssetPackageVersionSerializer(many=True)
    class Meta:
        model = AssetPackage
        fields = ("idx", "name")


class AssetRunSerializer(serializers.ModelSerializer):
    device = serializers.SerializerMethodField()
    # asset_set = AssetSerializer(many=True)
    assets = serializers.SerializerMethodField()
    packages = AssetPackageVersionSerializer(many=True)

    def get_assets(self, obj):
        return [str(pkg) for pkg in obj.generate_assets_no_save()]

    def get_device(self, obj):
        if self.context and "device" in self.context:
            return self.context["device"]
        else:
            return 0

    class Meta:
        model = AssetRun
        fields = ("idx", "device", "run_index", "run_type", "assets",
                  "run_start_time", "run_end_time", "packages")


class DeviceInventory(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    inventory_type = models.CharField(
        max_length=255,
        choices=(
            ("lstopo", "LSTopo"),
            ("dmi", "DMI"),
            ("pci", "PCI"),
        )
    )
    # results from the same fetch run have the same run_idx
    run_idx = models.IntegerField(default=0)
    # serialized XML
    value = models.TextField()
    date = models.DateTimeField(auto_now_add=True)


class StaticAssetType(IntEnum):
    # related to a software
    LICENSE = 1
    # general contract
    CONTRACT = 2
    # special hardware
    HARDWARE = 3


class AssetTemplateFieldType(IntEnum):
    INTEGER = 1
    STRING = 2
    DATE = 3


# static assets
class StaticAssetTemplate(models.Model):
    # to be defined by administrator
    idx = models.AutoField(primary_key=True)
    # asset type
    type = models.IntegerField(choices=[(_type.value, _type.name) for _type in StaticAssetType])
    # name of Template
    name = models.CharField(max_length=128, unique=True)
    # is consumable
    consumable = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class StaticAssetTemplateField(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    field_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in AssetTemplateFieldType])
    # is optional
    optional = models.BooleanField(default=False)
    # default value
    default_value_str = models.CharField(default="", blank=True, max_length=255)
    default_value_int = models.IntegerField(default=0)
    default_value_date = models.DateField(default=django.utils.timezone.now)
    # bounds, for input checking
    has_bounds = models.BooleanField(default=False)
    value_int_lower_bound = models.IntegerField(default=0)
    value_int_upper_bound = models.IntegerField(default=0)
    # monitor flag, only for datefiles
    monitor = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class StaticAsset(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    # device
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)


class StaticAssetFieldValue(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset = models.ForeignKey("backbone.StaticAsset")
    # field
    static_asset_template_field = models.ForeignKey("backbone.StaticAssetTemplateField")
    # change user
    user = models.ForeignKey("backbone.user")
    # value
    value_str = models.CharField(null=True, blank=True, max_length=255, default=None)
    value_int = models.IntegerField(null=True, blank=True, default=None)
    value_date = models.DateField(null=True, blank=True, default=None)
    date = models.DateTimeField(auto_now_add=True)
