# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the collectd-init package
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
#
""" resize part of collectd-init """

import time
import subprocess

import psutil
from initat.collectd.config import global_config
from initat.tools import logging_tools
from initat.tools import process_tools


class RSyncMixin(object):
    def _setup_rsync(self):
        _is_ram = False
        for _fs in psutil.disk_partitions(all=True):
            if _fs.mountpoint == global_config["RRD_DIR"] and _fs.fstype in ["tmpfs", "ramdisk"]:
                _is_ram = True
                break
        self._rsync_bin = process_tools.find_file("rsync")
        self.log(
            "{} is{} a RAM-disk, rsync binary is at {} ...".format(
                global_config["RRD_DIR"],
                "" if _is_ram else " not",
                self._rsync_bin,
            )
        )
        if _is_ram and self._rsync_bin and global_config["RRD_DISK_CACHE"] != global_config["RRD_DIR"]:
            self.do_rsync = True
            self.log("rsync for RRDs is enabled")
        else:
            self.do_rsync = False
            self.log("rsync for RRDs is disabled")

    def sync_from_disk_to_ram(self):
        if not hasattr(self, "do_rsync"):
            self._setup_rsync()
        if self.do_rsync:
            s_time = time.time()
            _cmd = "{} -a --delete {}/* {}".format(
                self._rsync_bin,
                global_config["RRD_DISK_CACHE"],
                global_config["RRD_DIR"],
            )
            subprocess.call(
                _cmd,
                shell=True
            )
            e_time = time.time()
            self.log("command {} took {}".format(_cmd, logging_tools.get_diff_time_str(e_time - s_time)))

    def sync_from_ram_to_disk(self):
        if not hasattr(self, "do_rsync"):
            self._setup_rsync()
        if self.do_rsync:
            s_time = time.time()
            _cmd = "{} -a {}/* {}".format(
                self._rsync_bin,
                global_config["RRD_DIR"],
                global_config["RRD_DISK_CACHE"],
            )
            subprocess.call(
                _cmd,
                shell=True
            )
            e_time = time.time()
            self.log("command {} took {}".format(_cmd, logging_tools.get_diff_time_str(e_time - s_time)))
