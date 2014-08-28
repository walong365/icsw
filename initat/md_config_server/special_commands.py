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
""" special tasks for md-config-server, should be split into submodules, FIXME """

from django.db.models import Q
from initat.cluster.backbone.models import partition, netdevice, lvm_lv, monitoring_hint, \
    cluster_timezone
from initat.host_monitoring import ipc_comtools
from initat.host_monitoring.modules import supermicro_mod
from lxml.builder import E  # @UnresolvedImport
import datetime
import logging_tools
import process_tools
import re
import time

"""
cache_modes, how to handle to cache for special commands
in case of connection problems always use the cache (if set, of course)
ALWAYS   : always use value from cache, even if empty
DYNAMIC  : use cache only when set and not too old, otherwise try to connect to device
REFRESH  : always try to contact device
"""

CACHE_MODES = ["ALWAYS", "DYNAMIC", "REFRESH"]
DEFAULT_CACHE_MODE = "ALWAYS"


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
        # is active ?
        is_active = True
        # command
        command = ""
        # description
        description = "no description available"

    def __init__(self, build_proc=None, s_check=None, host=None, global_config=None, **kwargs):
        for key in dir(special_base.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(special_base.Meta, key))
        self.Meta.name = self.__class__.__name__.split("_", 1)[1]
        self.ds_name = self.Meta.name
        # print "ds_name=", self.ds_name
        self.cache_mode = kwargs.get("cache_mode", DEFAULT_CACHE_MODE)
        self.build_process = build_proc
        self.s_check = s_check
        self.host = host

    def _store_cache(self):
        self.log("storing cache ({})".format(logging_tools.get_plural("entry", len(self.__hint_list))))
        monitoring_hint.objects.filter(Q(device=self.host) & Q(m_type=self.ds_name)).delete()
        for ch in self.__hint_list:
            ch.save()

    def _load_cache(self):
        self.__cache_created, self.__cache_age, self.__cache_valid = (0, 0, False)
        self.__cache = monitoring_hint.objects.filter(Q(device=self.host) & Q(m_type=self.ds_name))
        # set datasource to cache
        for _entry in self.__cache:
            if _entry.datasource != "c":
                _entry.datasource = "c"
                _entry.save(update_fields=["datasource"])
        self.log(
            "loaded hints ({}) from db".format(
                logging_tools.get_plural("entry", len(self.__cache))
            )
        )
        if self.__cache:
            _now = cluster_timezone.localize(datetime.datetime.now())
            self.__cache_age = max([abs(_now - _entry.changed).total_seconds() for _entry in self.__cache])
            self.__cache_valid = self.__cache_age < self.Meta.cache_timeout

    def _show_cache_info(self):
        if self.__cache:
            self.log(
                "cache is present ({}, age is {}, timeout {}, {})".format(
                    logging_tools.get_plural("entry", len(self.__cache)),
                    logging_tools.get_diff_time_str(self.__cache_age),
                    logging_tools.get_diff_time_str(self.Meta.cache_timeout),
                    "valid" if self.__cache_valid else "invalid",
                )
            )
        else:
            self.log("no cache set")

    def add_persistent_entries(self, hint_list):
        pers_dict = {_hint.key: _hint for _hint in self.__cache if _hint.persistent}
        cache_keys = set([_hint.key for _hint in hint_list])
        missing_keys = set(pers_dict.keys()) - cache_keys
        if missing_keys:
            self.log(
                "add {} to hint_list: {}".format(
                    logging_tools.get_plural("persistent entry", len(missing_keys)),
                    ", ".join(sorted(list(missing_keys))),
                )
            )
            for mis_key in missing_keys:
                _hint = pers_dict[mis_key]
                _hint.datasource = "p"
                _hint.save(update_fields=["datasource"])
                hint_list.append(_hint)

    def cleanup(self):
        self.build_process = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.build_process.mach_log("[sc] {}".format(what), log_level)

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

    def to_hint(self, srv_reply):
        # transforms server reply to monitoring hints
        return []

    def _salt_hints(self, in_list, call_idx):
        for hint in in_list:
            hint.datasource = "s"
            hint.device = self.host
            hint.m_type = self.ds_name
            hint.call_idx = call_idx
        return in_list

    @property
    def call_idx(self):
        # gives current server call number
        return self.__call_idx

    def _call_server(self, command, server_name, *args, **kwargs):
        if not self.Meta.server_contact:
            # not beautifull but working
            self.log("not allowed to make an external call", logging_tools.LOG_LEVEL_CRITICAL)
            return None
        self.log("calling server '{}' for {}, command is '{}', {}, {}".format(
            server_name,
            self.host.valid_ip.ip,
            command,
            "args is '{}'".format(", ".join([str(value) for value in args])) if args else "no arguments",
            ", ".join(["{}='{}'".format(key, str(value)) for key, value in kwargs.iteritems()]) if kwargs else "no kwargs",
        ))
        connect_to_localhost = kwargs.pop("connect_to_localhost", False)
        conn_ip = "127.0.0.1" if connect_to_localhost else self.host.valid_ip.ip
        if not self.__use_cache:
            # contact the server / device
            hint_list = []
            for cur_iter in xrange(self.Meta.retries):
                _result_ok = False
                log_str, log_level = (
                    "iteration {:d} of {:d} (timeout={:d})".format(cur_iter, self.Meta.retries, self.Meta.timeout),
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
                    log_str = "{}, error connecting to '{}' ({}, {}): {}".format(
                        log_str,
                        server_name,
                        conn_ip,
                        command,
                        process_tools.get_except_info()
                    )
                    self.__server_contact_ok = False
                else:
                    srv_error = srv_reply.xpath(".//ns:result[@state != '0']", smart_strings=False)
                    if srv_error:
                        self.__server_contact_ok = False
                        log_str = "{}, got an error ({:d}): {}".format(
                            log_str,
                            int(srv_error[0].attrib["state"]),
                            srv_error[0].attrib["reply"],
                        )
                    else:
                        e_time = time.time()
                        log_str = "{}, got a valid result in {}".format(
                            log_str,
                            logging_tools.get_diff_time_str(e_time - s_time),
                        )
                        _result_ok = True
                        log_level = logging_tools.LOG_LEVEL_OK
                        # salt hints, add call_idx
                        hint_list = self._salt_hints(self.to_hint(srv_reply), self.__call_idx)
                        # as default all hints are used for monitor checks
                        for _entry in hint_list:
                            _entry.check_created = True
                        self.__server_contacts += 1
                        self.__hint_list.extend(hint_list)
                self.log(log_str, log_level)
                if _result_ok:
                    break
                self.log("waiting for {:d} seconds".format(self.Meta.error_wait), logging_tools.LOG_LEVEL_WARN)
                time.sleep(self.Meta.error_wait)
            if hint_list == [] and self.__call_idx == 0 and len(self.__cache):
                # use cache only when first call went wrong and we have something in the cache
                self.__use_cache = True
        if self.__use_cache:
            hint_list = [_entry for _entry in self.__cache if _entry.call_idx == self.__call_idx]
            self.log("take result from cache")
        else:
            # add persistent values
            self.add_persistent_entries(hint_list)
        self.__call_idx += 1
        return hint_list

    def __call__(self):
        s_name = self.__class__.__name__.split("_", 1)[1]
        self.log("starting {} for {}, cache_mode is {}".format(s_name, self.host.name, self.cache_mode))
        s_time = time.time()
        # flag to force store the cache (in case of migration of cache entries from FS to DB), only used internally
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
            self.__hint_list, self.__call_idx = ([], 0)
        cur_ret = self._call()
        e_time = time.time()
        if self.Meta.server_contact and not self.__use_cache:
            self.log(
                "took {}, ({:d} ok, {:d} server contacts [{}], {})".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                    self.__call_idx,
                    self.__server_contacts,
                    "ok" if self.__server_contact_ok else "failed",
                    logging_tools.get_plural("hint", len(self.__hint_list))
                ))
            # anything set (from cache or direct) and all server contacts ok (a little bit redundant)
            if (self.__server_contacts == self.__call_idx and self.__call_idx) or self.__force_store_cache:
                if (self.__server_contacts and self.__server_contact_ok) or self.__force_store_cache:
                    self._store_cache()
        else:
            self.log(
                "took {}".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
        return cur_ret

    def get_arg_template(self, *args, **kwargs):
        return arg_template(self.s_check, *args, is_active=self.Meta.is_active, **kwargs)


class arg_template(dict):
    def __init__(self, s_base, *args, **kwargs):
        dict.__init__(self)
        self._addon_dict = {}
        self.info = args[0]
        self.is_active = kwargs.pop("is_active", True)
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

    @property
    def addon_dict(self):
        return self._addon_dict

    def __setitem__(self, key, value):
        l_key = key.lower()
        if l_key.startswith("arg"):
            if l_key.startswith("arg_"):
                key = "arg{:d}".format(len(self.argument_names) + 1 - int(l_key[4:]))
            if key.upper() not in self.argument_names:
                raise KeyError(
                    "key '{}' not defined in arg_list ({}, {})".format(
                        key,
                        self.info,
                        ", ".join(self.argument_names)
                    )
                )
            else:
                dict.__setitem__(self, key.upper(), value)
        elif key.startswith("_"):
            self._addon_dict[key] = value
        else:
            if key in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut[key].upper(), value)
            elif "-{}".format(key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["-{}".format(key)].upper(), value)
            elif "--{}".format(key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["--{}".format(key)].upper(), value)
            else:
                raise KeyError(
                    "key '{}' not defined in arg_list ({})".format(
                        key,
                        self.info
                    )
                )


