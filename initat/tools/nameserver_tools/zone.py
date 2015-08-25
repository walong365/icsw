#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009,2012-2015 Andreas Lang-Nevyjel
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
""" generates zonefiles for nsX.init.at """

import os
import time
import tempfile
import shutil
import commands
import pwd
import json
import stat

from initat.tools import logging_tools, ipvx_tools

from .functions import make_qualified, make_unqualified, to_idna
from .network import Network

A_RECORD = "{:<24s} IN A {}"
NS_RECORD = "{:<24s} IN NS {{}}".format("")
NSS_RECORD = "{:<24s} IN NS {}"
MX_RECORD = "{:<24s} IN MX {{:<4d}} {{}}".format("")
CNAME_RECORD = "{:<24s} IN CNAME {}"
SPF_RECORD = "{:<24s} IN SPF \"{{}}\"".format("")
TXT_RECORD = "{:<24s} IN TXT \"{{}}\"".format("")


class Zone(object):
    zones = []

    class Meta:
        # primary server
        primary = []
        secondary = []
        nameservers = []
        # mx -> ip
        mx_records = {}
        cname_records = []
        forward_to = []

    def __init__(self, name, *records, **kwargs):
        for _key in dir(Zone.Meta):
            if not hasattr(self.Meta, _key):
                setattr(self.Meta, _key, getattr(Zone.Meta, _key))
        Zone.zones.append(self)
        self.name = name
        self.origin = name
        self.spf_record = None
        self.__qname = make_qualified(self.name)
        self.__uname = make_unqualified(self.name)
        self.values = {
            "serial": time.strftime("%y%m%d%H%M"),
            "refresh": "1H",
            "retry": "15M",
            "expiry": kwargs.get("expiry", "1W"),
            "minimum": "1H"
        }
        self.records = list(records)
        self.cname_records = list(kwargs.get("cname", []))
        self.public_empty = True
        self.private_empty = True

    def get_header(self):
        content = [
            "$ORIGIN {}".format(make_qualified(to_idna(self.origin))),
            "$TTL 1H",
            "@ IN SOA {} {} (".format(
                make_qualified(self.Meta.primary[0].name),
                Zone.opts.creator,
            )
        ]
        content.extend(
            [
                "{} {:<12s} ; {}".format(
                    " " * 24,
                    self.values[key],
                    key
                ) for key in ["serial", "refresh", "retry", "expiry", "minimum"]
            ] + [
                ")"
            ]
        )
        content.extend(
            [
                NS_RECORD.format(make_qualified(ns.name)) for ns in self.Meta.nameservers
            ]
        )
        return content

    def generate(self):
        self.generate_zone(True)
        self.generate_zone(False)
        self.create_master_slave_content()

    def generate_zone(self, private):
        content = self.get_header()
        content.extend(
            [
                MX_RECORD.format(pri, make_qualified(name)) for name, pri in self.Meta.mx_records.iteritems()
            ]
        )
        if self.spf_record:
            # deprecated
            # content.append(SPF_RECORD.format(self.spf_record))
            content.append(TXT_RECORD.format(self.spf_record))
        used_names = []
        if self.records:
            fwd_domains = []
            setattr(self, "{}_empty".format("private" if private else "public"), False)
            [_h.fix_names(self) for _h in self.records]
            for _h in self.filter(self.records, private):
                content.append(A_RECORD.format(to_idna(_h.short_name), _h.get_ip(private)))
                used_names.append(_h.name.split(".")[0])
                if _h.forward_domain:
                    fwd_domains.append((_h.forward_domain, _h))
            for _fwd in sorted(fwd_domains):
                content.append(NSS_RECORD.format(make_qualified(_fwd[0]), make_qualified(_fwd[1].long_name)))
            [Zone.feed_host(_host, self) for _host in self.records]
        if self.cname_records:
            cname_dict = {src: dst for src, dst in self.cname_records}
            _cnames_consumed = set()
            _iter = True
            while _iter:
                _iter = False
                for _src, _dst in cname_dict.iteritems():
                    if _dst in used_names and _src not in _cnames_consumed:
                        _cnames_consumed.add(_src)
                        used_names.append(_src)
                        _iter = True
                        content.append(
                            CNAME_RECORD.format(to_idna(_src), to_idna(_dst))
                        )
        _target = "{}_content".format("private" if private else "public")
        setattr(self, _target, content)

    def zone_file_name(self, private):
        return "dyn/{}_{}.zone".format(
            to_idna(self.__uname),
            "private" if private else "public",
        )

    def filter(self, in_list, private):
        # return filtered list
        if private:
            r_list = [entry for entry in in_list if entry.create_record]
        else:
            r_list = []
            for _entry in in_list:
                if _entry.public_ip:
                    # always add
                    r_list.append(_entry)
                else:
                    if not _entry.private:
                        r_list.append(_entry)
        return sorted(r_list, lambda x, y: cmp(x.name, y.name))

    def create_master_slave_content(self):
        self.split_zone = self.public_content != self.private_content
        if self.split_zone:
            # generate private and public zone
            _iter_list = [True, False]
        else:
            # only generate public zone
            _iter_list = [False]
        for private in _iter_list:
            _pf = "private" if private else "public"
            _npf = "private" if not private else "public"
            if self.Meta.forward_to:
                # create forward zone
                p_content = [
                    "zone \"{}\" IN {{".format(to_idna(self.origin)),
                    "    type forward;",
                    "    forwarders {{ {}; }};".format("; ".join(self.Meta.forward_to)),
                    "    forward only;",
                    "};",
                    "",
                ]
                s_content = p_content
            else:
                p_content = [
                    "zone \"{}\" IN {{".format(to_idna(self.origin)),
                    "    file \"{}\";".format(self.zone_file_name(private)),
                    "    type master;",
                    "    notify yes;",
                    "    allow-update { none; } ;",
                    "    allow-transfer {{ key {}-key; !key {}-key; {}; }};".format(
                        _pf,
                        _npf,
                        "; ".join([str(_s.ip) for _s in self.Meta.secondary]),
                    ),
                    "    also-notify {{ {} ; }};".format("; ".join([str(_s.ip) for _s in self.Meta.secondary])),
                    "};",
                    "",
                ]
                s_content = [
                    "zone \"{}\" IN {{".format(to_idna(self.origin)),
                    "    file \"{}\";".format(self.zone_file_name(private)),
                    "    type slave;",
                    "    masters {{ {}; }};".format("; ".join([str(_p.ip) for _p in self.Meta.primary])),
                    "    allow-transfer { none; };",
                    "    notify no;",
                    "};",
                    "",
                ]
            setattr(self, "{}_master_entry".format(_pf), p_content)
            setattr(self, "{}_slave_entry".format(_pf), s_content)

    @staticmethod
    def setup(opts):
        Zone.opts = opts
        Zone.zones = []

    @staticmethod
    def generate_all():
        [zone.generate() for zone in Zone.zones]
        [net.create_zone() for net in Network.networks if net.records]

    @staticmethod
    def show_all():
        print("{} defined:".format(logging_tools.get_plural("Zone", len(Zone.zones))))
        for _name, _zone in sorted([(_zone.name, _zone) for _zone in Zone.zones]):
            print(
                u"   {} ({})".format(
                    _name,
                    logging_tools.get_plural("A record", len(_zone.records)),
                )
            )
            print "\n".join(_zone.content_private)
            print "\n".join(_zone.content_public)
            print "\n".join(_zone.master_entry)
            print "\n".join(_zone.slave_entry)

    @staticmethod
    def feed_host(host, zone):
        if not host.is_special:
            [_nw.feed_host(host, zone) for _nw in Network.networks]

    @staticmethod
    def create_keys():
        _key_dir = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, Zone.opts.key_dir)
        if not os.path.isdir(_key_dir):
            os.makedirs(_key_dir)
        os.chmod(_key_dir, stat.S_IRWXU)
        _res_name = os.path.join(_key_dir, "info")
        if not os.path.exists(_res_name):
            _res_dict = {}
            for _key in ["public", "private"]:
                _res_dict[_key] = commands.getoutput(
                    "/usr/sbin/dnssec-keygen -v 10 -a HMAC-MD5 -n HOST -b 128 -r /dev/urandom -K {} {}".format(
                        _key_dir,
                        _key,
                    )
                ).strip()
            file(_res_name, "w").write(json.dumps(_res_dict))
        key_dict = {}
        for _key, _value in json.loads(file(_res_name, "r").read()).iteritems():
            for _t in ["key", "private"]:
                _content = file(os.path.join(_key_dir, "{}.{}".format(_value, _t)), "r").read()
                key_dict.setdefault(_key, {})[_t] = {
                    "content": _content,
                    # not correct for private
                    "secret": _content.strip().split()[-1],
                }
        # import pprint
        # pprint.pprint(key_dict)
        return key_dict

    @staticmethod
    def create_files():
        key_dict = Zone.create_keys()
        if Zone.opts.tmpdir:
            _create_dir = Zone.opts.tmpdir
            if not os.path.exists(_create_dir):
                os.mkdir(_create_dir)
            for _entry in os.listdir(_create_dir):
                shutil.rmtree(os.path.join(_create_dir, _entry))
        else:
            _create_dir = tempfile.mkdtemp()
        print("Creating files in {}".format(_create_dir))
        try:
            Zone.write_files(_create_dir, key_dict)
            if Zone.opts.deploy:
                Zone.deploy(_create_dir)
        finally:
            if Zone.opts.tmpdir:
                print("Contents are now in {}".format(_create_dir))
            else:
                print("Removing tempdir...")
                shutil.rmtree(_create_dir)

    @staticmethod
    def write_files(create_dir, key_dict):
        _zone_dir = os.path.join(create_dir, "zones")
        os.makedirs(os.path.join(_zone_dir, "dyn"))
        _conf_dir = os.path.join(create_dir, "conf")
        os.makedirs(_conf_dir)
        num_files = 0
        for master in [True, False]:
            _btype = "master" if master else "slave"
            _z_content = [
                "key \"public-key\" {",
                "    algorithm hmac-md5;",
                "    secret \"{}\";".format(key_dict["public"]["key"]["secret"]),
                "};",
                "",
                "key \"private-key\" {",
                "    algorithm hmac-md5;",
                "    secret \"{}\";".format(key_dict["private"]["key"]["secret"]),
                "};",
                "",
            ]
            for private in [True, False]:
                _pf = "private" if private else "public"
                _z_content.extend(
                    [
                        "view \"{}\" {{".format(_pf),
                    ]
                )
                if master:
                    _z_content.extend(
                        sum(
                            [
                                [
                                    "    server {} {{".format(_srv.ip),
                                    "        keys {}-key;".format(_pf),
                                    "        transfer-format many-answers;".format(_pf),
                                    "    };",
                                ] for _srv in Zone.Meta.secondary
                            ],
                            []
                        )
                    )
                else:
                    _z_content.extend(
                        sum(
                            [
                                [
                                    "    server {} {{".format(_srv.ip),
                                    "        keys {}-key;".format(_pf),
                                    "    };",
                                ] for _srv in Zone.Meta.primary
                            ],
                            []
                        )
                    )
                if private:
                    _addr_list = "; ".join([net.get_src_mask() for net in Network.networks])
                    _z_content.extend(
                        [
                            "    match-clients {{ key private-key; !key public-key; {}; }};".format(_addr_list),
                            "    recursion yes;",
                            "    allow-recursion {{ {}; }};".format(_addr_list),
                        ]
                    )
                else:
                    _z_content.extend(
                        [
                            "    match-clients { key public-key; !key private-key; 0.0.0.0/0; };",
                        ]
                    )
                _z_content.extend(
                    [
                        "    {}".format(_line) for _line in [
                            "zone \".\" in {",
                            "    type hint;",
                            "    file \"root.hint\";",
                            "};",
                            "",
                            "zone \"localhost\" in {",
                            "    type master;",
                            "    file \"localhost.zone\";",
                            "};",
                            "",
                            "zone \"0.0.127.in-addr.arpa\" in {",
                            "    type master;",
                            "    file \"127.0.0.zone\";",
                            "};",
                            "",
                            "zone \"0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa\" IN {",
                            "    type master;",
                            "    file \"127.0.0.zone\";",
                            "};",
                            "",
                        ]
                    ]
                )
                # forward zones
                _fwd_zones = [_zn for _zn in Zone.zones if _zn.Meta.forward_to]
                for _fwd_zone in _fwd_zones:
                    _z_content.extend(
                        [
                            "    {}".format(
                                _line
                            ) for _line in sum(
                                [
                                    getattr(
                                        _zn, "{}_{}_entry".format(
                                            _pf if _zn.split_zone else "public", _btype
                                        )
                                    ) for _zn in _fwd_zones
                                ], []
                            )
                        ]
                    )

                # resolve zones
                _z_content.extend(
                    [
                        "    {}".format(
                            _line
                        ) for _line in sum(
                            [
                                getattr(
                                    _zn, "{}_{}_entry".format(
                                        _pf if _zn.split_zone else "public", _btype
                                    )
                                ) for _zn in Zone.zones if not getattr(
                                    _zn,
                                    "{}_empty".format(
                                        _pf if _zn.split_zone else "public"
                                    )
                                )
                            ], []
                        )
                    ]
                )
                _z_content.extend(
                    [
                        "};",
                    ]
                )
                if _btype == "master":
                    for zone in Zone.zones:
                        if not zone.split_zone and private:
                            # do not write private zonefile for uniqe (private == public) zones
                            continue
                        if getattr(zone, "{}_empty".format(_pf)):
                            # do not write empty zones
                            continue
                        num_files += 1
                        file(
                            os.path.join(
                                _zone_dir,
                                zone.zone_file_name(private)
                            ),
                            "w"
                        ).write(
                            "\n".join(getattr(zone, "{}_content".format(_pf)) + [""])
                        )
                        # uid, gid = pwd.getpwnam("named")[2:4]
                        # os.chown(dest_file, uid, gid)
            file(os.path.join(_conf_dir, "{}_zones".format(_btype)), "w").write("\n".join(_z_content))
            num_files += 1
        print("Wrote {}.".format(logging_tools.get_plural("file", num_files)))

    @staticmethod
    def call_command(com):
        if Zone.opts.dryrun:
            print("[DR] {}".format(com))
            _stat, _out = (0, "dryrun")
        else:
            _stat, _out = commands.getstatusoutput(com)
            print("command '{}' gave ({:d}): {}".format(com, _stat, _out))
        return _stat, _out

    @staticmethod
    def deploy(create_dir):
        d_map = {}
        if Zone.opts.deploy_map:
            for _entry in Zone.opts.deploy_map.strip().split(","):
                _src_ip, _dst_ip = _entry.strip().split(":")
                d_map[ipvx_tools.ipv4(_src_ip)] = ipvx_tools.ipv4(_dst_ip)
        for _entry in Zone.Meta.nameservers:
            _entry.deploy_ip = d_map.get(_entry.ip, _entry.ip)
        print(
            "Deploying to {}: {}".format(
                logging_tools.get_plural("Nameserver", len(Zone.Meta.nameservers)),
                ", ".join(
                    [
                        unicode(_entry) for _entry in Zone.Meta.nameservers
                    ]
                ),
            )
        )
        _dyn_dir = os.path.join(Zone.opts.named_run_dir, "dyn")
        _zone_file = os.path.join(Zone.opts.named_conf_dir, "zones")
        _zone_src_dir = os.path.join(create_dir, "zones", "dyn")
        for _srv in Zone.Meta.nameservers:
            s_time = time.time()
            print("")
            _local = _srv.name.split(".")[0] == Zone.opts.hostname
            _master = _srv.name in [_entry.name for _entry in Zone.Meta.primary]
            print(
                "... to {} ({} {})".format(
                    _srv.name,
                    "local" if _local else "remote",
                    "master" if _master else "slave",
                )
            )
            if _local:
                # local deploy
                shutil.copyfile(
                    os.path.join(create_dir, "conf", "{}_zones".format("master" if _master else "slave")),
                    _zone_file,
                )
                os.chown(_zone_file, Zone.opts.uid, Zone.opts.gid)
                if os.path.isdir(_dyn_dir):
                    shutil.rmtree(_dyn_dir)
                os.mkdir(_dyn_dir)
                os.chown(_dyn_dir, Zone.opts.uid, Zone.opts.gid)
                if _master:
                    # copy zone files
                    for _entry in os.listdir(_zone_src_dir):
                        _dst = os.path.join(_dyn_dir, _entry)
                        shutil.copyfile(
                            os.path.join(_zone_src_dir, _entry),
                            _dst,
                        )
                        os.chown(_dst, Zone.opts.uid, Zone.opts.gid)
            else:
                # remote deploy
                _cmd_list = [
                    (
                        os.path.join(create_dir, "conf", "{}_zones".format("master" if _master else "slave")),
                        _zone_file,
                    ),
                    "chown {:d}:{:d} {}".format(
                        Zone.opts.uid,
                        Zone.opts.gid,
                        _zone_file,
                    ),
                ]
                if Zone.opts.restart:
                    _cmd_list.extend(
                        [
                            "rm -rf {}".format(
                                _dyn_dir,
                            ),
                            "mkdir {}".format(
                                _dyn_dir,
                            ),
                            "chown -R {:d}:{:d} {}".format(
                                Zone.opts.uid,
                                Zone.opts.gid,
                                _dyn_dir,
                            )
                        ]
                    )
                if _master:
                    _cmd_list.extend(
                        [
                            (
                                os.path.join(create_dir, "zones", "dyn", "*"),
                                _dyn_dir,
                                "-pr",
                            ),
                            "chown {:d}:{:d} {}/*".format(
                                Zone.opts.uid,
                                Zone.opts.gid,
                                _dyn_dir,
                            )
                        ]
                    )
                print("{}".format(logging_tools.get_plural("remote command", len(_cmd_list))))
                for _cmd in _cmd_list:
                    if type(_cmd) is tuple:
                        # copy
                        if len(_cmd) == 3:
                            _opts = _cmd[2]
                        else:
                            _opts = "-p"
                        _rcom = "scp {} {} root@{}:{}".format(
                            _opts,
                            _cmd[0],
                            _srv.deploy_ip,
                            _cmd[1]
                        )
                    else:
                        # command
                        _rcom = "ssh root@{} {}".format(
                            _srv.deploy_ip,
                            _cmd,
                        )
                    _stat, _out = Zone.call_command(_rcom)
            e_time = time.time()
            print("deployment took {}".format(logging_tools.get_diff_time_str(e_time - s_time)))
            print("")
        # reload / restart nameservers
        _mode = "restart" if Zone.opts.restart else "reload"
        for _is_master in [True, False]:
            for _srv in Zone.Meta.nameservers:
                _local = _srv.name.split(".")[0] == Zone.opts.hostname
                _master = _srv.name in [_entry.name for _entry in Zone.Meta.primary]
                if _master == _is_master:
                    if _local:
                        print("{}ing local {} {}".format(_mode, "master" if _master else "slave", unicode(_srv)))
                        Zone.call_command("/etc/init.d/named {}".format(_mode))
                    else:
                        print("{}ing remote {} {}".format(_mode, "master" if _master else "slave", unicode(_srv)))
                        Zone.call_command("ssh root@{} /etc/init.d/named {}".format(_srv.deploy_ip, _mode))
        print("")
