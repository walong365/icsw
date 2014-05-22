# Copyright (C) 2012,2014 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone
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
""" handles module dependencies """

import commands
import copy
import fnmatch
import logging_tools
import os
import re

class dependency_handler(object):
    def __init__(self, kernel_dir, **kwargs):
        self.log_com = kwargs.get("log_com", None)
        self.kernel_dir = kernel_dir
        # linux_native = True for /lib/modules/<kernel> structure
        # linux_natvie = False (default) for ICSW /tftpboot/kernels/<kernel>/lib/modules/<kernel> structure
        self.linux_native = kwargs.get("linux_native", False)
        self.log("kernel_dir is {}".format(self.kernel_dir))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.log_com:
            self.log_com("[dh] {}".format(what), log_level)
        else:
            print "[dh {:2d} {}] {}".format(log_level, logging_tools.get_log_level_str(log_level), what)
    def _shorten_module_name(self, mod_name):
        return mod_name.endswith(".ko") and mod_name[:-3] or (mod_name.endswith(".o") and mod_name[:-2] or mod_name)
    def get_dep_file_name(self, ftype="dep"):
        if self.linux_native:
            dep_file_dir = self.kernel_dir
        else:
            dep_file_dir = os.path.join(self.kernel_dir, "lib", "modules")
            if os.path.isdir(dep_file_dir):
                dep_file_dir = os.path.join(dep_file_dir, os.listdir(dep_file_dir)[0])
        if os.path.isdir(dep_file_dir):
            dep_file = os.path.join(dep_file_dir, "modules.{}".format(ftype))
            if os.path.isfile(dep_file):
                pass
            else:
                self.log("dep_file {} not found".format(dep_file), logging_tools.LOG_LEVEL_ERROR)
                dep_file = None
        else:
            self.log("dep_dir {} not found".format(dep_file_dir), logging_tools.LOG_LEVEL_ERROR)
            dep_file = None
        return dep_file
    def find_module_by_modalias(self, alias_list, **kwargs):
        dep_file = self.get_dep_file_name(ftype="alias")
        resolv_dict = {key : [] for key in alias_list}
        for line in file(dep_file, "r").readlines():
            _parts = line.strip().split()
            if len(_parts) > 2 and _parts[0] == "alias" and _parts[1].startswith("pci:"):
                try:
                    _mc = re.compile("^{}$".format(_parts[1].replace("*", ".*").replace("?", ".")))
                except:
                    # cannot create regexp, forget id
                    pass
                else:
                    for cur_alias in alias_list:
                        if _mc.match(cur_alias):
                            _mod = _parts[2]
                            if not _mod in resolv_dict[cur_alias]:
                                resolv_dict[cur_alias].append(_mod)
        return resolv_dict
    def resolve(self, mod_list, **kwargs):
        verbose = kwargs.get("verbose", 0)
        # pure module names
        mod_names = [self._shorten_module_name(key) for key in mod_list]
        # list of modules with postfix
        matches_found = set()
        # lut: short_name -> full name (with postfix but without path)
        mod_dict = {}
        # lut: module with with postfix -> full path
        file_dict = {}
        for act_dir, _dir_names, file_names in os.walk(self.kernel_dir):
            for f_name in file_names:
                mod_name = f_name[:-3] if f_name.endswith(".ko") else (f_name[:-2] if f_name.endswith(".o") else f_name)
                # print f_name, mod_name
                file_dict[f_name] = os.path.join(act_dir, f_name)
                match_list = [match_name for match_name in mod_names if fnmatch.fnmatch(mod_name, match_name)]
                if match_list:
                    matches_found.add(f_name)
        dep_file = self.get_dep_file_name()
        if dep_file:
            dep_lines = [line.replace("\t", " ").strip() for line in file(dep_file, "r").read().split("\n") if line.strip()]
            dep_lines2 = []
            add_next_line = False
            for dep_line in dep_lines:
                if dep_line.endswith("\\"):
                    anl = True
                    dep_line = dep_line[:-1]
                else:
                    anl = False
                if add_next_line:
                    dep_lines2[-1] += " {}".format(dep_line)
                else:
                    dep_lines2 += [dep_line]
                add_next_line = anl
            # simplify
            dep_lines2 = [line.replace("//", "/").replace("//", "/").split(":") for line in dep_lines2]
            dep_dict = dict([(key, value.strip().split()) for key, value in [entry for entry in dep_lines2 if len(entry) == 2]])
            # kernel_mod_dict = dict([(os.path.basename(key), key) for key in dep_dict.iterkeys()])
            kernel_lut_dict = dict([(key, os.path.basename(key)) for key in dep_dict.iterkeys()])
            dep_dict = dict([(os.path.basename(key), set([kernel_lut_dict[m_path] for m_path in value])) for key, value in dep_dict.iteritems()])
            first_found = copy.deepcopy(matches_found)
            m_iter = 0
            while True:
                cur_size = len(matches_found)
                m_iter += 1
                # next_dep = copy.deepcopy(auto_dep)
                if verbose:
                    self.log(" - {:2d} {}".format(m_iter, ", ".join(sorted(list(matches_found)))))
                for cur_match in list(matches_found):
                    matches_found |= set(dep_dict[cur_match])
                if len(matches_found) == cur_size:
                    break
            self.auto_modules = sorted(list(matches_found - first_found))
        # update mod_dict
        for entry in matches_found:
            mod_dict[self._shorten_module_name(entry)] = entry
        not_found_mods = [key for key in mod_names if key not in mod_dict]
        found_mods = [value for key, value in mod_dict.iteritems()]
        if kwargs.get("firmware", True):
            fw_lines = []
            for f_module in found_mods:
                fw_stat, fw_out = commands.getstatusoutput("modinfo {}".format(file_dict[f_module]))
                if fw_stat:
                    self.log(
                        "Error calling modinfo for {} ({:d}): {}".format(
                            f_module,
                            fw_stat,
                            fw_out
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    loc_fw_lines = [line.split(":")[1].strip() for line in fw_out.split("\n") if line.lower().startswith("firmware:")]
                    if loc_fw_lines:
                        self.log(
                            "found {} for module {}: {}".format(
                                logging_tools.get_plural("firmware file", len(loc_fw_lines)),
                                f_module,
                                ", ".join(loc_fw_lines)
                            )
                        )
                        fw_lines.extend(loc_fw_lines)
                    else:
                        self.log("no firmware files needed for {}".format(f_module))
            self.firmware_list = fw_lines
        if kwargs.get("resolve_module_dict", False):
            mod_dict = dict([(key, file_dict[value]) for key, value in mod_dict.iteritems()])
        self.module_dict = mod_dict
        self.module_list = [file_dict[entry] for entry in matches_found]
        self.error_list = not_found_mods

