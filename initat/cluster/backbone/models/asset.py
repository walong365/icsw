#
# Copyright (C) 2016 Gregor Kaufmann, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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

import base64
import bz2
import datetime
import json
import pickle
import uuid

from django.utils import timezone, dateparse
import django.utils.timezone
from django.db import models
from django.db.models import Q
from enum import IntEnum
from lxml import etree

from initat.tools import server_command


########################################################################################################################
# Functions
########################################################################################################################


def get_base_assets_from_raw_result(asset_run, blob, runtype, scantype):
    assets = []

    if not blob:
        return assets

    if runtype == AssetType.PACKAGE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, version, size, date) in l:
                if size == "Unknown":
                    size = 0
                assets.append(
                    BaseAssetPackage(
                        name,
                        version=version,
                        size=size,
                        install_date=date,
                        package_type=PackageTypeEnum.WINDOWS
                    )
                )
        elif scantype == ScanType.HM:
            try:
                package_dict = server_command.decompress(blob, pickle=True)
            except:
                raise
            else:
                for package_name in package_dict:
                    for versions_dict in package_dict[package_name]:
                        assets.append(
                            BaseAssetPackage(
                                package_name,
                                version=versions_dict['version'],
                                size=versions_dict['size'],
                                release=versions_dict['release'],
                                package_type=PackageTypeEnum.LINUX
                            )
                        )
        # lookup cache
        lu_cache = {}
        for idx, ba in enumerate(assets):
            if idx % 100 == 0:
                lu_cache = {
                    _p.name: _p for _p in AssetPackage.objects.filter(
                        Q(name__in=[_x.name for _x in assets[idx:idx + 100]]) &
                        Q(package_type=ba.package_type)
                    ).prefetch_related(
                        "assetpackageversion_set"
                    )
                }
            name = ba.name
            version = ba.version if ba.version else ""
            release = ba.release if ba.release else ""
            size = ba.size if ba.size else 0
            package_type = ba.package_type

            # kwfilterdict['name'] = ba.name
            # kwfilterdict['version'] = ba.version
            # kwfilterdict['release'] = ba.release
            if name in lu_cache:
                ap = lu_cache[ba.name]

                versions = ap.assetpackageversion_set.filter(version=version, release=release, size=size)
                assert (len(versions) < 2)

                if versions:
                    apv = versions[0]
                else:
                    apv = AssetPackageVersion(asset_package=ap, version=version, release=release, size=size)
                    apv.save()
            else:
                ap = AssetPackage(name=name, package_type=package_type)
                ap.save()
                apv = AssetPackageVersion(asset_package=ap, version=version, release=release, size=size)
                apv.save()
            asset_run.packages.add(apv)

    elif runtype == AssetType.HARDWARE:
        if scantype == ScanType.NRPE:
            s = blob[2:-4].encode('ascii')
        elif scantype == ScanType.HM:
            s = bz2.decompress(base64.b64decode(blob))
        else:
            s = blob

        root = etree.fromstring(s)
        assert (root.tag == "topology")

        # lookup for structural entries
        _struct_lut = {}
        _root_tree = root.getroottree()
        struct_el = None
        for element in root.iter():
            if element.tag in ["topology", "object"]:
                # structural entry
                struct_el = AssetHardwareEntry(
                    type=element.tag,
                    attributes=json.dumps({key: value for key, value in element.attrib.iteritems()}),
                    asset_run=asset_run,
                )
                # get local path
                _path = _root_tree.getpath(element)
                _struct_lut[_path] = struct_el
                struct_el._info_dict = {}
                if element.getparent() is not None:
                    # parent_path
                    _parent = _struct_lut[_root_tree.getpath(element.getparent())]
                    struct_el.parent = _parent
                    struct_el.depth = _parent.depth + 1

                struct_el.save()
            else:
                _struct_el = _struct_lut[_root_tree.getpath(element.getparent())]
                _struct_el._info_dict.setdefault(element.tag, []).append(
                    json.dumps(
                        {key: value for key, value in element.attrib.iteritems()}
                    )
                )
        for _path, _el in _struct_lut.iteritems():
            _el.info_list = json.dumps(_el._info_dict)
            _el.save()

    elif runtype == AssetType.LICENSE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, licensekey) in l:
                new_lic = AssetLicenseEntry(
                    name=name,
                    license_key=licensekey,
                    asset_run=asset_run,
                )
                new_lic.save()
        elif scantype == ScanType.HM:
            # todo implement me (--> what do we want to gather/display here?)
            pass

    elif runtype == AssetType.PENDING_UPDATE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, optional) in l:
                new_pup = AssetUpdateEntry(
                    name=name,
                    installed=False,
                    asset_run=asset_run,
                    optional=optional,
                )
                new_pup.save()

        elif scantype == ScanType.HM:
            l = server_command.decompress(blob, pickle=True)
            for (name, version) in l:
                new_pup = AssetUpdateEntry(
                    name=name,
                    installed=False,
                    asset_run=asset_run,
                    # by definition linux updates are optional
                    optional=True,
                    new_version=version,
                )
                new_pup.save()

    elif runtype == AssetType.UPDATE:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            for (name, up_date, status) in l:
                new_up = AssetUpdateEntry(
                    name=name,
                    install_date=dateparse.parse_datetime(up_date),
                    status=status,
                    installed=True,
                    asset_run=asset_run,
                    optional=False,
                )
                new_up.save()
        elif scantype == ScanType.HM:
            # todo implement me (--> what do we want to gather/display here?)
            pass

    elif runtype == AssetType.SOFTWARE_VERSION:
        # todo implement me
        pass

    elif runtype == AssetType.PROCESS:
        if scantype == ScanType.NRPE:
            l = json.loads(blob)
            process_dict = {int(pid): {"name": name} for name, pid in l}
        elif scantype == ScanType.HM:
            process_dict = eval(bz2.decompress(base64.b64decode(blob)))
        for pid, stuff in process_dict.iteritems():
            new_proc = AssetProcessEntry(
                pid=pid,
                name=stuff["name"],
                asset_run=asset_run,
            )
            new_proc.save()

    return assets

