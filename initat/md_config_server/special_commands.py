#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2012,2013 Andreas Lang-Nevyjel, init.at
#
# this file is part of nagios-config-server
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
""" special tasks for generating md-config-server """

import sys
import re
import logging_tools
import os
import process_tools
import server_command
import time
import copy
from initat.host_monitoring import ipc_comtools
from initat.host_monitoring.modules import supermicro_mod
from initat.cluster.backbone.models import partition, partition_disc, partition_table, partition_fs, \
     netdevice, net_ip, network, lvm_vg, lvm_lv, device, device_variable, md_check_data_store
from django.db.models import Q
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport

EXPECTED_FILE = "/etc/sysconfig/host-monitoring.d/openvpn_expected"

"""
cache_modes, how to handle to cache for special commands
in case of connection problems always use the cache (if set, of course)
ALWAYS   : always use value from cache, even if empty
DYNAMIC  : use cache only when set and not too old, otherwise try to connect to device
REFRESH  : always try to contact device
"""

CACHE_MODES = ["ALWAYS", "DYNAMIC", "REFRESH"]
DEFAULT_CACHE_MODE = "ALWAYS"

def parse_expected():
    ret_dict = {}
    if os.path.isfile(EXPECTED_FILE):
        in_field = open(EXPECTED_FILE, "r").read().split("\n")
        lines = [line.strip() for line in in_field if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if line.count("=") == 1:
                dev_name, dev_stuff = line.split("=", 1)
                dev_dict = {}
                ret_dict[dev_name.strip()] = dev_dict
                instances = dev_stuff.split()
                for instance in instances:
                    inst_parts = instance.split(":")
                    inst_dict = {}
                    dev_dict[inst_parts.pop(0)] = inst_dict
                    for inst_part in inst_parts:
                        c_parts = inst_part.split(",")
                        client_name = c_parts.pop(0)
                        inst_dict[client_name] = True
                        # inst_dict[client_name] = limits.nag_STATE_CRITICAL
                        # if c_parts and c_parts[0].lower() in ["w"]:
                        #    inst_dict[client_name] = limits.nag_STATE_WARNING
    return ret_dict

class special_base(object):
    class Meta:
        # number of retries in case of error
        retries = 1
        # timeout for connection to server
        timeout = 15
        # how long the cache is valid
        cache_timeout = 7 * 24 * 3600
        # wait time in case of connection error
        error_wait = 5
        # contact server
        server_contact = False
    def __init__(self, build_proc, s_check, host, global_config, **kwargs):
        for key in dir(special_base.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(special_base.Meta, key))
        self.Meta.name = self.__class__.__name__.split("_", 1)[1]
        self.ds_name = self.Meta.name
        self.cache_mode = kwargs.get("cache_mode", DEFAULT_CACHE_MODE)
        self.build_process = build_proc
        self.s_check = s_check
        self.host = host
    def _cache_name(self):
        return "/tmp/.md-config-server/%s_%s" % (
            self.host.name,
            self.host.valid_ip)
    def _store_cache(self):
        if self.__force_store_cache:
            cache = E.cache(
                *[cur_res.tree for cur_res in self.__cache],
                num_entries="%d" % (len(self.__cache)),
                created="%d" % (int(time.time()))
            )
        else:
            cache = E.cache(
                *[cur_res.tree for cur_res in self.__server_results],
                num_entries="%d" % (len(self.__server_results)),
                created="%d" % (int(time.time()))
            )
        if False:
            # old file-based cache, ignore
            c_name = self._cache_name()
            if not os.path.isdir(os.path.dirname(c_name)):
                os.makedirs(os.path.dirname(c_name))
                file(c_name, "wb").write(etree.tostring(cache, pretty_print=True))
            self.log("stored tree to %s" % (c_name))
        else:
            # new code for db
            try:
                cur_ds = md_check_data_store.objects.get(
                    Q(device=self.host) &
                    Q(mon_check_command=self.s_check.mon_check_command) &
                    Q(name=self.ds_name))
            except md_check_data_store.DoesNotExist:
                cur_ds = md_check_data_store(
                    device=self.host,
                    mon_check_command=self.s_check.mon_check_command,
                    name=self.ds_name)
                self.log("creating DB-cache")
            else:
                self.log("updating DB-cache")
            cur_ds.data = etree.tostring(cache)
            cur_ds.save()
    def _load_cache(self):
        self.__cache, self.__cache_created, self.__cache_age = ([], 0, 0)
        self.__cache_valid = False
        c_name = self._cache_name()
        if os.path.isfile(c_name):
            # old code
            try:
                c_tree = etree.fromstring(file(c_name, "rb").read())
            except:
                self.log("cannot read xml_tree from %s: %s" % (
                    c_name,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                try:
                    os.unlink(c_name)
                except:
                    self.log("cannot remove invalid cache_file %s: %s" % (c_name, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("loaded cache (%s) from %s" % (
                    logging_tools.get_plural("entry", int(c_tree.attrib["num_entries"])),
                    c_name)
                         )
                self.__cache_created = int(c_tree.get("created", "0"))
                self.__cache_age = abs(time.time() - self.__cache_created)
                self.__cache_valid = self.__cache_age < self.Meta.cache_timeout
                # the copy.deepcopy is important to preserve the root element
                self.__cache = [server_command.srv_command(source=copy.deepcopy(entry)) for entry in c_tree]
                self.__force_store_cache = True
            try:
                os.unlink(c_name)
            except:
                self.log("cannot remove old cache_file %s: %s" % (
                    c_name,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("removed old cache_file %s" % (c_name))
        else:
            try:
                cur_ds = md_check_data_store.objects.get(
                    Q(device=self.host) &
                    Q(mon_check_command=self.s_check.mon_check_command) &
                    Q(name=self.ds_name))
            except md_check_data_store.DoesNotExist:
                pass
            else:
                c_tree = etree.fromstring(cur_ds.data)
                self.log("loaded cache (%s) from db" % (
                    logging_tools.get_plural("entry", int(c_tree.attrib["num_entries"]))
                ))
                self.__cache_created = int(c_tree.get("created", "0"))
                self.__cache_age = abs(time.time() - self.__cache_created)
                self.__cache_valid = self.__cache_age < self.Meta.cache_timeout
                # the copy.deepcopy is important to preserve the root element
                self.__cache = [server_command.srv_command(source=copy.deepcopy(entry)) for entry in c_tree]
    def _show_cache_info(self):
        if self.__cache:
            self.log(
                "cache is present (%s, age is %s, timeout %s, %s)" % (
                    logging_tools.get_plural("entry", len(self.__cache)),
                    logging_tools.get_diff_time_str(self.__cache_age),
                    logging_tools.get_diff_time_str(self.Meta.cache_timeout),
                    "valid" if self.__cache_valid else "invalid",
                )
            )
        else:
            self.log("no cache set")
    def cleanup(self):
        self.build_process = None
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.build_process.mach_log("[sc] %s" % (what), log_level)
    def collrelay(self, command, *args, **kwargs):
        return self._call_server(
            command,
            "collrelay",
            *args,
            **kwargs
        )
    def snmprelay(self, command, *args, **kwargs):
        return self._call_server(
            command,
            "snmp_relay",
            *args,
            snmp_community=self.host.dev_variables["SNMP_READ_COMMUNITY"],
            snmp_version=self.host.dev_variables["SNMP_VERSION"],
            **kwargs
        )
    def _call_server(self, command, server_name, *args, **kwargs):
        if not self.Meta.server_contact:
            # not beautifull but working
            self.log("not allowed to make an external call", logging_tools.LOG_LEVEL_CRITICAL)
            return None
        self.log("calling server '%s' for %s, command is '%s', %s, %s" % (
            server_name,
            self.host.valid_ip,
            command,
            "args is '%s'" % (", ".join([str(value) for value in args])) if args else "no arguments",
            ", ".join(["%s='%s'" % (key, value) for key, value in kwargs.iteritems()]) if kwargs else "no kwargs",
        ))
        connect_to_localhost = kwargs.pop("connect_to_localhost", False)
        conn_ip = "127.0.0.1" if connect_to_localhost else self.host.valid_ip
        if not self.__use_cache:
            # contact the server / device
            srv_reply = None
            for cur_iter in xrange(self.Meta.retries):
                log_str, log_level = (
                    "iteration %d of %d (timeout=%d)" % (cur_iter, self.Meta.retries, self.Meta.timeout),
                    logging_tools.LOG_LEVEL_ERROR,
                )
                s_time = time.time()
                try:
                    srv_reply = ipc_comtools.send_and_receive_zmq(
                        conn_ip,
                        command,
                        *args,
                        server=server_name,
                        zmq_context=self.build_process.zmq_context,
                        port=2001,
                        timeout=self.Meta.timeout,
                        **kwargs)
                except:
                    log_str = "%s, error connecting to '%s' (%s, %s): %s" % (
                        log_str,
                        server_name,
                        conn_ip,
                        command,
                        process_tools.get_except_info()
                    )
                    srv_reply = None
                    self.__server_contact_ok = False
                else:
                    srv_error = srv_reply.xpath(None, ".//ns:result[@state != '0']")
                    if srv_error:
                        self.__server_contact_ok = False
                        log_str = "%s, got an error (%d): %s" % (
                            log_str,
                            int(srv_error[0].attrib["state"]),
                            srv_error[0].attrib["reply"],
                        )
                        srv_reply = None
                    else:
                        e_time = time.time()
                        log_str = "%s, got a valid result in %s" % (
                            log_str,
                            logging_tools.get_diff_time_str(e_time - s_time),
                        )
                        log_level = logging_tools.LOG_LEVEL_OK
                        self.__server_contacts += 1
                        self.__server_results.append(srv_reply)
                self.log(log_str, log_level)
                if srv_reply is not None:
                    break
                self.log("waiting for %d seconds" % (self.Meta.error_wait), logging_tools.LOG_LEVEL_WARN)
                time.sleep(self.Meta.error_wait)
            if srv_reply is None and self.__call_idx == 0 and len(self.__cache):
                # use cache only when first call went wrong and we have something in the cache
                self.__use_cache = True
        if self.__use_cache:
            if len(self.__cache) > self.__call_idx:
                srv_reply = self.__cache[self.__call_idx]
                self.log("take result from cache [index %d]" % (
                    self.__call_idx
                ))
            else:
                self.log(
                    "cache too small (%s)" % (
                        "%d <= %d" % (len(self.__cache), self.__call_idx) if self.__cache else "is empty",
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                srv_reply = None
        self.__call_idx += 1
        return srv_reply
    def real_parameter_name(self, in_name):
        return "{MDC}_%s" % (in_name)
    def get_parameter(self, para_name, xpath_str, command, *args, **kwargs):
        """
        get a paramter, by default as device_variable
        """
        server_type = kwargs.pop("target_server", "collrelay")
        var_type = kwargs.pop("var_type", "s")
        r_para_name = self.real_parameter_name(para_name)
        try:
            cur_var = device_variable.objects.get(Q(device=self.host) & Q(name=r_para_name))
        except device_variable.DoesNotExist:
            srv_result = getattr(self, server_type)(command, *args)
            if srv_result is None:
                self.log("no result, returning None vor parameter %s" % (para_name),
                         logging_tools.LOG_LEVEL_ERROR)
                cur_var = None
            else:
                self.log("requested parameter %s from device via %s" % (para_name, server_type))
                cur_val = srv_result.xpath(None, xpath_str)[0].text
                if var_type == "i":
                    cur_val = int(cur_val)
                cur_var = device_variable(
                    device=self.host,
                    is_public=True,
                    name=r_para_name,
                    description="requested from md-config-server",
                    var_type=var_type,
                )
                cur_var.set_value(cur_val)
                cur_var.save()
        else:
            self.log("read parameter %s from database" % (para_name))
        if cur_var is None:
            return cur_var
        else:
            return cur_var.get_value()
    def __call__(self):
        s_name = self.__class__.__name__.split("_", 1)[1]
        self.log("starting %s for %s, cache_mode is %s" % (s_name, self.host.name, self.cache_mode))
        s_time = time.time()
        # flag to force store the cache (in case of migration of cache entries from FS to DB)
        self.__force_store_cache = False
        if self.Meta.server_contact:
            # at first we load the current cache
            self._load_cache()
            # show information
            self._show_cache_info()
            # use cache flag, dependent on the cache mode
            if self.cache_mode == "ALWAYS":
                self.__use_cache = True
            elif self.cache_mode == "DYNAMIC":
                self.__use_cache = self.__cache_valid
            elif self.cache_mode == "REFRESH":
                self.__use_cache = False
            # anything got from a direct all
            self.__server_contact_ok, self.__server_contacts = (True, 0)
            # init result list and number of server calls
            self.__server_results, self.__call_idx = ([], 0)
        cur_ret = self._call()
        e_time = time.time()
        if self.Meta.server_contact:
            self.log(
                "took %s, (%d of %d ok, %d server contacts [%s])" % (
                    logging_tools.get_diff_time_str(e_time - s_time),
                    len(self.__server_results),
                    self.__call_idx,
                    self.__server_contacts,
                    "ok" if self.__server_contact_ok else "failed"
                ))
            # anything set (from cache or direct) and all server contacts ok (a little bit redundant)
            if (len(self.__server_results) == self.__call_idx and self.__call_idx) or self.__force_store_cache:
                if (self.__server_contacts and self.__server_contact_ok) or self.__force_store_cache:
                    self._store_cache()
        else:
            self.log(
                "took %s" % (
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
        return cur_ret
    def get_arg_template(self, *args, **kwargs):
        return arg_template(self, *args, **kwargs)

class arg_template(dict):
    def __init__(self, s_base, *args, **kwargs):
        dict.__init__(self)
        self.info = args[0]
        if s_base is not None:
            if s_base.__class__.__name__ == "check_command":
                self.__arg_lut, self.__arg_list = s_base.arg_ll
            else:
                self.__arg_lut, self.__arg_list = s_base.s_check.arg_ll
        else:
            self.__arg_lut, self.__arg_list = ({}, [])
        # set defaults
        self.argument_names = sorted(list(set(self.__arg_list) | set(self.__arg_lut.values())))
        for arg_name in self.argument_names:
            dict.__setitem__(self, arg_name, "")
        for key, value in kwargs.iteritems():
            self[key] = value
    def __setitem__(self, key, value):
        l_key = key.lower()
        if l_key.startswith("arg"):
            if l_key.startswith("arg_"):
                key = "arg%d" % (len(self.argument_names) + 1 - int(l_key[4:]))
            if key.upper() not in self.argument_names:
                raise KeyError, "key '%s' not defined in arg_list (%s, %s)" % (
                    key,
                    self.info,
                    ", ".join(self.argument_names)
                )
            else:
                dict.__setitem__(self, key.upper(), value)
        else:
            if key in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut[key].upper(), value)
            elif "-%s" % (key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["-%s" % (key)].upper(), value)
            elif "--%s" % (key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["--%s" % (key)].upper(), value)
            else:
                raise KeyError, "key '%s' not defined in arg_list (%s)" % (
                    key,
                    self.info)

class special_openvpn(special_base):
    class Meta:
        server_contact = True
    def _call(self):
        sc_array = []
        exp_dict = parse_expected()
        if exp_dict.has_key(self.host.name):
            exp_dict = {} # exp_dict[host["name"]]
        else:
            exp_dict = {}
        if not exp_dict:
            # no expected_dict found, try to get the actual config from the server
            srv_result = self.collrelay("openvpn_status")
            # print etree.tostring(srv_result.tree, pretty_print=True)
            if srv_result is not None:
                if "openvpn_instances" in srv_result:
                    ovpn_dict = srv_result["openvpn_instances"]
                    # build exp_dict
                    for inst_name in ovpn_dict:
                        if ovpn_dict[inst_name]["type"] == "server":
                            for c_name in ovpn_dict[inst_name]["dict"]:
                                exp_dict.setdefault(inst_name, {})[c_name] = True
        if exp_dict:
            for inst_name in sorted(exp_dict):
                for peer_name in sorted(exp_dict[inst_name]):
                    sc_array.append(self.get_arg_template("OpenVPN peer %s on %s" % (peer_name, inst_name),
                                                          arg1=inst_name,
                                                          arg2=peer_name))
        if not sc_array:
            sc_array.append(self.get_arg_template("OpenVPN", arg1="ALL", arg2="ALL"))
        return sc_array

class special_supermicro(special_base):
    class Meta:
        server_contact = True
    def _call(self):
        # parameter list
        para_list = ["num_ibqdr", "num_power", "num_gigabit", "num_blade", "num_cmm"]
        para_dict = {}
        for para_name in para_list:
            r_para_name = self.real_parameter_name(para_name)
            try:
                cur_var = device_variable.objects.get(Q(device=self.host) & Q(name=r_para_name))
            except device_variable.DoesNotExist:
                self.log("variable %s does not exist, requesting info from BMC" % (r_para_name), logging_tools.LOG_LEVEL_WARN)
                break
            else:
                para_dict[para_name] = cur_var.get_value()
        if len(para_list) != len(para_dict):
            self.log("updating info from BMC")
            srv_result = self.collrelay("smcipmi", "--ip", self.host.valid_ip, "counter", connect_to_localhost=True)
            # xpath string origins in supermiro_mod, server part (scmipmi_struct)
            r_dict = supermicro_mod.generate_dict(srv_result.xpath(None, ".//ns:output/text()")[0].split("\n"))
            for para_name in para_list:
                r_para_name = self.real_parameter_name(para_name)
                s_name = para_name.split("_", 1)[1]
                if s_name in r_dict:
                    v_val = r_dict[s_name]["present"]
                    self.log("parameter %s: %d" % (para_name, v_val))
                else:
                    v_val = 0
                    self.log("parameter %s: %d (not found in dict)" % (para_name, v_val), logging_tools.LOG_LEVEL_WARN)
                try:
                    cur_var = device_variable.objects.get(Q(device=self.host) & Q(name=r_para_name))
                except device_variable.DoesNotExist:
                    cur_var = device_variable(
                        device=self.host,
                        name=r_para_name,
                        is_public=True,
                        description="Read from BMC",
                        var_type="i",
                        val_int=v_val)
                else:
                    cur_var.set_value(v_val)
                cur_var.save()
                para_dict[para_name] = cur_var.get_value()
        self.log("para_dict: %s" % (", ".join(["%s=%d" % (key, value) for key, value in para_dict.iteritems()])))
        sc_array = []
        sc_array.append(self.get_arg_template("Overview", arg1="counter"))
        for ps_num in xrange(para_dict.get("num_power", 0)):
            sc_array.append(self.get_arg_template(
                "Power supply %2d" % (ps_num + 1),
                arg1="power %d" % (ps_num + 1)
            )
                            )
        for blade_num in xrange(para_dict.get("num_blade", 0)):
            sc_array.append(self.get_arg_template(
                "Blade %2d" % (blade_num + 1),
                arg1="blade %d" % (blade_num + 1)
            )
                            )
        return sc_array

class special_disc_all(special_base):
    def _call(self):
        sc_array = [self.get_arg_template("All partitions", arg3="ALL")]
        return sc_array

class special_disc(special_base):
    def _call(self):
        part_dev = self.host.partdev
        first_disc = None
        part_list = []
        # print self.get_parameter("num_discs", "df", "/dev/sda1")
        # print self.get_parameter("num_discs", ".//ns:load1", "load")
        for part_p in partition.objects.filter(Q(partition_disc__partition_table=self.host.act_partition_table)).select_related(
            "partition_fs").order_by(
                "partition_disc__disc",
                "pnum"):
            if part_p.partition_fs.hexid == "82":
                # swap partiton
                pass
            else:
                act_disc, act_pnum = (part_p.partition_disc.disc, part_p.pnum)
                if not first_disc:
                    first_disc = act_disc
                if act_disc == first_disc and part_dev:
                    act_disc = part_dev
                if "dev/mapper" in act_disc:
                    part_pf = "-part"
                elif "cciss" in act_disc or "ida" in act_disc:
                    part_pf = "p"
                else:
                    part_pf = ""
                if act_pnum:
                    act_part = "%s%s%d" % (act_disc, part_pf, act_pnum)
                else:
                    # handle special case for unpartitioned disc
                    act_part = act_disc
                # which partition to check
                check_part = act_part
                # check for lut_blob
                # lut_blob = None # part_p.get("lut_blob", None)
                # if lut_blob:
                #    lut_blob = process_tools.net_to_sys(lut_blob)
                #    if lut_blob:
                #        if lut_blob.has_key("id"):
                #            scsi_id = [act_id for act_id in lut_blob["id"] if act_id.startswith("scsi")]
                #            if scsi_id:
                #                scsi_id = scsi_id[0]
                #                check_part = "/dev/disk/by-id/%s" % (scsi_id)
                if check_part.startswith("/"):
                    warn_level, crit_level = (
                        part_p.warn_threshold,
                        part_p.crit_threshold)
                    warn_level_str, crit_level_str = (
                        "%d" % (warn_level if warn_level else 85),
                        "%d" % (crit_level if crit_level else 95))
                    if part_p.mountpoint.strip():
                        part_list.append((part_p.mountpoint,
                                          check_part, warn_level_str, crit_level_str))
                else:
                    self.log("Diskcheck on host %s requested an illegal partition %s -> skipped" % (self.host["name"], act_part), logging_tools.LOG_LEVEL_WARN)
        # LVM-partitions
        for lvm_part in lvm_lv.objects.filter(Q(lvm_vg__partition_table=self.host.act_partition_table)).select_related("lvm_vg").order_by("name"):
            if lvm_part.mountpoint:
                warn_level, crit_level = (lvm_part.warn_threshold or 0,
                                          lvm_part.crit_threshold or 0)
                warn_level_str, crit_level_str = (
                    "%d" % (warn_level if warn_level else 85),
                    "%d" % (crit_level if crit_level else 95))
                part_list.append((
                    "%s (LVM)" % (lvm_part.mountpoint),
                    "/dev/mapper/%s-%s" % (lvm_part.lvm_vg.name, lvm_part.name),
                    warn_level_str,
                    crit_level_str))
        # manual setting-dict for df
        sc_array = []
        for info_name, p_name, w_lev, c_lev in part_list:
            self.log("  P: %-40s: %-40s (w: %-5s, c: %-5s)" % (
                info_name,
                p_name,
                w_lev or "N/S",
                c_lev or "N/S"))
            sc_array.append(self.get_arg_template(info_name, arg3=p_name, w=w_lev, c=c_lev))
        return sc_array

class special_net(special_base):
    def _call(self):
        sc_array = []
        eth_check = True if re.match(".*ethtool.*", self.s_check["command_name"]) else False
        virt_check = re.compile("^.*:\S+$")
        self.log("eth_check is %s" % ("on" if eth_check else "off"))
        # never check duplex and stuff for a loopback-device
        if eth_check:
            nd_list = netdevice.objects.exclude(Q(devname='lo')).filter(Q(device=self.host) & Q(netdevice_speed__check_via_ethtool=True)).order_by("devname").select_related("netdevice_speed")
        else:
            nd_list = netdevice.objects.filter(Q(device=self.host) & (Q(devname='lo') | Q(netdevice_speed__check_via_ethtool=False)))
        for net_dev in nd_list:
            if not virt_check.match(net_dev.devname):
                name_with_descr = "%s%s" % (
                    net_dev.devname,
                    " (%s)" % (net_dev.description) if net_dev.description else "")
                cur_temp = self.get_arg_template(
                    name_with_descr,
                    w="%.0f" % (net_dev.netdevice_speed.speed_bps * 0.9),
                    c="%.0f" % (net_dev.netdevice_speed.speed_bps * 0.95),
                    arg_1=net_dev.devname,
                )
                if eth_check:
                    cur_temp["duplex"] = net_dev.netdevice_speed.full_duplex and "full" or "half"
                    cur_temp["s"] = "%d" % (net_dev.netdevice_speed.speed_bps)
                self.log(" - netdevice %s with %s: %s" % (
                    name_with_descr,
                    logging_tools.get_plural("option", len(cur_temp.argument_names)),
                    ", ".join(cur_temp.argument_names)))
                sc_array.append(cur_temp)
                # sc_array.append((name_with_descr, eth_opts))
        return sc_array

class special_libvirt(special_base):
    class Meta:
        server_contact = True
    def _call(self):
        sc_array = []
        srv_result = self.collrelay("domain_overview")
        if srv_result is not None:
            if "domain_overview" in srv_result:
                domain_info = srv_result["domain_overview"]
                if "running" in domain_info and "defined" in domain_info:
                    domain_info = domain_info["running"]
                # build sc_array
                for inst_id in domain_info:
                    d_dict = domain_info[inst_id]
                    sc_array.append(
                        self.get_arg_template(
                            "Domain %s" % (d_dict["name"]),
                            arg1=d_dict["name"])
                    )
        return sc_array

class special_eonstor(special_base):
    class Meta:
        retries = 4
        server_contact = True
    def _call(self):
        sc_array = []
        srv_reply = self.snmprelay(
            "eonstor_get_counter",
        )
        if srv_reply and "eonstor_info" in srv_reply:
            info_dict = srv_reply["eonstor_info"]
            # disks
            for disk_id in sorted(info_dict.get("disc_ids", [])):
                sc_array.append(
                    self.get_arg_template(
                        "Disc %2d" % (disk_id),
                        arg3="eonstor_disc_info",
                        arg4="%d" % (disk_id),
                    )
                )
            # lds
            for ld_id in sorted(info_dict.get("ld_ids", [])):
                sc_array.append(
                    self.get_arg_template(
                        "LD %2d" % (ld_id),
                        arg3="eonstor_ld_info",
                        arg4="%d" % (ld_id)
                    )
                )
            # env_dicts
            for env_dict_name in sorted(info_dict.get("ent_dict", {}).keys()):
                env_dict = info_dict["ent_dict"][env_dict_name]
                for idx in sorted(env_dict.keys()):
                    nag_name = env_dict[idx]
                    add_check = True
                    # get info for certain environment types
                    if env_dict_name in ["ups", "bbu"]:
                        act_com = "eonstor_%s_info" % (env_dict_name)
                        srv_reply = self.snmprelay(
                            act_com,
                            "%d" % (idx)
                        )
                        if srv_reply and "eonstor_info:state" in srv_reply:
                            act_state = int(srv_reply["eonstor_info:state"].text)
                            self.log("state for %s:%d is %d" % (act_com, idx, act_state))
                            if env_dict_name == "ups":
                                # check for inactive psus
                                if act_state & 128:
                                    self.log("disabling psu with idx %d because not present" % (idx),
                                             logging_tools.LOG_LEVEL_ERROR)
                                    add_check = False
                            elif env_dict_name == "bbu":
                                if act_state & 128:
                                    self.log("disabling bbu with idx %d because not present" % (idx),
                                             logging_tools.LOG_LEVEL_ERROR)
                                    add_check = False
                    if add_check:
                        if not nag_name.lower().startswith(env_dict_name):
                            nag_name = "%s %s" % (env_dict_name, nag_name)
                        sc_array.append(
                            self.get_arg_template(
                                nag_name,
                                # not correct, fixme
                                arg3="eonstor_%s_info" % (env_dict_name),
                                arg4="%d" % (idx)
                            )
                        )
        # rewrite sc_array to include community and version
        # sc_array = [(name, ["", ""] + var_list) for name, var_list in sc_array]
        self.log("sc_array has %s" % (logging_tools.get_plural("entry", len(sc_array))))
        return sc_array

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)