class special_openvpn(special_base):
    class Meta:
        server_contact = True
        command = "$USER2$ -m $HOSTADDRESS$ openvpn_status -i $ARG1$ -p $ARG2$"
        description = "checks for running OpenVPN instances"

    def to_hint(self, srv_reply):
        _hints = []
        if "openvpn_instances" in srv_reply:
            ovpn_dict = srv_reply["openvpn_instances"]
            for inst_name in ovpn_dict:
                if ovpn_dict[inst_name]["type"] == "server":
                    for c_name in ovpn_dict[inst_name]["dict"]:
                        _hints.append(
                            monitoring_hint(
                                key="{}|{}".format(inst_name, c_name),
                                v_type="s",
                                value_string="used",
                                info="Client {} on instance {}".format(c_name, inst_name),
                                persistent=True,
                                )
                            )
        return _hints

    def _call(self):
        sc_array = []
        # no expected_dict found, try to get the actual config from the server
        hint_list = self.collrelay("openvpn_status")
        ip_dict = {}
        for hint in hint_list:
            inst_name, peer_name = hint.key.split("|")
            ip_dict.setdefault(inst_name, []).append(peer_name)
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=inst_name,
                    arg2=peer_name
                )
            )
        for inst_name in sorted(ip_dict.keys()):
            _clients = ip_dict[inst_name]
            if len(_clients) > 1:
                sc_array.append(
                    self.get_arg_template(
                        "OpenVPN clients for {} ({:d})".format(inst_name, len(_clients)),
                        arg1=inst_name,
                        arg2=",".join(_clients),
                    )
                )
        if not sc_array:
            sc_array.append(self.get_arg_template("OpenVPN", arg1="ALL", arg2="ALL"))
        return sc_array