########################################################################################################################
# Base Asset Classes
########################################################################################################################


class BaseAssetPackage(object):
    def __init__(self, name, version=None, release=None, size=None, install_date=None, package_type=None):
        self.name = name
        self.version = version
        self.release = release
        self.size = size
        self.install_date = install_date
        self.package_type = package_type

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
        if self.package_type:
            s += " PackageType: %s" % self.package_type

        return s

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
            and self.name == other.name \
            and self.version == other.version \
            and self.release == other.release \
            and self.size == other.size \
            and self.install_date == other.install_date \
            and self.package_type == other.package_type

    def __hash__(self):
        return hash((self.name, self.version, self.release, self.size, self.install_date, self.package_type))


# Enums
########################################################################################################################


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2  # lstopo
    LICENSE = 3
    UPDATE = 4
    SOFTWARE_VERSION = 5
    PROCESS = 6
    PENDING_UPDATE = 7
    DMI = 8
    PCI = 9


class ScanType(IntEnum):
    HM = 1
    NRPE = 2


class RunStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    ENDED = 3


class RunResult(IntEnum):
    UNKNOWN = 1
    SUCCESS = 2
    WARNING = 3
    FAILED = 4
    # canceled (no IP)
    CANCELED = 5


class PackageTypeEnum(IntEnum):
    WINDOWS = 1
    LINUX = 2

########################################################################################################################
# (Django Database) Classes
########################################################################################################################


