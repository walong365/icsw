# Copyright (C) 2008-2014,2016-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
"""
mon_config_containers, part of md-config-server

defines two structures:
MonFileContainer: holds one or more BaseConfigs (for a device for example)
MonDirContainer: holds a directory of MonFileContainers
"""

import codecs
import hashlib
import os
import time

from lxml.builder import E

from initat.tools import logging_tools, process_tools
from .global_config import global_config
from ..base_config.mon_base_config import LogBufferMixin

__all__ = [
    "MonFileContainer",
    "MonDirContainer",
]


class MonFileContainer(dict, LogBufferMixin):
    def __init__(self, name):
        dict.__init__(self)
        LogBufferMixin.__init__(self)
        # holds a list (and sometimes a dict) of config elements of the same type of {Flat, Structured}MonBaseConfig
        self.name = name
        # clear list and dict
        self.clear()
        self._cur_hash = None
        self._generation = 0

    def __repr__(self):
        return "MonFileContainer {}".format(self.name)

    def clear(self):
        self._obj_list = []
        super(MonFileContainer, self).clear()

    def ignore_content(self, obj):
        return False

    @property
    def object_list(self):
        return self._obj_list

    def append(self, value):
        self._obj_list.append(value)

    def extend(self, value):
        self._obj_list.extend(value)

    def add_object(self, value):
        self._obj_list.append(value)

    @property
    def is_valid(self):
        return True

    def get_file_name(self, parent_dir):
        if self.name.startswith("/"):
            return self.name
        else:
            return os.path.normpath(os.path.join(parent_dir, "{}.cfg".format(self.name)))

    @property
    def header(self):
        return [
            "# created: {}".format(time.ctime()),
            "# current hash: {}".format(self._cur_hash or "N/A"),
            "# generation: {:d}".format(self._generation),
            "",
        ]

    def create_content(self, log_com):
        # builds a new config and handles hash changes
        new_hash, info_str = self.get_content()
        if new_hash != self._cur_hash:
            self._cur_hash = new_hash
            self._generation += 1
            if info_str:
                log_com(info_str)
            return True
        else:
            return False

    def get_content(self):
        cur_hash = hashlib.new("md5")
        act_list = self.object_list
        self._content = []
        _types = {}
        if act_list:
            for act_le in act_list:
                if self.ignore_content(act_le):
                    continue
                _types.setdefault(act_le.obj_type, []).append(True)
                self._content.extend(act_le.emit_content())
            [cur_hash.update(_line.encode("utf8")) for _line in self._content]
            _info_str = "created {} for {}: {}".format(
                logging_tools.get_plural("entry", len(act_list)),
                logging_tools.get_plural("object_type", len(_types)),
                ", ".join(sorted(_types.keys())),
            )
        else:
            _info_str = ""
        return cur_hash.hexdigest(), _info_str

    def get_xml(self):
        res_xml = getattr(E, "{}_list".format(self.name))()
        for act_le in self.object_list:
            if self.ignore_content(act_le):
                continue
            res_xml.append(act_le.emit_xml())
        return [res_xml]

    def write_content(self, cfg_stats, parent_dir, log_com):
        act_cfg_name = self.get_file_name(parent_dir)
        if self.create_content(log_com):
            try:
                codecs.open(act_cfg_name, "w", "utf-8").write(
                    "\n".join(
                        self.header + self._content + [""]
                    )
                )
            except IOError:
                log_com(
                    "Error writing content of {} to {}: {}".format(
                        self.name,
                        act_cfg_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                self._content = []
            else:
                os.chmod(act_cfg_name, 0o644)
                cfg_stats.add(act_cfg_name)
        elif not self._content:
            # crate empty config file
            cfg_stats.add(act_cfg_name, empty=True)
            log_com(
                "creating empty file {}".format(act_cfg_name),
                logging_tools.LOG_LEVEL_WARN
            )
            open(act_cfg_name, "w").write("\n")
        else:
            # no change
            pass


class MonDirContainer(dict, LogBufferMixin):
    def __init__(self, name, **kwargs):
        dict.__init__(self)
        LogBufferMixin.__init__(self)
        self.__full_build = kwargs.get("full_build", True)
        # directory containing MonBaseContainers
        self.name = name
        self.clear()

    def __repr__(self):
        return "MonDirContainer {}".format(self.name)

    def clear(self):
        self.host_pks = set()
        super(MonDirContainer, self).clear()

    def refresh(self, gen_conf):
        # refresh, simply clear the current container
        self.clear()

    def add_entry(self, c_list, host):
        self.host_pks.add(host.pk)
        self[c_list.name] = c_list

    def get_file_name(self, parent_dir):
        if self.name.startswith("/"):
            return self.name
        else:
            return os.path.normpath(os.path.join(parent_dir, "{}.d".format(self.name)))

    def write_content(self, cfg_stats, etc_dir, log_com):
        from ..config import CfgEmitStats
        cfg_dir = self.get_file_name(etc_dir)
        if not os.path.isdir(cfg_dir):
            log_com("creating dir {}".format(cfg_dir))
            os.mkdir(cfg_dir)
        log_com("creating entries in {}".format(cfg_dir))
        loc_stats = CfgEmitStats()
        for key in sorted(self.keys()):
            self[key].write_content(loc_stats, cfg_dir, log_com)
        cfg_stats.merge(loc_stats)
        new_entries = set([os.path.basename(_entry) for _entry in loc_stats.total_written])
        present_entries = set(os.listdir(cfg_dir))
        del_entries = present_entries - new_entries
        _dbg = global_config["DEBUG"]
        if del_entries and self.__full_build:
            log_com(
                "removing {} from {}".format(
                    logging_tools.get_plural("entry", len(del_entries)),
                    cfg_dir,
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for del_entry in del_entries:
                full_name = os.path.join(cfg_dir, del_entry)
                try:
                    os.unlink(full_name)
                except:
                    log_com(
                        "cannot remove {}: {}".format(
                            full_name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    if _dbg:
                        log_com(
                            "removed {}".format(full_name),
                            logging_tools.LOG_LEVEL_WARN
                        )

    def get_xml(self):
        res_dict = {}
        for key, value in self.items():
            prev_tag = None
            for entry in value.object_list:
                if entry.obj_type != prev_tag:
                    if entry.obj_type not in res_dict:
                        res_xml = getattr(E, "{}_list".format(entry.obj_type))()
                        res_dict[entry.obj_type] = res_xml
                    else:
                        res_xml = res_dict[entry.obj_type]
                    prev_tag = entry.obj_type
                res_xml.append(entry.emit_xml())
        return list(res_dict.values())
