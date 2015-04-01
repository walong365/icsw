# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" config part of md-config-server """

from initat.md_config_server.config.content_emitter import content_emitter
from lxml.builder import E  # @UnresolvedImport
import codecs
import configfile
import logging_tools
import os
import process_tools


__all__ = [
    "config_dir",
]


global_config = configfile.get_global_config(process_tools.get_programm_name())


class config_dir(content_emitter):
    def __init__(self, name, gen_conf, build_proc):
        self.name = "{}.d".format(name)
        self.__build_proc = build_proc
        self.host_pks = set()
        self.refresh(gen_conf)
        self.act_content, self.prev_content = ([], [])

    def clear(self):
        self.__dict = {}

    def refresh(self, gen_conf):
        # ???
        self.clear()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, log_level)

    def get_name(self):
        return self.name

    def add_device(self, c_list, host):
        host_conf = c_list[0]
        self.host_pks.add(host.pk)
        self[host_conf.name] = c_list

    def values(self):
        return self.__dict.values()

    def __contains__(self, key):
        return key in self.__dict

    def __getitem__(self, key):
        return self.__dict[key]

    def __setitem__(self, key, value):
        self.__dict[key] = value

    def __delitem__(self, key):
        del self.__dict[key]

    def has_key(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()

    def create_content(self, etc_dir):
        cfg_written = []
        # check for missing files, FIXME
        cfg_dir = os.path.join(etc_dir, self.name)
        self.log("creating entries in {}".format(cfg_dir))
        new_entries = set()
        for key in sorted(self.keys()):
            new_entries.add("{}.cfg".format(key))
            cfg_name = os.path.join(cfg_dir, "{}.cfg".format(key))
            # check for changed content, FIXME
            content = self._create_sub_content(key)
            try:
                codecs.open(cfg_name, "w", "utf-8").write(u"\n".join(content + [u""]))
            except IOError:
                self.log(
                    "Error writing content of {} to {}: {}".format(
                        key,
                        cfg_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
            else:
                os.chmod(cfg_name, 0644)
                cfg_written.append(key)
        present_entries = set(os.listdir(cfg_dir))
        del_entries = present_entries - new_entries
        _dbg = global_config["DEBUG"]
        if del_entries:
            self.log(
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
                    self.log(
                        "cannot remove {}: {}".format(
                            full_name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    if _dbg:
                        self.log("removed {}".format(full_name), logging_tools.LOG_LEVEL_WARN)
        return cfg_written

    def _create_sub_content(self, key):
        content = []
        for entry in self[key]:
            content.extend(self._emit_content(entry.obj_type, entry))
        return content

    def get_xml(self):
        res_dict = {}
        for key, value in self.__dict.iteritems():
            prev_tag = None
            for entry in value:
                if entry.obj_type != prev_tag:
                    if entry.obj_type not in res_dict:
                        res_xml = getattr(E, "{}_list".format(entry.obj_type))()
                        res_dict[entry.obj_type] = res_xml
                    else:
                        res_xml = res_dict[entry.obj_type]
                    prev_tag = entry.obj_type
                res_xml.append(getattr(E, entry.obj_type)(**dict([(key, self._build_value_string(key, entry[key])) for key in sorted(entry.iterkeys())])))
        return list(res_dict.itervalues())