class AssetPackage(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    package_type = models.IntegerField(choices=[(pt.value, pt.name) for pt in PackageTypeEnum])

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
            and self.name == other.name \
            and self.package_type == other.package_type

    def __hash__(self):
        return hash((self.name, self.package_type))


class AssetPackageVersion(models.Model):
    idx = models.AutoField(primary_key=True)
    asset_package = models.ForeignKey("backbone.AssetPackage")
    size = models.IntegerField(default=0)
    # for comment and / or info
    info = models.TextField(default="")
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


class AssetHardwareEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # type (from XML)
    type = models.TextField(default="")
    # json-serializes attribute dict
    attributes = models.TextField(default="")
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # depth
    depth = models.IntegerField(default=0)
    # json-serialized dict of all non-structural subentries
    """
    <page_type size="4096" count="4092876"/>
    <page_type size="2097152" count="0"/>
    <info name="DMIProductName" value="System Product Name"/>
    <info name="DMIProductVersion" value="System Version"/>
    <info name="DMIProductSerial" value="System Serial Number"/>
    <info name="DMIProductUUID" value="00A5001E-8C00-005E-A775-3085A99A7CAF"/>
    <info name="DMIBoardVendor" value="ASUSTeK COMPUTER INC."/>
    <info name="DMIBoardName" value="P9X79"/>
    <info name="DMIBoardVersion" value="Rev 1.xx"/>

    becomes
    {
        page_type: [{size: ..., count: ...}, {size: ..., count:....}]
        info: [{name: ..., value: ....}, {name: ..., value: ....}]
    }
    """
    info_list = models.TextField(default="")
    # link to parent
    parent = models.ForeignKey("backbone.AssetHardwareEntry", null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetHardwareEntry {}".format(self.type)

    class Meta:
        ordering = ("idx",)


class AssetLicenseEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(default="", max_length=255)
    # license key
    license_key = models.CharField(default="", max_length=255)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetLicense name={}".format(self.name)

    class Meta:
        ordering = ("name",)


class AssetUpdateEntry(models.Model):
    # also for pendingUpdates
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(default="", max_length=255)
    # version / release
    version = models.CharField(default="", max_length=255)
    release = models.CharField(default="", max_length=255)
    # vendor ?
    # KnowledgeBase idx
    kb_idx = models.IntegerField(default=0)
    # install date
    install_date = models.DateTimeField(null=True)
    # status, now as string
    status = models.CharField(default="", max_length=128)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # optional
    optional = models.BooleanField(default=True)
    # installed
    installed = models.BooleanField(default=False)
    # new version (for RPMs)
    new_version = models.CharField(default="", max_length=64)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetUpdate name={}".format(self.name)

    class Meta:
        ordering = ("name",)


class AssetProcessEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # Process ID
    pid = models.IntegerField(default=0)
    # Name
    name = models.CharField(default="", max_length=255)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetProcess pid={:d}".format(self.pid)

    class Meta:
        ordering = ("pid",)


class AssetRun(models.Model):
    idx = models.AutoField(primary_key=True)

    run_index = models.IntegerField(default=1)
    run_status = models.IntegerField(
        choices=[(status.value, status.name) for status in RunStatus],
        default=RunStatus.PLANNED.value,
    )
    run_result = models.IntegerField(
        choices=[(status.value, status.name) for status in RunResult],
        default=RunResult.UNKNOWN.value,
    )
    run_type = models.IntegerField(
        choices=[(_type.value, _type.name) for _type in AssetType],
        default=AssetType.PACKAGE.value,
    )
    run_start_time = models.DateTimeField(null=True, blank=True)
    run_end_time = models.DateTimeField(null=True, blank=True)
    # runtime in seconds
    run_duration = models.IntegerField(default=0)
    # error string
    error_string = models.TextField(default="")
    # interpret error
    interpret_error_string = models.TextField(default="")
    asset_batch = models.ForeignKey("AssetBatch", null=True)
    device = models.ForeignKey("backbone.device", null=True)
    # run index in current batch
    batch_index = models.IntegerField(default=0)

    raw_result_str = models.TextField(null=True)

    raw_result_interpreted = models.BooleanField(default=False)

    scan_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in ScanType], null=True)

    # link to packageversions
    packages = models.ManyToManyField(AssetPackageVersion)
    created = models.DateTimeField(auto_now_add=True)

    def start(self):
        self.run_status = RunStatus.RUNNING
        self.run_start_time = timezone.now()
        self.save()

    def stop(self, result, error_string=""):
        self.run_result = result
        self.run_status = RunStatus.ENDED
        self.error_string = error_string
        if self.run_start_time:
            self.run_end_time = timezone.now()
            self.run_duration = int((self.run_end_time - self.run_start_time).seconds)
        else:
            # no start time hence no end time
            self.run_duration = 0
        self.save()
        self.asset_batch.run_done(self)

    def generate_assets(self):
        if not self.raw_result_interpreted:
            get_base_assets_from_raw_result(self, self.raw_result_str, self.run_type, self.scan_type)
            self.raw_result_interpreted = True
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
    run_start_time = models.DateTimeField(null=True, blank=True)
    run_end_time = models.DateTimeField(null=True, blank=True)
    # total number of runs
    num_runs = models.IntegerField(default=0)
    # number of runs completed
    num_completed = models.IntegerField(default=0)
    # number of runs ok / error
    num_runs_ok = models.IntegerField(default=0)
    num_runs_error = models.IntegerField(default=0)
    # status
    run_status = models.IntegerField(
        choices=[(status.value, status.name) for status in RunStatus],
        default=RunStatus.PLANNED.value,
    )
    # result
    run_result = models.IntegerField(
        choices=[(status.value, status.name) for status in RunResult],
        default=RunResult.UNKNOWN.value,
    )
    # error string
    error_string = models.TextField(default="")
    # total run time in seconds
    run_time = models.IntegerField(default=0)
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)

    def completed(self):
        for assetrun in self.assetrun_set.all():
            if not assetrun.run_status == RunStatus.ENDED:
                return False
        return True

    def run_done(self, asset_run):
        self.num_completed += 1
        if asset_run.run_result == RunResult.SUCCESS:
            self.num_runs_ok += 1
        else:
            self.num_runs_error += 1
        if self.num_completed == self.num_runs:
            # finished
            self.run_end_time = timezone.now()
            self.run_time = int((self.run_end_time - self.run_start_time).seconds)
            self.run_status = RunStatus.ENDED
            self.run_result = max([_res.run_result for _res in self.assetrun_set.all()])
        self.save()

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "AssetBatch for device '{}'".format(
            unicode(self.device)
        )


