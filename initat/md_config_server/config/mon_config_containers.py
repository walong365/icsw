# Copyright (C) 2008-2014,2016 Andreas Lang-Nevyjel, init.at
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
import os

from lxml.builder import E

from initat.tools import logging_tools, process_tools, configfile
from .mon_base_config import LogBufferMixin

__all__ = [
    "MonFileContainer",
    "MonDirContainer",
]


global_config = configfile.get_global_config(process_tools.get_programm_name())


class MonFileContainer(dict, LogBufferMixin):
    def __init__(self, name):
        dict.__init__(self)
        LogBufferMixin.__init__(self)
        # holds a list (and sometimes a dict) of config elements of the same type of {Flat, Structured}MonBaseConfig
        self.name = name
        # clear list and dict
        self.clear()
        self.act_content, self.prev_content = ([], [])

    def __repr__(self):
        return u"MonFileContainer {}".format(self.name)

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
        if self.name in ["uwsgi"]:
            return "/opt/cluster/etc/uwsgi/icinga.wsgi.ini"
        else:
            return os.path.normpath(os.path.join(parent_dir, "{}.cfg".format(self.name)))

    def create_content(self, log_com):
        # if self.act_content:
        self.old_content = [_v for _v in self.act_content]
        self.act_content = self.get_content(log_com)

    def set_previous_config(self, prev_conf):
        self.act_content = prev_conf.act_content

    def get_content(self, log_com):
        act_list = self.object_list
        content = []
        _types = {}
        if act_list:
            for act_le in act_list:
                if self.ignore_content(act_le):
                    continue
                _types.setdefault(act_le.obj_type, []).append(True)
                content.extend(act_le.emit_content())
            log_com(
                "created {} for {}: {}".format(
                    logging_tools.get_plural("entry", len(act_list)),
                    logging_tools.get_plural("object_type", len(_types)),
                    ", ".join(sorted(_types.keys())),
                )
            )
        return content

    def get_xml(self):
        res_xml = getattr(E, "{}_list".format(self.name))()
        for act_le in self.object_list:
            if self.ignore_content(act_le):
                continue
            res_xml.append(act_le.emit_xml())
        return [res_xml]

    def write_content(self, cfg_stats, parent_dir, log_com):
        act_cfg_name = self.get_file_name(parent_dir)
        self.create_content(log_com)
        if self.act_content != self.old_content:
            try:
                codecs.open(act_cfg_name, "w", "utf-8").write(u"\n".join(self.act_content + [u""]))
            except IOError:
                log_com(
                    "Error writing content of {} to {}: {}".format(
                        self.name,
                        act_cfg_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                self.act_content = []
            else:
                os.chmod(act_cfg_name, 0644)
                cfg_stats.add(act_cfg_name)
        elif not self.act_content:
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
    def __init__(self, name):
        dict.__init__(self)
        LogBufferMixin.__init__(self)
        # directory containing MonBaseContainers
        self.name = "{}.d".format(name)
        self.refresh()

    def __repr__(self):
        return u"MonDirContainer {}".format(self.name)

    def clear(self):
        super(MonDirContainer, self).clear()

    def refresh(self):
        # setup dir
        self.host_pks = set()
        self.clear()

    def add_entry(self, c_list, host):
        # add a MonFileContainer
        # print "*** ad", c_list, type(c_list), host
        # host_conf = c_list[0]
        self.host_pks.add(host.pk)
        self[c_list.name] = c_list

    def write_content(self, cfg_stats, etc_dir, log_com):
        from ..config import CfgEmitStats
        cfg_dir = os.path.join(etc_dir, self.name)
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
        if del_entries:
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
        for key, value in self.iteritems():
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
        return list(res_dict.itervalues())