class special_supermicro(special_base):
    class Meta:
        server_contact = True
        command = "$USER2$ -m 127.0.0.1 smcipmi --ip=$HOSTADDRESS$ --user=${ARG1:SMC_USER:ADMIN} --passwd=${ARG2:SMC_PASSWD:ADMIN} $ARG3$"
        description = "queries IPMI Bladecenters via the collserver on the localhost"

    def to_hint(self, srv_reply):
        r_dict = supermicro_mod.generate_dict(srv_reply.xpath(".//ns:output/text()", smart_strings=False)[0].split("\n"))
        _hints = []
        for m_key in sorted(r_dict):
            _struct = r_dict[m_key]
            for e_key in sorted([_key for _key in _struct.iterkeys() if type(_key) in [int]]):
                _hints.append(
                    monitoring_hint(
                        key="{}.{:d}".format(m_key, e_key),
                        v_type="s",
                        value_string="present",
                        info="{} {:d}".format(_struct["info"], e_key),
                    )
                )
        return _hints

    def _call(self):
        user_name = self.host.dev_variables.get("SMC_USER", "ADMIN")
        cur_pwd = self.host.dev_variables.get("SMC_PASSWD", "ADMIN")
        hint_list = self.collrelay(
            "smcipmi",
            "--ip={}".format(self.host.valid_ip.ip),
            "--user={}".format(user_name),
            "--passwd={}".format(cur_pwd),
            "counter",
            connect_to_localhost=True
        )
        sc_array = []
        sc_array.append(
            self.get_arg_template(
                "Overview",
                arg1=user_name,
                arg2=cur_pwd,
                arg3="counter",
            )
        )
        for hint in hint_list:
            inst_name, inst_id = hint.key.split(".")
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=user_name,
                    arg2=cur_pwd,
                    arg3="{} {}".format(inst_name, inst_id),
                )
            )
        return sc_array