class DeviceInventory(models.Model):
    # to be removed
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


class StaticAssetTemplateFieldType(IntEnum):
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
    # description
    description = models.TextField(default="")
    # system template (not deleteable)
    system_template = models.BooleanField(default=False)
    # parent template (for copy operations)
    parent_template = models.ForeignKey("backbone.StaticAssetTemplate", null=True)
    # link to creation user
    user = models.ForeignKey("backbone.user", null=True)
    # created
    date = models.DateTimeField(auto_now_add=True)

    def copy(self, new_obj, create_user):
        nt = StaticAssetTemplate(
            type=self.type,
            name=new_obj["name"],
            description=new_obj["description"],
            system_template=False,
            parent_template=self,
            user=create_user,
        )
        nt.save()
        return nt


class StaticAssetTemplateField(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    # name
    name = models.CharField(max_length=64, default="")
    # description
    field_description = models.TextField(default="")
    field_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in StaticAssetTemplateFieldType])
    # is optional
    optional = models.BooleanField(default=True)
    # is consumable (for integer fields)
    consumable = models.BooleanField(default=False)
    # default value
    default_value_str = models.CharField(default="", blank=True, max_length=255)
    default_value_int = models.IntegerField(default=0)
    default_value_date = models.DateField(default=timezone.now)
    # bounds, for input checking
    has_bounds = models.BooleanField(default=False)
    value_int_lower_bound = models.IntegerField(default=0)
    value_int_upper_bound = models.IntegerField(default=0)
    # monitor flag, only for datefiles
    monitor = models.BooleanField(default=False)
    # created
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ("static_asset_template", "name")
        ]


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
