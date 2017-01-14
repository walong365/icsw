#
# Copyright (C) 2016-2017 Gregor Kaufmann, Andreas Lang-Nevyjel init.at
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
""" asset database, functions and constants """



import base64
import bz2
import datetime
import json
import logging

from enum import IntEnum
from lxml import etree

from initat.tools import server_command

logger = logging.getLogger(__name__)

__all__ = [
    "BaseAssetPackage",
    "sizeof_fmt",
    "get_packages_for_ar",
    "ASSET_DATETIMEFORMAT",
    "AssetType",
    "ScanType",
    "RunStatus",
    "BatchStatus",
    "RunResult",
    "PackageTypeEnum",
]

########################################################################################################################
# Functions
########################################################################################################################


class BaseAssetPackage(object):
    def __init__(self, name, version=None, release=None, size=None, install_date=None, package_type=None):
        self.name = name
        self.version = version
        self.release = release
        self.size = size
        self.install_date = install_date
        self.package_type = package_type

    def get_install_time_as_datetime(self):
        if self.package_type == PackageTypeEnum.LINUX:
            try:
                return datetime.datetime.fromtimestamp(int(self.install_date))
            except:
                pass
        else:
            try:
                year = self.install_date[0:4]
                month = self.install_date[4:6]
                day = self.install_date[6:8]

                return datetime.datetime(year=int(year), month=int(month), day=int(day), hour=12)
            except:
                pass

        return None

    def get_as_row(self):
        _name = self.name
        _version = self.version if self.version else "N/A"
        _release = self.release if self.release else "N/A"

        if self.package_type == PackageTypeEnum.LINUX:
            if self.size:
                try:
                    _size = sizeof_fmt(self.size)
                except:
                    _size = "N/A"
            else:
                _size = "N/A"

            if self.install_date:
                try:
                    _install_date = datetime.datetime.fromtimestamp(int(self.install_date)).\
                        strftime(ASSET_DATETIMEFORMAT)
                except:
                    _install_date = "N/A"
            else:
                _install_date = "N/A"
        else:
            if self.size:
                try:
                    _size = sizeof_fmt(int(self.size) * 1024)
                except:
                    _size = "N/A"
            else:
                _size = "N/A"

            _install_date = self.install_date if self.install_date else "N/A"
            if _install_date == "Unknown":
                _install_date = "N/A"

            if _install_date != "N/A":
                try:
                    year = _install_date[0:4]
                    month = _install_date[4:6]
                    day = _install_date[6:8]

                    _install_date = datetime.datetime(year=int(year), month=int(month), day=int(day)).\
                        strftime(ASSET_DATETIMEFORMAT)
                except:
                    _install_date = "N/A"

        o = {}
        o['package_name'] = _name
        o['package_version'] = _version
        o['package_release'] = _release
        o['package_size'] = _size
        o['package_install_date'] = _install_date
        return o

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


def sizeof_fmt(num, suffix='B'):
    if num is None:
        return "N/A"
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def get_packages_for_ar(asset_run):
    blob = asset_run.raw_result_str
    runtype = asset_run.run_type
    scantype = asset_run.scan_type

    assets = []

    if blob:
        if runtype == AssetType.PACKAGE:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))
                l = json.loads(_data)
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
                tree = etree.fromstring(blob)
                blob = tree.xpath('ns0:pkg_list', namespaces=tree.nsmap)[0].text
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

                            assets.append(
                                BaseAssetPackage(
                                    package_name,
                                    version=versions_dict['version'],
                                    size=versions_dict['size'],
                                    release=versions_dict['release'],
                                    install_date=installtimestamp,
                                    package_type=PackageTypeEnum.LINUX
                                )
                            )

    return assets

ASSET_DATETIMEFORMAT = "%a %d. %b %Y %H:%M:%S"


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2  # lstopo
    LICENSE = 3
    UPDATE = 4
    LSHW = 5
    PROCESS = 6
    PENDING_UPDATE = 7
    DMI = 8
    PCI = 9
    PRETTYWINHW = 10
    PARTITION = 11
    LSBLK = 12
    XRANDR = 13


class ScanType(IntEnum):
    HM = 1
    NRPE = 2


class RunStatus(IntEnum):
    PLANNED = 1
    SCANNING = 2
    FINISHED_SCANNING = 3
    GENERATING_ASSETS = 4
    FINISHED = 5


class BatchStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    FINISHED_RUNS = 3
    GENERATING_ASSETS = 4
    FINISHED = 5


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
