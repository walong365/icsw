#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel
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

import sys
import cs_base_class
import server_command
import os
import logging_tools
import time
import re
import process_tools

try:
    import HTMLParser
except ImportError:
    my_html_parser = None
else:
    class my_main_parser(HTMLParser.HTMLParser):
        def __init__(self, sys_dict={}):
            HTMLParser.HTMLParser.__init__(self)
            self.system = "%s_%s" % (sys_dict.get("vendor" , "?"),
                                     sys_dict.get("version", "?"))
            self.sub_sites = []
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                attr_dict = dict(attrs)
                if attr_dict.has_key("href"):
                    self.sub_sites.append(attr_dict["href"])
                    #print "Encountered the beginning of a %s tag" % tag, attr_dict
        def handle_endtag(self, tag):
            pass

    class my_sub_parser(HTMLParser.HTMLParser):
        def __init__(self):
            HTMLParser.HTMLParser.__init__(self)
            self.found_rpms = []
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                attr_dict = dict(attrs)
                if attr_dict.has_key("href") and attr_dict["href"].endswith(".rpm"):
                    try:
                        new_rpm = rpm_info(attr_dict["href"])
                    except IndexError:
                        new_rpm = None
                    else:
                        self.found_rpms.append(new_rpm)
        def handle_endtag(self, tag):
            pass

class rpm_info(object):
    def __init__(self, name):
        self.rpm_name = name
        self.parse_rpm_name()
    def parse_rpm_name(self):
        long_rp = re.match("^(?P<name>\S+)-(?P<version>[^-]+)-(?P<release>[^-]+)\\.(?P<arch>[^-]+)\\.rpm$", self.rpm_name)
        short_rp = re.match("^(?P<name>\S+)\\.(?P<arch>\S+)\\.rpm$", self.rpm_name)
        if long_rp:
            self.name, self.version, self.release, self.arch = (long_rp.group("name"),
                                                                long_rp.group("version"),
                                                                long_rp.group("release"),
                                                                long_rp.group("arch"))
            if self.release != "latest" and self.version[0].isdigit() and self.release[0].isdigit():
                self.version_parts = [int(x) for x in self.version.split(".") if x.isdigit()]
                self.release_parts = [int(x) for x in self.release.split(".") if x.isdigit()]
            else:
                raise IndexError
        elif short_rp:
            raise IndexError
        else:
            raise ValueError, self.rpm_name
    def get_full_name(self):
        return self.rpm_name
    def get_name(self):
        return self.name
    def get_version(self):
        return self.version
    def get_release(self):
        return self.release
    def get_arch(self):
        return self.arch
    def arch_is_ok(self, sys_arch):
        if self.arch == sys_arch:
            return True
        elif self.arch == "noarch":
            return True
        elif re.match("^i.86$", self.arch) and re.match("^i.86$", sys_arch):
            return True
        else:
            return False
    def is_newer(self, op):
        m_v, o_v = ([x for x in self.version_parts],
                    [x for x in op.version_parts])
        if len(m_v) > len(o_v):
            o_v.extend([0] * (len(m_v) - len(o_v)))
        elif len(o_v) > len(m_v):
            m_v.extend([0] * (len(o_v) - len(m_v)))
        m_v.extend(self.release_parts)
        o_v.extend(op.release_parts)
        if len(m_v) > len(o_v):
            o_v.extend([0] * (len(m_v) - len(o_v)))
        elif len(o_v) > len(m_v):
            m_v.extend([0] * (len(o_v) - len(m_v)))
        for m_p, o_p in zip(m_v, o_v):
            if m_p > o_p:
                return True
            elif m_p < o_p:
                return False
        return False
    def __repr__(self):
        return "Package: %s-%s-%s.%s" % (self.name, self.version, self.release, self.arch)

def parse_local_path(site):
    rpm_dir = site.split(":", 1)[1]
    rpm_dict = {}
    if os.path.isdir(rpm_dir):
        sub_dirs = os.listdir(rpm_dir)
        if "general" in sub_dirs:
            for sys_name in sub_dirs:
                for file_found in [x for x in os.listdir("%s/%s" % (rpm_dir, sys_name)) if x.endswith(".rpm")]:
                    try:
                        new_rpm = rpm_info(file_found)
                    except IndexError:
                        pass
                    else:
                        rpm_dict.setdefault(sys_name, []).append(new_rpm)
        else:
            raise StandardError, "'general' not in sub_dir_list"
    else:
        raise IOError, "not a directory (%s)" % (rpm_dir)
    return rpm_dict

