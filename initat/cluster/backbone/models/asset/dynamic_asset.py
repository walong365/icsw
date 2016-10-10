#
# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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
""" asset database, models for dynamic assets """

import base64
import bz2
import datetime
import json
import logging
import time

from django.db import models
from django.db.models import Q
from django.utils import timezone, dateparse
from lxml import etree

from initat.cluster.backbone.models.functions import get_related_models
from initat.cluster.backbone.models.partition import partition_disc, \
    partition_table, partition, partition_fs, LogicalDisc, lvm_vg, \
    sys_partition, lvm_lv
from initat.cluster.backbone.tools.hw import Hardware
from initat.snmp.snmp_struct import ResultNode
from initat.tools import server_command, pci_database, dmi_tools, \
    partition_tools, logging_tools
from initat.tools.server_command import srv_command
from initat.cluster.backbone.models.asset.asset_functions import \
    PackageTypeEnum, ScanType, BaseAssetPackage, BatchStatus, RunStatus, \
    RunResult, AssetType, sizeof_fmt

logger = logging.getLogger(__name__)


__all__ = [
    "AssetHWMemoryEntry",
    "AssetHWCPUEntry",
    "AssetHWGPUEntry",
    "AssetHWLogicalEntry",
    "AssetHWDisplayEntry",
    "AssetHWNetworkDevice",
    "AssetPackageVersionInstallTime",
    "AssetPackage",
    "AssetPackageVersion",
    "AssetHardwareEntry",
    "AssetLicenseEntry",
    "AssetUpdateEntry",
    "AssetProcessEntry",
    "AssetPCIEntry",
    "AssetDMIHead",
    "AssetDMIHandle",
    "AssetDMIValue",
    "AssetRun",
    "AssetBatch",
    "DeviceInventory",
]


class AssetHWMemoryEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    # i.e slot 0 / slot A
    banklabel = models.TextField(null=True)
    # dimm type
    formfactor = models.TextField(null=True)
    # i.e ddr/ddr2 if known
    memorytype = models.TextField(null=True)
    manufacturer = models.TextField(null=True)
    capacity = models.BigIntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "BankLabel:{} FormFactor:{} Memorytype:{} Manufacturer:{} Capacity:{}".format(
            self.banklabel,
            self.formfactor,
            self.memorytype,
            self.manufacturer,
            sizeof_fmt(self.capacity)
        )

    def get_name_of_form_factor(self):
        return self.formfactor

    def get_name_of_memory_type(self):
        return self.memorytype


class AssetHWCPUEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField(null=True)
    numberofcores = models.IntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} [Cores:{}]".format(self.name, self.numberofcores)


class AssetHWGPUEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{}".format(self.name)


class AssetHWLogicalEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField(null=True)
    size = models.BigIntegerField(null=True)
    free = models.BigIntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} [Size:{} Free:{}]".format(self.name, sizeof_fmt(self.size), sizeof_fmt(self.free))


class AssetHWDisplayEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField(null=True)
    type = models.TextField(null=True)
    xpixels = models.IntegerField(null=True)
    ypixels = models.IntegerField(null=True)
    manufacturer = models.TextField(null=True)

    def __unicode__(self):
        return "{} [Type:{} xpixels:{} ypixels:{} manufacturer:{}]".format(
            self.name,
            self.type,
            self.xpixels,
            self.ypixels,
            self.manufacturer
        )


class AssetHWNetworkDevice(models.Model):
    idx = models.AutoField(primary_key=True)
    manufacturer = models.TextField(null=True)
    product_name = models.TextField(null=True)
    device_name = models.TextField(null=True)
    speed = models.IntegerField(null=True)
    mac_address = models.TextField(null=True)

    def __unicode__(self):
        return "AssetHWNetworkDevice[Manufacturer:{}|Product Name:{}|"\
            "Device Name:{}|Speed:{}]".format(
                self.manufacturer,
                self.product_name,
                self.device_name,
                self.speed,
            )