class special_disc_all(special_base):
    class Meta:
        command = "$USER2$ -m $HOSTADDRESS$ df -w ${ARG1:85} -c ${ARG2:95} $ARG3$"
        description = "queries the collserver on the target system for the partition with the lowest space"

    def _call(self):
        sc_array = [self.get_arg_template("All partitions", arg3="ALL")]
        return sc_array


class special_disc(special_base):
    class Meta:
        command = "$USER2$ -m $HOSTADDRESS$ df -w ${ARG1:85} -c ${ARG2:95} $ARG3$"
        description = "queries the partition on the target system via collserver"

    def _call(self):
        part_dev = self.host.partdev
        first_disc = None
        part_list = []
        for part_p in partition.objects.filter(
            Q(partition_disc__partition_table=self.host.act_partition_table)
            ).select_related(
                "partition_fs"
            ).prefetch_related(
                "partition_disc"
            ).order_by(
                "partition_disc__disc",
                "pnum"):
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
                act_part = "{}{}{}".format(act_disc, part_pf, "{:d}".format(act_pnum) if act_pnum else "")
            else:
                # handle special case for unpartitioned disc
                act_part = act_disc
            if part_p.partition_fs.hexid == "82":
                # swap partiton
                self.log("ignoring {} (is swap)".format(act_part))
            else:
                # which partition to check
                check_part = act_part
                if check_part.startswith("/"):
                    warn_level, crit_level = (
                        part_p.warn_threshold,
                        part_p.crit_threshold)
                    warn_level_str, crit_level_str = (
                        "{:d}".format(warn_level if warn_level else 85),
                        "{:d}".format(crit_level if crit_level else 95))
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
                    "{:d}".format(warn_level if warn_level else 85),
                    "{:d}".format(crit_level if crit_level else 95))
                part_list.append((
                    "{} (LVM)".format(lvm_part.mountpoint),
                    "/dev/mapper/{}-{}".format(lvm_part.lvm_vg.name, lvm_part.name),
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
    class Meta:
        command = "$USER2$ -m $HOSTADDRESS$ net --duplex $ARG1$ -s $ARG2$ -w $ARG3$ -c $ARG4$ $ARG5$"
        description = "queries all configured network devices"

    def _call(self):
        sc_array = []
        virt_check = re.compile("^.*:\S+$")
        # never check duplex and stuff for a loopback-device
        nd_list = netdevice.objects.filter(
            Q(device=self.host) &
            Q(enabled=True)).select_related("netdevice_speed")
        for net_dev in nd_list:
            if not virt_check.match(net_dev.devname):
                name_with_descr = "{}{}".format(
                    net_dev.devname,
                    " ({})".format(net_dev.description) if net_dev.description else "")
                cur_temp = self.get_arg_template(
                    name_with_descr,
                    w="{:.0f}".format(net_dev.netdevice_speed.speed_bps * 0.9),
                    c="{:.0f}".format(net_dev.netdevice_speed.speed_bps * 0.95),
                    arg_1=net_dev.devname,
                )
                if net_dev.netdevice_speed.check_via_ethtool and net_dev.devname != "lo":
                    cur_temp["duplex"] = net_dev.netdevice_speed.full_duplex and "full" or "half"
                    cur_temp["s"] = "{:d}".format(net_dev.netdevice_speed.speed_bps)
                else:
                    cur_temp["duplex"] = "-"
                    cur_temp["s"] = "-"
                self.log(" - netdevice {} with {}: {}".format(
                    name_with_descr,
                    logging_tools.get_plural("option", len(cur_temp.argument_names)),
                    ", ".join(cur_temp.argument_names)))
                sc_array.append(cur_temp)
                # sc_array.append((name_with_descr, eth_opts))
        return sc_array


class special_libvirt(special_base):
    class Meta:
        server_contact = True
        command = "$USER2$ -m $HOSTADDRESS$ domain_status $ARG1$"
        description = "checks running virtual machines on the target host via libvirt"

    def to_hint(self, srv_reply):
        _hints = []
        if srv_reply is not None:
            if "domain_overview" in srv_reply:
                domain_info = srv_reply["domain_overview"]
                if "running" in domain_info and "defined" in domain_info:
                    domain_info = domain_info["running"]
                for _d_idx, d_dict in domain_info.iteritems():
                    new_hint = monitoring_hint(
                        key=d_dict["name"],
                        v_type="s",
                        info="Domain {}".format(d_dict["name"]),
                        value_string="running",
                    )
                    _hints.append(new_hint)
        return _hints

    def _call(self):
        sc_array = []
        for hint in self.collrelay("domain_overview"):
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=hint.key,
                )
            )
        return sc_array


