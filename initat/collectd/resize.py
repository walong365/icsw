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

import os
import stat
import time
import subprocess
import psutil

from django.db import connection
from initat.collectd.config import global_config
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import rrd_tools
from initat.tools import server_mixins
from initat.tools import threading_tools

try:
    import rrdtool  # @UnresolvedImport
except:
    rrdtool = None

# constant, change to limit RRDs to be converted at once
MAX_FOUND = 0


class resize_process(threading_tools.process_obj, server_mixins.OperationalErrorMixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self.rrd_cache_socket = global_config["RRD_CACHED_SOCKET"]
        self.rrd_root = global_config["RRD_DIR"]
        cov_keys = [_key for _key in global_config.keys() if _key.startswith("RRD_COVERAGE")]
        self.rrd_coverage = [global_config[_key] for _key in cov_keys]
        self.log("RRD coverage: {}".format(", ".join(self.rrd_coverage)))
        self.register_timer(self.check_size, 6 * 3600, first_timeout=1)
        self.__verbose = global_config["VERBOSE"]
        self.is_ram = False
        for _fs in psutil.disk_partitions(all=True):
            if _fs.mountpoint == global_config["RRD_DIR"] and _fs.fstype in ["tmpfs", "ramdisk"]:
                self.is_ram = True
                break
        self.rsync_bin = process_tools.find_file("rsync")
        self.log(
            "{} is{} a RAM-disk, _rsync binary is at {} ...".format(
                global_config["RRD_DIR"],
                "" if self.is_ram else " not",
                self.rsync_bin,
            )
        )
        self.do_sync = self.is_ram and self.rsync_bin and global_config["RRD_DISK_CACHE"] != global_config["RRD_DIR"]
        if self.do_sync:
            self.log(
                "enabling periodic RAM-to-disk sync from {} to {} every {}".format(
                    global_config["RRD_DIR"],
                    global_config["RRD_DISK_CACHE"],
                    logging_tools.get_diff_time_str(global_config["RRD_DISK_CACHE_SYNC"]),
                )
            )
            self.register_timer(self.sync_ram_to_disk, global_config["RRD_DISK_CACHE_SYNC"])

    def sync_ram_to_disk(self):
        s_time = time.time()
        _cmd = "{} -a {}/* {}".format(
            self.rsync_bin,
            global_config["RRD_DIR"],
            global_config["RRD_DISK_CACHE"],
        )
        subprocess.call(
            _cmd,
            shell=True
        )
        e_time = time.time()
        self.log("command {} took {}".format(_cmd, logging_tools.get_diff_time_str(e_time - s_time)))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def get_tc_dict(self, step):
        if step not in self.tc_dict:
            _dict = {_key: rrd_tools.RRA.parse_width_str(_key, step) for _key in self.rrd_coverage}
            _dict = {_key: _value for _key, _value in _dict.iteritems() if _value is not None}
            self.tc_dict[step] = _dict
            self.log("target coverage (step={:d}): {:d} entries".format(step, len(self.tc_dict)))
            for _idx, _key in enumerate(sorted(_dict.iterkeys()), 1):
                self.log(" {:2d} :: {} -> {}".format(_idx, _key, _dict[_key]["name"]))
        return self.tc_dict[step]

    def _disable_rrd_cached(self):
        self.__rrd_cached_running = False
        self.send_pool_message("disable_rrd_cached")

    def _enable_rrd_cached(self):
        self.send_pool_message("enable_rrd_cached")

    def check_size(self):
        # init target coverage dict
        self.tc_dict = {}
        if not rrdtool:
            self.log("no rrdtool, ignoring resize call", logging_tools.LOG_LEVEL_WARN)
        elif not self.rrd_coverage:
            self.log("rrd_coverage is empty", logging_tools.LOG_LEVEL_WARN)
        elif not global_config["MODIFY_RRD_COVERAGE"]:
            self.log("rrd_coverage modification is disabled", logging_tools.LOG_LEVEL_WARN)
        else:
            # improvement: create new files in a separate directory, move them (in batch mode, every
            # 20 RRDs or so) back to the main directory while rrdcached is stopped
            self.__rrd_cached_running = True
            s_time = time.time()
            _found, _changed = (0, 0)
            self.log("checking sizes of RRD-graphs in {}".format(self.rrd_root))
            for _dir, _dir_list, _file_list in os.walk(self.rrd_root):
                _rrd_files = [_entry for _entry in _file_list if _entry.endswith(".rrd")]
                for _rrd_file in sorted(_rrd_files):
                    if self.check_rrd_file(os.path.join(_dir, _rrd_file)):
                        _changed += 1
                    _found += 1
                    if MAX_FOUND and _found >= MAX_FOUND or not self["run_flag"]:
                        break
                    self.step()
                if MAX_FOUND and _found >= MAX_FOUND or not self["run_flag"]:
                    break
            e_time = time.time()
            self.log("found {:d}, changed {:d}, took {} ({} per entry) ".format(
                _found,
                _changed,
                logging_tools.get_diff_time_str(e_time - s_time),
                logging_tools.get_diff_time_str((e_time - s_time) / max(1, _found)),
            ))
            if not self.__rrd_cached_running:
                self._enable_rrd_cached()

    def find_best_tc(self, rra_name, tc_dict):
        _tw = rrd_tools.RRA.total_width(rra_name)
        _min_key = min([(abs(_tw - _value["total"]), _key) for _key, _value in tc_dict.iteritems()])[1]
        return _min_key

    def check_rrd_file(self, f_name):
        _changed = False
        s_time = time.time()
        try:
            _old_size = os.stat(f_name)[stat.ST_SIZE]
        except:
            self.log("cannot get size of {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            _old_size = 0
        else:
            if _old_size:
                try:
                    _rrd = rrd_tools.RRD(f_name, log_com=self.log, build_rras=False, verbose=self.__verbose)
                except:
                    # check if file is not an rrd file
                    _content = file(f_name, "rb").read()
                    if f_name.endswith(".rrd") and _content[:3] != "RRD":
                        self.log("file {} has no RRD header, trying to remove it".format(f_name), logging_tools.LOG_LEVEL_ERROR)
                        try:
                            os.unlink(f_name)
                        except:
                            pass
                    else:
                        self.log("cannot get info about {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        for _line in process_tools.exception_info().log_lines:
                            self.log(_line, logging_tools.LOG_LEVEL_ERROR)
                else:
                    _changed = self.check_rrd_file_2(f_name, _rrd)
                    if _changed:
                        _new_size = os.stat(f_name)[stat.ST_SIZE]
                        e_time = time.time()
                        self.log(
                            "modification of {} took {} ({} -> {} Bytes)".format(
                                f_name,
                                logging_tools.get_diff_time_str(e_time - s_time),
                                _old_size,
                                _new_size,
                            )
                        )
            else:
                self.log("file {} is empty".format(f_name), logging_tools.LOG_LEVEL_WARN)
        return _changed

    def find_best_rra_name(self, rra_names, tc_dict, tc_key):
        _min_key = min([(abs(rrd_tools.RRA.total_width(_name) - tc_dict[tc_key]["total"]), _name) for _name in rra_names])[1]
        return _min_key

    def find_ref_rras(self, cf, rra_names):
        return sorted(list(set([_entry for _entry in rra_names if _entry.startswith("RRA-{}-".format(cf))])), key=rrd_tools.RRA.total_width)

    def check_rrd_file_2(self, f_name, _rrd):
        # flush cache
        _rrd_short_names = set(_rrd["rra_short_names"])
        tc_dict = self.get_tc_dict(_rrd["step"])
        _target_short_names = set([_value["name"] for _value in tc_dict.itervalues()])
        if _rrd_short_names != _target_short_names:
            _rrd.build_rras()
            self.log("RRAs for {} differ from target".format(f_name))
            if self.__rrd_cached_running:
                self._disable_rrd_cached()
                # we should wait a few seconds to wait for process shutdown
                self.log("waiting for 5 seconds ...", logging_tools.LOG_LEVEL_WARN)
                time.sleep(5)
            # try:
            #    rrdtool.flushcached("--daemon", self.rrd_cache_socket, f_name)
            # except:
            #    self.log("error flushing {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            # pprint.pprint(info)
            _prev_names = set([_entry for _entry in _rrd["rra_names"]])
            _prev_popcount = {_key: _rrd["rra_dict"][_key].popcount[1] for _key in _prev_names}
            _new_names = set()
            _new_popcount = {}
            for _key in tc_dict.iterkeys():
                _short_src_rra_name = self.find_best_rra_name(_rrd["rra_short_names"], tc_dict, _key)
                # find best srouce
                _src_rra_names = [_name for _name in _rrd["rra_names"] if _name.endswith("-{}".format(_short_src_rra_name))]
                self.log("for '{}' we will use '{}' ({})".format(_key, _short_src_rra_name, ", ".join(_src_rra_names)))
                _tc_value = tc_dict[_key]
                for _src_rra_name in _src_rra_names:
                    _src_rra = _rrd["rra_dict"][_src_rra_name]
                    # add RRA/CF to name
                    _tc_full_name = rrd_tools.RRA.fill_rra_name(_tc_value["name"], _src_rra_name)
                    # is needed in target
                    _new_names.add(_tc_full_name)
                    # check if this RRA is already present
                    if _tc_full_name not in _prev_names:
                        _src_cf = rrd_tools.RRA.parse_cf(_src_rra_name)
                        # print _src_rra, _tc_value
                        new_rra = rrd_tools.RRA.create(
                            step=_rrd["step"],
                            rows=_tc_value["rows"],
                            cf=_src_cf,
                            xff=_src_rra.xff,
                            pdp=_tc_value["pdp"],
                            ref_rra=_src_rra,
                            log_com=_rrd.log,
                        )
                        new_rra.fit_data([_rrd["rra_dict"][_name] for _name in self.find_ref_rras(_src_cf, _rrd["rra_names"])])
                        _rrd.add_rra(new_rra)
                    else:
                        new_rra = _src_rra
                    _new_popcount[_tc_full_name] = new_rra.popcount[1]
            # delete old rras
            [_rrd.remove_rra(_del_name) for _del_name in _prev_names - _new_names]
            self.log("RRA list changed from")
            self.log("  {}".format(", ".join(["{} ({:d})".format(_name, _prev_popcount[_name]) for _name in sorted(list(_prev_names))])))
            self.log("to")
            self.log("  {}".format(", ".join(["{} ({:d})".format(_name, _new_popcount[_name]) for _name in sorted(list(_new_names))])))
            try:
                file(f_name, "wb").write(_rrd.content())
            except:
                self.log(
                    "error writing RRA to {}: {}".format(f_name, process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR
                )
            _changed = True
        else:
            _changed = False
        return _changed

    def loop_post(self):
        if self.do_sync:
            self.sync_ram_to_disk()
        self.__log_template.close()