class AssetPackageVersionInstallTime(models.Model):
    idx = models.AutoField(primary_key=True)
    package_version = models.ForeignKey("backbone.AssetPackageVersion")
    timestamp = models.BigIntegerField()

    @property
    def install_time(self):
        return datetime.datetime.fromtimestamp(float(self.timestamp))


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

    @property
    def install_info(self):
        _dict = {}
        for assetbatch in self.assetbatch_set.all():
            if assetbatch.device.idx not in _dict:
                _dict[assetbatch.device.idx] = {}
                _dict[assetbatch.device.idx]["device_name"] = assetbatch.device.full_name
                _dict[assetbatch.device.idx]["install_history_list"] = []

            _dict[assetbatch.device.idx]["install_history_list"].append(assetbatch.run_start_time)

        return _dict

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
    # optional
    optional = models.BooleanField(default=True)
    # installed
    installed = models.BooleanField(default=False)
    # new version (for RPMs)
    new_version = models.CharField(default="", max_length=64)

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


class AssetPCIEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # Domain / Bus / Slot / Func
    domain = models.IntegerField(default=0)
    bus = models.IntegerField(default=0)
    slot = models.IntegerField(default=0)
    func = models.IntegerField(default=0)
    # ids
    pci_class = models.IntegerField(default=0)
    subclass = models.IntegerField(default=0)
    device = models.IntegerField(default=0)
    vendor = models.IntegerField(default=0)
    revision = models.IntegerField(default=0)
    # Name(s)
    pci_classname = models.CharField(default="", max_length=255)
    subclassname = models.CharField(default="", max_length=255)
    devicename = models.CharField(default="", max_length=255)
    vendorname = models.CharField(default="", max_length=255)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetPCIEntry {:04x}:{:02x}:{:02x}.{:x} {}".format(
            self.domain,
            self.bus,
            self.slot,
            self.func,
            self.devicename,
        )

    class Meta:
        ordering = ("domain", "bus", "slot", "func",)


class AssetDMIHead(models.Model):
    idx = models.AutoField(primary_key=True)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    version = models.CharField(default="", max_length=63)
    size = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetDMIHead"


class AssetDMIHandle(models.Model):
    idx = models.AutoField(primary_key=True)
    # dmi_head
    dmihead = models.ForeignKey("backbone.AssetDMIHead")
    # handle id
    handle = models.IntegerField(default=0)
    # type
    dmi_type = models.IntegerField(default=0)
    # header string
    header = models.CharField(default="", max_length=128)
    # length
    length = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetDMIHandle {:d}: {}".format(
            self.handle,
            self.header,
        )