class special_ipmi(special_base):
    class Meta:
        server_contact = True
        command = "$USER2$ -m $HOSTADDRESS$ ipmi_sensor --lowern=${ARG1:na} --lowerc=${ARG2:na} " \
            "--lowerw=${ARG3:na} --upperw=${ARG4:na} --upperc=${ARG5:na} --uppern=${ARG6:na} $ARG7$"
        description = "queries the IPMI sensors of the underlying IPMI interface of the target device"

    def to_hint(self, srv_reply):
        _hints = []
        if srv_reply is not None:
            if "list:sensor_list" in srv_reply:
                for sensor in srv_reply["list:sensor_list"]:
                    lim_dict = {l_key: sensor.attrib[key] for l_key, key in [
                        ("lower_warn", "limit_lw"),
                        ("lower_crit", "limit_lc"),
                        ("upper_warn", "limit_uw"),
                        ("upper_crit", "limit_uc")] if key in sensor.attrib}
                    new_hint = monitoring_hint(
                        key=sensor.attrib["key"],
                        v_type="f",
                        info=sensor.attrib["info"],
                    )
                    new_hint.update_limits(0.0, lim_dict)
                    _hints.append(new_hint)
        return _hints

    def _call(self):
        sc_array = []
        for hint in self.collrelay("ipmi_sensor"):
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1="na",
                    arg2=hint.get_limit("lower_crit", "na"),
                    arg3=hint.get_limit("lower_warn", "na"),
                    arg4=hint.get_limit("upper_warn", "na"),
                    arg5=hint.get_limit("upper_crit", "na"),
                    arg6="na",
                    arg7=hint.key,
                )
            )
        return sc_array