class check_for_updates(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_used_config_keys(["UPDATE_SITE", "RPM_TARGET_DIR"])
    def call_it(self, opt_dict, call_params):
        sys.path.append("/usr/local/sbin")
        sys.path.append("/usr/local/sbin/modules")
        import urllib
        import rpm_mod
        log_lines, sys_dict = process_tools.fetch_sysinfo("/")
        main_site = call_params.get_g_config()["UPDATE_SITE"]
        all_rpms = {}
        if main_site.startswith("http:"):
            update_smode = "http"
            try:
                http_struct = urllib.urlopen(main_site)
            except:
                ret_str = "error for urlopen to %s: %s" % (main_site,
                                                           process_tools.get_except_info())
            else:
                my_mp = my_main_parser(sys_dict)
                while True:
                    line = http_struct.read()
                    if line:
                        try:
                            my_mp.feed(line)
                        except:
                            pass   
                    else:
                        break
                all_rpms = {}
                for sub_site in my_mp.sub_sites:
                    host_loc = urllib.urlopen("%s/%s" % (main_site, sub_site))
                    my_subp = my_sub_parser()
                    while True:
                        line = host_loc.read()
                        if line:
                            try:
                                my_subp.feed(line)
                            except:
                                pass
                        else:
                            break
                    sys_ver = sub_site
                    if sys_ver.endswith("/"):
                        sys_ver = sys_ver[:-1]
                    all_rpms[sys_ver] = my_subp.found_rpms
            if not all_rpms:
                ret_str = "warning no rpms found at http_site %s" % (main_site)
        elif main_site.startswith("local:"):
            update_smode = "local"
            try:
                all_rpms = parse_local_path(main_site)
            except:
                ret_str = "error for parsing local_site %s: %s" % (main_site,
                                                                   process_tools.get_except_info())
            else:
                if not all_rpms:
                    ret_str = "warning no rpms found at local_site %s" % (main_site)
        else:
            ret_str = "error unknown type for main_site %s" % (main_site)
        if all_rpms:
            rpm_dict = {}
            for sys_ver, rpm_list in all_rpms.iteritems():
                for rpm in rpm_list:
                    rpm_dict.setdefault(rpm.get_name(), [])
                    rpm_dict[rpm.get_name()].append((sys_ver, rpm))
            # get local rpm-dict
            call_params.log("fetching local rpm-dict ...")
            log_list, ret_dict, stat = rpm_mod.rpmlist_int("/", [], False)
            for log in log_list:
                call_params.log(log)
            if stat:
                ret_str = "error getting rpm-dict (%d): %s" % (stat, ret_dict)
            else:
                remote_packs = sorted(rpm_dict.keys())
                num_rem_packages = 0
                my_arch = sys_dict["arch"]
                my_sys_ver = "%s_%s" % (sys_dict["vendor"], sys_dict["version"])
                call_params.log("my architecture is %s, sys_str is %s" % (my_arch,
                                                                          my_sys_ver))
                call_params.log("found %s: %s" % (logging_tools.get_plural("remote package", len(remote_packs)),
                                                  ", ".join(remote_packs)))
                local_packs = [x for x in remote_packs if ret_dict.has_key(x)]
                call_params.log("found %s: %s" % (logging_tools.get_plural("local package", len(local_packs)),
                                                  ", ".join(local_packs)))
                newer_packs = []
                other_newer_packs = []
                for local_pack_name in local_packs:
                    if len(ret_dict[local_pack_name]) == 1:
                        loc_pack_info = ret_dict[local_pack_name][0]
                        loc_pack_info_str = "%s-%s-%s.%s.rpm" % (local_pack_name,
                                                                 loc_pack_info["version"],
                                                                 loc_pack_info["release"],
                                                                 loc_pack_info["arch"])
                        local_pack = rpm_info(loc_pack_info_str)
                        new_sys, new_pack, act_new_pack = (None, None, local_pack)
                        other_new_sys, other_new_pack, other_act_new_pack = (None, None, local_pack)
                        for sys_ver, rem_pack in rpm_dict[local_pack_name]:
                            num_rem_packages += 1
                            if (my_sys_ver == sys_ver or sys_ver == "general") and rem_pack.arch_is_ok(my_arch):
                                if rem_pack.is_newer(act_new_pack):
                                    new_sys, new_pack, act_new_pack = (sys_ver, rem_pack, rem_pack)
                            elif rem_pack.is_newer(other_act_new_pack):
                                other_new_sys, other_new_pack, other_act_new_pack = (sys_ver, rem_pack, rem_pack)
                        if new_sys:
                            newer_packs.append((new_sys, new_pack))
                        if other_new_sys:
                            other_newer_packs.append((other_new_sys, other_act_new_pack))
                    else:
                        call_params.log("not implemented: more than one instance (%d) installed of %s" % (len(ret_dict[local_pack_name]),
                                                                                                          local_pack_name))
                if newer_packs:
                    target_dir = call_params.get_g_config()["RPM_TARGET_DIR"]
                    if not os.path.isdir(target_dir):
                        try:
                            os.makedirs(target_dir)
                        except IOError:
                            call_params.log("error creating dir %s: %s" % (target_dir,
                                                                           process_tools.get_except_info()))
                            t_dir_ok = False
                        else:
                            call_params.log("created dir %s" % (target_dir))
                            t_dir_ok = True
                    else:
                        call_params.log("target_dir %s valid" % (target_dir))
                        t_dir_ok = True
                    call_params.log("Found %s:" % (logging_tools.get_plural("newer package", len(newer_packs))))
                    for sys_v, pack in newer_packs:
                        s_time = time.time()
                        call_params.log(" - site %s (%s), sys %s, full_name is %s" % (main_site, update_smode, sys_v, pack.get_full_name()))
                        if update_smode == "http":
                            act_url = "%s/%s/%s" % (main_site, sys_v, pack.get_full_name())
                            act_url_p = urllib.urlopen(act_url)
                            pack_data = act_url_p.read()
                            del act_url_p
                        else:
                            pack_data = file("%s/%s/%s" % (main_site.split(":", 1)[1], sys_v, pack.get_full_name()), "r").read()
                        d_file_name = "%s/%s" % (target_dir,
                                                 pack.get_full_name())
                        call_params.log(" - %s, %s, transfering of %s took %.2f seconds" % (sys_v,
                                                                                            str(pack),
                                                                                            logging_tools.get_plural("byte", len(pack_data)),
                                                                                            time.time() - s_time))
                        if t_dir_ok:
                            try:
                                file(d_file_name, "w").write(pack_data)
                            except:
                                call_params.log(" - error writing package_file %s: %s" % (d_file_name,
                                                                                          process_tools.get_except_info()))
                            else:
                                call_params.log(" - wrote %s" % (d_file_name))
                    ret_str = "ok found %s (checked %s)" % (logging_tools.get_plural("new package", len(newer_packs)),
                                                            logging_tools.get_plural("package", num_rem_packages))
                else:
                    call_params.log("Found no newer packages")
                    ret_str = " ok found no newer packages (checked %s)" % (logging_tools.get_plural("package", num_rem_packages))
                if other_newer_packs:
                    call_params.log("Found %s with wrong sys_version:" % (logging_tools.get_plural("newer package", len(other_newer_packs))))
                    s_array = []
                    for o_sys, o_pack in other_newer_packs:
                        call_params.log(" - %s %s-%s (%s)" % (o_pack.get_name(),
                                                              str(o_pack.get_version()),
                                                              str(o_pack.get_release()),
                                                              o_sys))
                        s_array.append("%s %s-%s (%s)" % (o_pack.get_name(),
                                                          str(o_pack.get_version()),
                                                          str(o_pack.get_release()),
                                                          o_sys))
                    ret_str += ", %s with wrong sys_version: %s" % (logging_tools.get_plural("newer package", len(other_newer_packs)),
                                                                    ", ".join(s_array))
        return ret_str
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