class AssetDMIValue(models.Model):
    idx = models.AutoField(primary_key=True)
    # dmi_handle
    dmihandle = models.ForeignKey("backbone.AssetDMIHandle")
    # key
    key = models.CharField(default="", max_length=128)
    # is single valued
    single_value = models.BooleanField(default=True)
    # number of values, 1 or more
    num_values = models.IntegerField(default=1)
    # value for single_valued else json encoded
    value = models.TextField(default="")
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetDMIValue {}".format(
            self.key,
        )


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
    # runtime in seconds (for communication)
    run_duration = models.IntegerField(default=0)
    # time needed to generate assets in db
    generate_duration = models.FloatField(default=0.0)
    # error string
    error_string = models.TextField(default="")
    # interpret error
    interpret_error_string = models.TextField(default="")
    asset_batch = models.ForeignKey("AssetBatch", null=True)
    # run index in current batch
    batch_index = models.IntegerField(default=0)
    raw_result_str = models.TextField(null=True)
    raw_result_interpreted = models.BooleanField(default=False)
    scan_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in ScanType], null=True)

    created = models.DateTimeField(auto_now_add=True)

    def is_finished_processing(self):
        if self.interpret_error_string or self.generate_duration:
            return True
        return False

    # XXX remove this
    @property
    def hdds(self):
        if self.asset_batch and self.asset_batch.partition_table:
            return self.asset_batch.partition_table.partition_disc_set.all()
        return []

    @property
    def cpus(self):
        return self.asset_batch.cpus.all()

    @property
    def gpus(self):
        return self.asset_batch.gpus.all()

    @property
    def displays(self):
        return self.asset_batch.displays.all()

    @property
    def memory_modules(self):
        return self.asset_batch.memory_modules.all()

    @property
    def cpu_count(self):
        return len(self.asset_batch.cpus.all())

    @property
    def memory_count(self):
        return len(self.asset_batch.memory_modules.all())

    @property
    def packages(self):
        return [package.idx for package in self.asset_batch.packages.all()]

    @property
    def packages_install_times(self):
        return self.asset_batch.packages_install_times.all()

    @property
    def device(self):
        return self.asset_batch.device.idx

    def state_start_scan(self):
        self._change_state(RunStatus.SCANNING)
        self.run_start_time = timezone.now()
        self.save()

    def state_finished_scan(self, result, error_string, raw_result_str):
        self._change_state(RunStatus.FINISHED_SCANNING)
        self.run_result = result
        self.error_string = error_string
        self.raw_result_str = raw_result_str
        if self.run_start_time:
            self.run_end_time = timezone.now()
            self.run_duration = int(
                (self.run_end_time - self.run_start_time).seconds
            )
        self.save()

    def state_start_generation(self):
        self._change_state(RunStatus.GENERATING_ASSETS)
        self.save()

    def state_finished(self, result, error_string=""):
        self._change_state(RunStatus.FINISHED)
        self.run_result = result
        self.error_string = error_string
        self.save()
        self.asset_batch.run_done()

    def _change_state(self, new_state):
        logger.debug(
            'Asset run {} state: {} -> {}'.format(
                str(self.idx),
                str(RunStatus(self.run_status)),
                str(new_state),
            )
        )
        self.run_status = new_state
        self.save()

    def has_data(self):
        return RunResult(self.run_result) == RunResult.SUCCESS

    @property
    def raw_result(self):
        raw = self.raw_result_str
        if self.scan_type == ScanType.NRPE:
            if raw.startswith("b'"):
                raw = raw[2:-2]
            result = bz2.decompress(base64.b64decode(raw))
        elif self.scan_type == ScanType.HM:
            # parse XML
            result = etree.fromstring(raw)
        else:
            raise NotImplemented
        return result

    def generate_assets(self):
        function_name = '_generate_assets_{}_{}'.format(
            AssetType(self.run_type)._name_.lower(),
            ScanType(self.scan_type)._name_.lower()
        )
        if not self.raw_result_interpreted:
            # call the appropriate _generate_assets_... method
            if hasattr(self, function_name):
                getattr(self, function_name)(self.raw_result)
                self.save()

    def _generate_assets_package_nrpe(self, data):
        assets = []
        if self.scan_type == ScanType.NRPE:
            l = json.loads(data)
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
        self._generate_assets_package(assets)

    def _generate_assets_package_hm(self, tree):
        blob = tree.xpath('ns0:pkg_list', namespaces=tree.nsmap)[0].text
        assets = []
        try:
            package_dict = server_command.decompress(blob, pickle=True)
        except:
            raise
        else:
            for package_name in package_dict:
                for versions_dict in package_dict[package_name]:
                    installtimestamp = None
                    if 'installtimestamp' in versions_dict:
                        installtimestamp = versions_dict['installtimestamp']

                    size = 0
                    if 'size' in versions_dict:
                        size = versions_dict['size']

                    assets.append(
                        BaseAssetPackage(
                            package_name,
                            version=versions_dict['version'],
                            size=size,
                            release=versions_dict['release'],
                            install_date=installtimestamp,
                            package_type=PackageTypeEnum.LINUX
                        )
                    )
        self._generate_assets_package(assets)

    def _generate_assets_package(self, assets):
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
            self.asset_batch.packages.add(apv)

            install_time = ba.get_install_time_as_datetime()

            if install_time:
                timestamp = time.mktime(install_time.timetuple())

                apv_install_times = AssetPackageVersionInstallTime.objects.filter(
                    package_version=apv,
                    timestamp=timestamp
                )

                if not apv_install_times:
                    apv_install_time = AssetPackageVersionInstallTime(
                        package_version=apv,
                        timestamp=timestamp
                    )

                    apv_install_time.save()
                else:
                    apv_install_time = apv_install_times[0]

                self.asset_batch.packages_install_times.add(apv_install_time)

    def _generate_assets_hardware_nrpe(self, data):
        self._generate_assets_hardware(etree.fromstring(data))

    def _generate_assets_hardware_hm(self, tree):
        blob = tree.xpath('ns0:lstopo_dump', namespaces=tree.nsmap)[0].text
        xml_str = bz2.decompress(base64.b64decode(blob))
        root = etree.fromstring(xml_str)
        self._generate_assets_hardware(root)

    def _generate_assets_hardware(self, root):
        # lookup for structural entries
        _struct_lut = {}
        _root_tree = root.getroottree()
        for element in root.iter():
            if element.tag in ["topology", "object"]:
                # structural entry
                struct_el = AssetHardwareEntry(
                    type=element.tag,
                    attributes=json.dumps({key: value for key, value in element.attrib.iteritems()}),
                    asset_run=self,
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

    def _generate_assets_license_nrpe(self, data):
        l = json.loads(data)
        for (name, licensekey) in l:
            new_lic = AssetLicenseEntry(
                name=name,
                license_key=licensekey,
                asset_run=self,
            )
            new_lic.save()

    def _generate_assets_pending_update_nrpe(self, data):
        l = json.loads(data)
        for (name, optional) in l:
            asset_update_entry = AssetUpdateEntry.objects.filter(
                name=name,
                version="",
                release="",
                kb_idx=0,
                install_date=None,
                status="",
                optional=optional,
                installed=False,
                new_version=""
                )
            if asset_update_entry:
                asset_update_entry = asset_update_entry[0]
            else:
                asset_update_entry = AssetUpdateEntry(
                    name=name,
                    installed=False,
                    optional=optional,
                )
                asset_update_entry.save()

            self.asset_batch.pending_updates.add(asset_update_entry)

    def _generate_assets_pending_update_hm(self, tree):
        blob = tree.xpath('ns0:update_list', namespaces=tree.nsmap)[0]\
            .text
        l = server_command.decompress(blob, pickle=True)
        for (name, version) in l:
            asset_update_entry = AssetUpdateEntry.objects.filter(
                name=name,
                version="",
                release="",
                kb_idx=0,
                install_date=None,
                status="",
                optional=True,
                installed=False,
                new_version=version
                )
            if asset_update_entry:
                asset_update_entry = asset_update_entry[0]
            else:
                asset_update_entry = AssetUpdateEntry(
                    name=name,
                    # by definition linux updates are optional
                    optional=True,
                    installed=False,
                    new_version=version,
                )
                asset_update_entry.save()

            self.asset_batch.pending_updates.add(asset_update_entry)

    def _generate_assets_update_nrpe(self, data):
        l = json.loads(data)
        for (name, up_date, status) in l:
            asset_update_entry = AssetUpdateEntry.objects.filter(
                name=name,
                version="",
                release="",
                kb_idx=0,
                install_date=dateparse.parse_datetime(up_date),
                status=status,
                optional=False,
                installed=True,
                new_version=""
                )
            if asset_update_entry:
                asset_update_entry = asset_update_entry[0]
            else:
                asset_update_entry = AssetUpdateEntry(
                    name=name,
                    install_date=dateparse.parse_datetime(up_date),
                    status=status,
                    optional=False,
                    installed=True
                )
                asset_update_entry.save()

            self.asset_batch.installed_updates.add(asset_update_entry)

    def _generate_assets_process_nrpe(self, data):
        l = json.loads(data)
        process_dict = {int(pid): {"name": name} for name, pid in l}
        self._generate_assets_process(process_dict)

    def _generate_assets_process_hm(self, tree):
        blob = tree.xpath('ns0:process_tree', namespaces=tree.nsmap)[0]\
            .text
        # TODO: Remove eval().
        process_dict = eval(bz2.decompress(base64.b64decode(blob)))
        self._generate_assets_process(process_dict)

    def _generate_assets_process(self, process_dict):
        for pid, stuff in process_dict.iteritems():
            new_proc = AssetProcessEntry(
                pid=pid,
                name=stuff["name"],
                asset_run=self,
            )
            new_proc.save()

    def _generate_assets_pci_nrpe(self, data):
        info_dicts = []
        info_dict = {}
        for line in data.decode().split("\r\n"):
            if len(line) == 0:
                if len(info_dict) > 0:
                    info_dicts.append(info_dict)
                    info_dict = {}
            if line.startswith("Slot:"):
                info_dict['slot'] = line.split("\t", 1)[1]

                comps = info_dict['slot'].split(":")
                bus = comps[0]

                comps = comps[1].split(".")
                slot = comps[0]
                func = comps[1]

                info_dict['bus'] = bus
                info_dict['slot'] = slot
                info_dict['func'] = func
            elif line.startswith("Class:"):
                info_dict['class'] = line.split("\t", 1)[1]
            elif line.startswith("Vendor:"):
                info_dict['vendor'] = line.split("\t", 1)[1]
            elif line.startswith("Device:"):
                info_dict['device'] = line.split("\t", 1)[1]
            elif line.startswith("SVendor:"):
                info_dict['svendor'] = line.split("\t", 1)[1]
            elif line.startswith("SDevice:"):
                info_dict['sdevice'] = line.split("\t", 1)[1]
            elif line.startswith("Rev:"):
                info_dict['rev'] = line.split("\t", 1)[1]

        for info_dict in info_dicts:
            new_pci = AssetPCIEntry(
                asset_run=self,
                domain=0,
                bus=int(info_dict['bus'], 16) if 'bus' in info_dict else 0,
                slot=int(info_dict['slot'], 16) if 'slot' in info_dict else 0,
                func=int(info_dict['func'], 16) if 'func' in info_dict else 0,
                pci_class=0,
                subclass=0,
                device=0,
                vendor=0,
                revision=int(info_dict['rev'], 16) if 'rev' in info_dict else 0,
                pci_classname=info_dict['class'],
                subclassname=info_dict['class'],
                devicename=info_dict['device'],
                vendorname=info_dict['vendor'],
            )
            new_pci.save()

    def _generate_assets_pci_hm(self, tree):
        blob = tree.xpath('ns0:pci_dump', namespaces=tree.nsmap)[0].text
        s = pci_database.pci_struct_to_xml(
            pci_database.decompress_pci_info(blob)
        )
        for func in s.findall(".//func"):
            _slot = func.getparent()
            _bus = _slot.getparent()
            _domain = _bus.getparent()
            new_pci = AssetPCIEntry(
                asset_run=self,
                domain=int(_domain.get("id")),
                bus=int(_domain.get("id")),
                slot=int(_slot.get("id")),
                func=int(func.get("id")),
                pci_class=int(func.get("class"), 16),
                subclass=int(func.get("subclass"), 16),
                device=int(func.get("device"), 16),
                vendor=int(func.get("vendor"), 16),
                revision=int(func.get("revision"), 16),
                pci_classname=func.get("classname"),
                subclassname=func.get("subclassname"),
                devicename=func.get("devicename"),
                vendorname=func.get("vendorname"),
            )
            new_pci.save()

    def _generate_assets_dmi_nrpe(self, blob):
        _lines = []
        for line in blob.decode().split("\r\n"):
            _lines.append(line)
            if line == "End Of Table":
                break
        xml = dmi_tools.dmi_struct_to_xml(dmi_tools.parse_dmi_output(_lines))
        self._generate_assets_dmi(xml)

    def _generate_assets_dmi_hm(self, tree):
        blob = tree.xpath('ns0:dmi_dump', namespaces=tree.nsmap)[0].text
        xml = dmi_tools.decompress_dmi_info(blob)
        self._generate_assets_dmi(xml)

    def _generate_assets_dmi(self, xml):
        head = AssetDMIHead(
            asset_run=self,
            version=xml.get("version"),
            size=int(xml.get("size")),
        )
        head.save()
        for _handle in xml.findall(".//handle"):
            handle = AssetDMIHandle(
                dmihead=head,
                handle=int(_handle.get("handle")),
                dmi_type=int(_handle.get("dmi_type")),
                length=int(_handle.get("length")),
                header=_handle.get("header"),
            )
            handle.save()
            for _value in _handle.findall(".//value"):
                if len(_value):
                    value = AssetDMIValue(
                        dmihandle=handle,
                        key=_value.get("key"),
                        single_value=False,
                        value=json.dumps([_el.text for _el in _value]),
                        num_values=len(_value),
                    )
                else:
                    value = AssetDMIValue(
                        dmihandle=handle,
                        key=_value.get("key"),
                        single_value=True,
                        value=_value.text or "",
                        num_values=1,
                    )
                value.save()


class AssetBatch(models.Model):
    idx = models.AutoField(primary_key=True)
    run_start_time = models.DateTimeField(null=True, blank=True)
    run_end_time = models.DateTimeField(null=True, blank=True)
    # status
    run_status = models.IntegerField(
        choices=[(status.value, status.name) for status in BatchStatus],
        default=BatchStatus.PLANNED.value,
    )
    # error string
    error_string = models.TextField(default="")

    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)
    # fields generated from raw entries
    packages = models.ManyToManyField(AssetPackageVersion)
    packages_install_times = models.ManyToManyField(AssetPackageVersionInstallTime)
    cpus = models.ManyToManyField(AssetHWCPUEntry)
    memory_modules = models.ManyToManyField(AssetHWMemoryEntry)
    gpus = models.ManyToManyField(AssetHWGPUEntry)
    displays = models.ManyToManyField(AssetHWDisplayEntry)
    partition_table = models.ForeignKey(
        "backbone.partition_table",
        on_delete=models.SET_NULL,
        null=True,
    )
    network_devices = models.ManyToManyField(AssetHWNetworkDevice)
    pending_updates = models.ManyToManyField(AssetUpdateEntry, related_name="assetbatch_pending_updates")
    installed_updates = models.ManyToManyField(AssetUpdateEntry, related_name="assetbatch_installed_updates")

    @property
    def partition_table_length(self):
        if self.partition_table:
            return 1
        return 0

    @property
    def packages_length(self):
        return self.packages.count()

    @property
    def packages_install_times_length(self):
        return self.packages_install_times.count()

    @property
    def cpus_length(self):
        return self.cpus.count()

    @property
    def memory_modules_length(self):
        return self.memory_modules.count()

    @property
    def gpus_length(self):
        return self.gpus.count()

    @property
    def network_devices_length(self):
        return self.network_devices.count()

    @property
    def displays_length(self):
        return self.displays.count()

    @property
    def pending_updates_length(self):
        return self.pending_updates.count()

    @property
    def installed_updates_length(self):
        return self.installed_updates.count()

    @property
    def is_finished_processing(self):
        if self.run_status == BatchStatus.FINISHED:
            return True
        return False

    @property
    def run_time(self):
        if self.run_start_time and self.run_end_time:
            return (self.run_end_time - self.run_start_time).seconds

        return None

    def state_init(self):
        self.run_start_time = timezone.now()
        self._change_state(BatchStatus.PLANNED)

    def state_start_runs(self):
        self._change_state(BatchStatus.RUNNING)

    def state_finished_runs(self):
        self._change_state(BatchStatus.FINISHED_RUNS)

    def state_start_generation(self):
        self._change_state(BatchStatus.GENERATING_ASSETS)

    def state_finished(self):
        self.run_end_time = timezone.now()
        self._change_state(BatchStatus.FINISHED)

    def _change_state(self, new_state):
        logger.debug(
            'Asset batch {} state: {} -> {}'.format(
                str(self.idx),
                str(BatchStatus(self.run_status)),
                str(new_state),
            )
        )
        self.run_status = new_state
        self.save()

    def run_done(self):
        if self.run_status < BatchStatus.GENERATING_ASSETS:
            if all(r.run_status == RunStatus.FINISHED
                   for r in self.assetrun_set.all()):
                self.state_finished_runs()
                if all(r.run_result == RunResult.SUCCESS
                       for r in self.assetrun_set.all()):
                    self.run_result = RunResult.SUCCESS
                self.save()

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "AssetBatch for device '{}'".format(
            unicode(self.device)
        )

    def generate_assets(self):
        """Set the batch level hardware information (.cpus, .memory_modules
        etc.) from the acquired asset runs."""
        runs = {
            AssetType.PRETTYWINHW: "win32_tree",
            AssetType.LSHW: "lshw_dump",
            AssetType.DMI: "dmi_head",
            AssetType.LSBLK: "lsblk_dump",
            AssetType.PARTITION: "partinfo_tree",
            AssetType.XRANDR: "xrandr_dump",
            }

        # search for relevant asset runs and Base64 decode and unzip the result
        run_results = {}
        for run in self.assetrun_set.all():
            if run.run_type not in runs:
                continue

            arg_name = runs[run.run_type]

            if (run.run_status == RunStatus.FINISHED and
                    run.run_result == RunResult.SUCCESS):
                if run.run_type == AssetType.DMI:
                    arg_value = run.assetdmihead_set.get()
                else:
                    if run.scan_type == ScanType.NRPE:
                        blob = run.raw_result
                        arg_value = json.loads(blob)
                    elif run.scan_type == ScanType.HM:
                        tree = run.raw_result
                        if run.run_type == AssetType.PARTITION:
                            arg_value = tree
                        else:
                            blob = tree.xpath(
                                'ns0:{}'.format(arg_name),
                                namespaces=tree.nsmap
                            )[0].text
                            blob = bz2.decompress(base64.b64decode(blob))
                            if run.run_type == AssetType.LSHW:
                                arg_value = etree.fromstring(blob)
                            else:
                                arg_value = blob

                run_results[arg_name] = arg_value

        hw = Hardware(**run_results)

        # set the CPUs
        self.cpus.all().delete()
        for cpu in hw.cpus:
            new_cpu = AssetHWCPUEntry(
                name=cpu.product,
                numberofcores=cpu.number_of_cores
            )
            new_cpu.save()
            self.cpus.add(new_cpu)

        # set the memory modules
        self.memory_modules.all().delete()
        for memory_module in hw.memory_modules:
            new_memory_module = AssetHWMemoryEntry(
                banklabel=memory_module.bank_label,
                formfactor=memory_module.form_factor,
                memorytype=memory_module.type,
                manufacturer=memory_module.manufacturer,
                capacity=memory_module.capacity,
            )
            new_memory_module.save()
            self.memory_modules.add(new_memory_module)

        # set the GPUs and displays
        self.gpus.all().delete()
        for gpus in hw.gpus:
            new_gpu = AssetHWGPUEntry(name=gpus.product)
            new_gpu.save()
            self.gpus.add(new_gpu)
        for display in hw.displays:
            new_display = AssetHWDisplayEntry(
                name=display.product,
                xpixels=display.x_resolution,
                ypixels=display.y_resolution,
                manufacturer=display.manufacturer,
            )
            new_display.save()
            self.displays.add(new_display)

        # set the discs and partitions
        fs_dict = {fs.name: fs for fs in partition_fs.objects.all()}
        name = "_".join([self.device.name, "part", str(self.idx)])
        partition_table_ = partition_table(
            name=name,
            description='partition information generated during asset run',
        )
        partition_table_.save()
        for hdd in hw.hdds:
            disc = partition_disc(
                partition_table=partition_table_,
                disc=hdd.device_name,
                size=hdd.size,
                serial=hdd.serial if hdd.serial else '',
            )
            disc.save()

            for hdd_partition in hdd.partitions:
                logical = hdd_partition.logical
                partition_ = partition(
                    partition_disc=disc,
                    pnum=hdd_partition.index,
                    size=hdd_partition.size,
                    mountpoint='',
                )
                partition_fs_ = fs_dict.get(
                    hdd_partition.type,
                    fs_dict["unknown"]
                )
                partition_.partition_fs = partition_fs_
                if logical:
                    partition_.mountpoint = logical.mount_point
                partition_.save()

        for logical in hw.logical_disks:
            partition_fs_ = fs_dict.get(
                logical.file_system,
                fs_dict["unknown"]
            )
            logical_db = LogicalDisc(
                partition_table=partition_table_,
                device_name=logical.device_name,
                partition_fs=partition_fs_,
                size=logical.size,
                free_space=logical.free_space,
            )
            logical_db.save()
            logical_db.partitions.add(partition_)

        self.partition_table = partition_table_
        # set the partition info on the device
        self.device.act_partition_table = partition_table_
        self.device.save()

        # set the network devices
        self.network_devices.all().delete()
        for network_device in hw.network_devices:
            new_network_device = AssetHWNetworkDevice(
                manufacturer=network_device.manufacturer,
                product_name=network_device.product,
                device_name=network_device.device_name,
                speed=network_device.speed,
                mac_address=network_device.mac_address
                )
            new_network_device.save()
            self.network_devices.add(new_network_device)

        self.save()
        # TODO: Set displays.


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