class special_ipmi_ext(special_base):
    class Meta:
        command = ""
        is_active = False
        description = "queries the IPMI sensors of the IPMI interface directly (not via the target host)"

    def _call(self):
        sc_array = []
        for ipmi_ext in monitoring_hint.objects.filter(
            Q(device=self.host) & Q(m_type="ipmi")
        ):
            new_at = self.get_arg_template(
                ipmi_ext.info,
                _monitoring_hint=ipmi_ext.pk,
            )
            sc_array.append(new_at)
            if not ipmi_ext.check_created:
                ipmi_ext.check_created = True
                ipmi_ext.save(update_fields=["check_created"])
        return sc_array


class special_eonstor(special_base):
    class Meta:
        retries = 2
        server_contact = True
        command = "$USER3$ -m $HOSTADDRESS$ -C ${ARG1:SNMP_COMMUNITY:public} -V ${ARG2:SNMP_VERSION:2} $ARG3$ $ARG4$"
        description = "checks the eonstore disc chassis via SNMP"

    def to_hint(self, srv_reply):
        _hints = []
        if srv_reply is not None:
            if self.call_idx == 0:
                if "eonstor_info" in srv_reply:
                    info_dict = srv_reply["eonstor_info"]
                    self.info_dict = info_dict
                    # disks
                    for disk_id in sorted(info_dict.get("disc_ids", [])):
                        _hints.append(self._get_env_check("Disc {:2d}".format(disk_id), "eonstor_disc_info", disk_id))
                    # lds
                    for ld_id in sorted(info_dict.get("ld_ids", [])):
                        _hints.append(self._get_env_check("Logical Drive {:2d}".format(ld_id), "eonstor_ld_info", ld_id))
                    # env_dicts
                    for env_dict_name in sorted(info_dict.get("ent_dict", {}).keys()):
                        if env_dict_name not in ["ups", "bbu"]:
                            env_dict = info_dict["ent_dict"][env_dict_name]
                            for idx in sorted(env_dict.keys()):
                                _hints.append(self._get_env_check(env_dict[idx], "eonstor_{}_info".format(env_dict_name), idx))
            else:
                if "eonstor_info:state" in srv_reply:
                    _com = srv_reply["*command"]
                    act_state = int(srv_reply["eonstor_info:state"].text)
                    self.log(
                        "state for {} ({}) is {:d}".format(
                            _com,
                            srv_reply["*arg_list"],
                            act_state
                        )
                    )
                    idx = int(srv_reply["*arg_list"])
                    env_dict_name = _com.split("_")[1]
                    if env_dict_name == "ups" and act_state & 128:
                        self.log("disabling psu because not present",
                                 logging_tools.LOG_LEVEL_ERROR)
                    elif env_dict_name == " bbu" and act_state & 128:
                        self.log("disabling bbu because not present",
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        _hints.append(self._get_env_check(self.info_dict["ent_dict"][env_dict_name][idx], "eonstor_{}_info".format(env_dict_name), idx))
        return _hints

    def _get_env_check(self, info, key, idx):
        return monitoring_hint(
            key=key,
            v_type="i",
            value_int=idx,
            info=info,
        )

    def _call(self):
        self.info_dict = {}
        hints = self.snmprelay(
            "eonstor_get_counter",
        )
        if self.info_dict:
            info_dict = self.info_dict
            for env_dict_name in sorted([_entry for _entry in info_dict.get("ent_dict", {}) if _entry in ["ups", "bbu"]]):
                env_dict = info_dict["ent_dict"][env_dict_name]
                for idx in sorted(env_dict.keys()):
                    hints.extend(
                        self.snmprelay(
                            "eonstor_{}_info".format(env_dict_name),
                            "{:d}".format(idx)
                        )
                    )
        sc_array = []
        for hint in hints:
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=self.host.dev_variables["SNMP_READ_COMMUNITY"],
                    arg2=self.host.dev_variables["SNMP_VERSION"],
                    arg3=hint.key,
                    arg4="{:d}".format(hint.value_int),
                )
            )
        self.log("sc_array has %s" % (logging_tools.get_plural("entry", len(sc_array))))
        return sc_array
