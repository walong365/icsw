# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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

from initat.host_monitoring import limits, hm_classes
import commands
import datetime
import glob
import logging_tools
import os
import process_tools
import re
import shutil
import tempfile
import time

OPENVPN_DIR = "/etc/openvpn"


class net_speed(object):
    def __init__(self):
        self.__last_update = None
        self.__act_rx, self.__act_tx = (0., 0.)

    def _get_value(self, diff_val, diff_time):
        val = max(0, min(10000000., diff_val / diff_time))
        return val

    def feed(self, rx, tx):
        act_time = time.time()
        last_update = self.__last_update
        self.__last_update = act_time
        prev_rx, prev_tx = (self.__act_rx,
                            self.__act_tx)
        # store
        self.__act_rx, self.__act_tx = (rx, tx)
        if last_update:
            diff_time = max(1, abs(last_update - self.__last_update))
            return (self._get_value(self.__act_rx - prev_rx, diff_time),
                    self._get_value(self.__act_tx - prev_tx, diff_time))
        else:
            return (0., 0.)


class _general(hm_classes.hm_module):
    def __init__(self, *args, **kwargs):
        hm_classes.hm_module.__init__(self, *args, **kwargs)
        # instance dict
        self.__inst_dict = {}

    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning(u"cannot execute {} ({:d}): {}".format(com, stat, out))
            out = ""
        return out.split("\n")

    def init_machine_vector(self, mv):
        # register entries
        self.__base_mv_registered = False
        self.__client_dict = {}
        self.__last_status_update = None

    def update_machine_vector(self, mv):
        self.update_status()
        ovpn_keys = self.keys()
        num_total = len(ovpn_keys)
        if num_total and not self.__base_mv_registered:
            self.__base_mv_registered = True
            mv.register_entry("ovpn.total", 0, "Number of OpenVPN Instances")
            mv.register_entry("ovpn.operational", 0, "Number of OpenVPN Instances operational")
            mv.register_entry("ovpn.offline", 0, "Number of OpenVPN Instances offline")
        if self.__base_mv_registered:
            num_online = len([True for key in ovpn_keys if self[key].state])
            num_offline = num_total - num_online
            mv["ovpn.total"] = num_total
            mv["ovpn.operational"] = num_online
            mv["ovpn.offline"] = num_offline
        for ovpn_inst in [self[key] for key in ovpn_keys if self[key].ovpn_type == "server"]:
            ovpn_name = ovpn_inst.name.split(".")[0]
            clients = ovpn_inst.keys()
            if not ovpn_inst.mv_registered:
                ovpn_inst.mv_registered = True
                self.__client_dict[ovpn_name] = {}
                mv.register_entry("ovpn.{}.total".format(ovpn_name), 0, "Number of clients total for $2")
                mv.register_entry("ovpn.{}.online".format(ovpn_name), 0, "Number of clients online for $2")
                mv.register_entry("ovpn.{}.offline".format(ovpn_name), 0, "Number of clients offline for $2")
            num_online = len([True for key in clients if ovpn_inst[key]["online"]])
            num_offline = len(clients) - num_online
            mv["ovpn.{}.total".format(ovpn_name)] = len(clients)
            mv["ovpn.{}.online".format(ovpn_name)] = num_online
            mv["ovpn.{}.offline".format(ovpn_name)] = num_offline
            # iterate over clients
            act_dict = self.__client_dict[ovpn_name]
            for client in clients:
                c_dict = ovpn_inst[client]
                client_dict = act_dict.setdefault(
                    client,
                    {
                        "registered": False,
                        "speed": net_speed()
                    }
                )
                c_pfix = "ovpn.{}.{}".format(ovpn_name, client.replace(".", "_"))
                if not client_dict["registered"]:
                    client_dict["registered"] = True
                    mv.register_entry("{}.rx".format(c_pfix), 0., "bytes per seconds received by $3", "Byte/s", 1024)
                    mv.register_entry("{}.tx".format(c_pfix), 0., "bytes per seconds transmitted by $3", "Byte/s", 1024)
                act_rx, act_tx = client_dict["speed"].feed(c_dict["rx"], c_dict["tx"])
                mv["{}.rx".format(c_pfix)] = act_rx
                mv["{}.tx".format(c_pfix)] = act_tx
            # pprint.pprint(ovpn_inst.get_repr())

    def update_status(self):
        if self.__last_status_update is None or abs(self.__last_status_update - time.time()) > 5:
            # update
            self.__last_status_update = time.time()
            found_inst = []
            if os.path.isdir(OPENVPN_DIR):
                for entry in os.listdir(OPENVPN_DIR):
                    if entry.endswith(".conf") and not entry.startswith("."):
                        e_key = entry[:-5]
                        if e_key in self.__inst_dict:
                            try:
                                self.__inst_dict[e_key].update()
                            except:
                                self.log(
                                    u"unable to update instance {}: {}".format(
                                        entry,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                found_inst.append(e_key)
                        else:
                            try:
                                new_inst = openvpn_instance(self.log, entry)
                            except:
                                self.log(
                                    u"unable to create new openvpn_instance for {}: {}".format(
                                        entry,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                self.__inst_dict[e_key] = new_inst
                                found_inst.append(e_key)
            old_inst = [key for key in self.__inst_dict.keys() if key not in found_inst]
            if old_inst:
                self.log(
                    u"removing {}: {}".format(
                        logging_tools.get_plural("instance", len(old_inst)),
                        ", ".join(sorted(old_inst))
                    )
                )
                for inst in old_inst:
                    del self.__inst_dict[inst]

    def keys(self):
        return self.__inst_dict.keys()

    def __getitem__(self, key):
        return self.__inst_dict[key]


class openvpn_instance(object):
    def __init__(self, log_h, name):
        self.__log_handle = log_h
        self.name = name
        self.__conf_obj = process_tools.cached_file(
            "{}/{}".format(
                OPENVPN_DIR, name),
            log_handle=self.log)
        self.__status_name, self.__status_obj = ("", None)
        # save client_config_files
        self.__client_config_files = {}
        # for machinevector
        self.mv_registered = False
        # speed dict
        self.__speed_dict = {}
        self.update()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_handle.log(u"[oi] {}".format(what), log_level)

    def keys(self):
        return self.__act_dict.keys()

    def __getitem__(self, key):
        return self.__act_dict[key]

    def update(self):
        self.ovpn_type, self.__device = (
            "unknown",
            "unknown",
        )
        self.__conf_obj.update()
        self.__ccd = None
        self.__verify_script = None
        for line in self.__conf_obj.content.split("\n"):
            line_p = line.strip().split()
            if line_p:
                key = line_p.pop(0)
                if line_p:
                    if key == "status":
                        stat_name = line_p[0]
                        if stat_name != self.__status_name:
                            self.__status_name = stat_name
                            self.__status_obj = process_tools.cached_file(self.__status_name, log_handle=self.__log_handle)
                if key == "client":
                    self.ovpn_type = "client"
                elif key == "server":
                    self.ovpn_type = "server"
                elif key == "dev":
                    self.__device = line_p[0]
                elif key == "client-config-dir":
                    self.__ccd = line_p[0]
                elif key == "tls-verify":
                    self.__verify_script = line_p[0]
        if self.__ccd:
            self.__ccd = os.path.join(OPENVPN_DIR, self.__ccd)
        self.state, self.status_str = (False, "no status file found")
        act_dict = {}
        if self.__status_obj:
            self.__status_obj.update()
            if self.__status_obj.content is not None:
                if self.ovpn_type == "client":
                    stat_lines = self.__status_obj.content.split("\n")
                    # default value
                    self.state, self.status_str = (False, "wrong version of client status file")
                    if stat_lines[0].startswith("OpenVPN STAT"):
                        stat_lines.pop(0)
                        upd_line = stat_lines.pop(0).split(",")
                        if upd_line[0] == "Updated":
                            act_time = time.time()
                            upd_time = time.mktime(time.strptime(upd_line[1]))
                            if abs(act_time - upd_time) > 60:
                                # client is dead
                                self.state, self.status_str = (False, "not connected")
                            else:
                                self.state, self.status_str = (True, "is connected")
                else:
                    stat_lines = self.__status_obj.content.split("\n")
                    if stat_lines[0].startswith("TITLE"):
                        for line in stat_lines:
                            line = line.strip().split(",")
                            if line and line[0]:
                                key = line.pop(0)
                                if key in ["TIME"]:
                                    cur_time = int(line[-1])
                                    keys = self.__speed_dict.keys()
                                    if cur_time not in keys:
                                        # remove oldest one
                                        if len(keys) > 1:
                                            del self.__speed_dict[min(keys)]
                                        self.__speed_dict[cur_time] = {}
                                        # get keys again
                                        keys = self.__speed_dict.keys()
                                    if len(keys) == 2:
                                        prev_speed_dict, cur_speed_dict = (self.__speed_dict[min(keys)], self.__speed_dict[max(keys)])
                                        diff_time = abs(keys[0] - keys[1])
                                    else:
                                        diff_time = None
                                elif key in ["CLIENT_LIST", "ROUTING_TABLE"]:
                                    if key == "CLIENT_LIST":
                                        c_name = line[0]
                                        act_dict[c_name] = {
                                            "online": True,
                                            "src": line[1],
                                            "remote": line[2],
                                            "rx": int(line[3]),
                                            "tx": int(line[4]),
                                            "connected": int(line[6])
                                        }
                                        if diff_time:
                                            cur_speed_dict[c_name] = (int(line[3]), int(line[4]))
                                            if c_name in prev_speed_dict:
                                                act_dict[c_name].update({
                                                    "rxs": abs(int(line[3]) - prev_speed_dict[c_name][0]) / diff_time,
                                                    "txs": abs(int(line[4]) - prev_speed_dict[c_name][1]) / diff_time,
                                                })
                                    elif key == "ROUTING_TABLE":
                                        act_dict[line[1]]["reference"] = int(line[4])
                        # try to add client dirs
                        if self.__ccd:
                            for client_name in act_dict.keys():
                                cconf_name = os.path.join(
                                    self.__ccd,
                                    client_name)
                                if os.path.isfile(cconf_name):
                                    if cconf_name not in self.__client_config_files:
                                        self.__client_config_files[cconf_name] = process_tools.cached_file(cconf_name,
                                                                                                           log_handle=self.log)
                                    self.__client_config_files[cconf_name].update()
                                    cconf_object = self.__client_config_files[cconf_name]
                                    if cconf_object.content is not None:
                                        for client_line in cconf_object.content.split("\n"):
                                            line_split = client_line.strip().split()
                                            if line_split and line_split[0] == "ifconfig-push":
                                                act_dict.setdefault(client_name, {"oneline": False})["client_ip"] = line_split[1]
                        self.state, self.status_str = (True, "{} connected".format(logging_tools.get_plural("client", len(act_dict.keys()))))
                    else:
                        self.state, self.status_str = (False, "wrong version of server status file")
            else:
                self.state, self.status_str = (False, "status file defined but unable to read")
        else:
            self.state, self.status_str = (False, "no status file defined")
        self.__act_dict = act_dict

    def get_repr(self):
        return {
            "state": self.state,
            "status": self.status_str,
            "has_verify_script": True if self.__verify_script else False,
            "type": self.ovpn_type,
            "dict": self.__act_dict,
            "device": self.__device
        }


class certificate_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def _get_pem_status(self, file_name):
        pem_com = "/usr/bin/openssl x509 -in {} -startdate -enddate -noout".format(file_name)
        c_stat, c_out = commands.getstatusoutput(pem_com)
        if not c_stat:
            act_dict = {}
            for line in c_out.split("\n"):
                if line.count("="):
                    key, value = [part.strip() for part in line.split("=", 1)]
                    if key.lower() in ["notbefore", "notafter"]:
                        time_st = datetime.datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
                        act_dict[key] = time_st
        else:
            act_dict = None
        return act_dict

    def __call__(self, srv_com, cm):
        temp_dir = tempfile.mkdtemp("_certcheck")
        pem_files = sum([glob.glob(s_glob) for s_glob in cm.arguments], [])
        inline_cert_re = re.compile(".*</*(?P<cert_type>[a-zA-Z]+)>.*")
        cert_dict, map_dict = ({}, {})
        if not pem_files and os.path.isdir(OPENVPN_DIR):
            conf_files = [file_name for file_name in os.listdir(OPENVPN_DIR) if file_name.endswith(".conf")]
            for conf_file in conf_files:
                file_name = os.path.join(OPENVPN_DIR, conf_file)
                lines = file(file_name, "r").read().split("\n")
                is_inline = False
                inline_pems = {}
                for line in lines:
                    cr_match = inline_cert_re.match(line)
                    if cr_match:
                        is_inline = not is_inline
                        cur_inline_name = cr_match.group("cert_type")
                        if is_inline:
                            if cur_inline_name in inline_pems:
                                self.log("pem '{}' already present".format(cur_inline_name), logging_tools.LOG_LEVEL_ERROR)
                            else:
                                inline_pems[cur_inline_name] = []
                    else:
                        if is_inline:
                            inline_pems[cur_inline_name].append(line)
                        else:
                            l_parts = line.strip().split()
                            if len(l_parts) == 2:
                                key, value = l_parts
                                if key.lower() in ["ca", "cert"]:
                                    map_dict[os.path.join(OPENVPN_DIR, value)] = file_name
                for key, value in inline_pems.iteritems():
                    if key not in ["key"]:
                        full_name = os.path.join(temp_dir, "{}_{}.pem".format(conf_file.replace(".conf", ""), key))
                        file(full_name, "w").write("\n".join(inline_pems[key]))
                        pem_files.append(full_name)
                # pprint.pprint(inline_pems)
            for dir_name, _dir_list, file_list in os.walk(OPENVPN_DIR):
                pem_files.extend([os.path.join(dir_name, file_name) for file_name in file_list if file_name.endswith(".pem")])
        for file_name in pem_files:
            act_dict = self._get_pem_status(file_name)
            if act_dict:
                if file_name in map_dict:
                    act_dict["openvpn_config"] = map_dict[file_name]
                cert_dict[file_name] = act_dict
        shutil.rmtree(temp_dir)
        srv_com["certificates"] = cert_dict

    def interpret(self, srv_com, cur_ns):
        cert_dict = srv_com["certificates"]
        return self._interpret(cert_dict)

    def interpret_old(self, result, parsed_coms):
        cert_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(cert_dict)

    def _interpret(self, cert_dict):
        num_dict = {key: 0 for key in ["ok", "warn", "error", "total"]}
        errors = []
        act_time = datetime.datetime.now()
        for file_name in sorted(cert_dict.keys()):
            cert_info = cert_dict[file_name]
            start_diff_time, end_diff_time = (
                (act_time - cert_info["notBefore"]).days,
                (cert_info["notAfter"] - act_time).days
            )
            if "openvpn_config" in cert_info:
                info_str = "{} ({})".format(
                    file_name,
                    os.path.basename(cert_info["openvpn_config"]))
            else:
                info_str = file_name
            num_dict["total"] += 1
            if start_diff_time < 0:
                num_dict["error"] += 1
                errors.append("{}: will start in {}".format(
                    info_str,
                    logging_tools.get_plural("day", abs(start_diff_time))))
            if end_diff_time < 0:
                num_dict["error"] += 1
                errors.append("{}: is expired since {}".format(
                    info_str,
                    logging_tools.get_plural("day", abs(end_diff_time))))
            elif end_diff_time < 30:
                if end_diff_time < 14:
                    num_dict["error"] += 1
                else:
                    num_dict["error"] += 1
                    num_dict["warn"] += 1
                errors.append("{}: will expire in {}".format(
                    info_str,
                    logging_tools.get_plural("day", abs(end_diff_time))))
        if num_dict["error"]:
            ret_state = limits.nag_STATE_CRITICAL
        elif num_dict["warn"]:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, "checked {}, {}{}".format(
            logging_tools.get_plural("certificate", num_dict["total"]),
            ", ".join([logging_tools.get_plural(key, num_dict[key]) for key in ["ok", "warn", "error"] if num_dict[key]]) or "no problems",
            "; {}".format(", ".join(sorted(errors))) if errors else "")


class openvpn_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-i", dest="instance", type=str, default="ALL")
        self.parser.add_argument("-p", dest="peer", type=str, default="ALL")

    def __call__(self, srv_com, cur_ns):
        self.module.update_status()
        insts = self.module.keys()
        if insts:
            ret_dict = {}
            for inst in sorted(insts):
                ret_dict[inst] = self.module[inst].get_repr()
        else:
            ret_dict = {}
        srv_com["openvpn_instances"] = ret_dict

    def interpret_old(self, result, parsed_coms):
        inst_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(inst_dict, parsed_coms, self.NOGOOD_srv_com["host"].text)

    def interpret(self, srv_com, cur_ns):
        inst_dict = srv_com["openvpn_instances"]
        return self._interpret(inst_dict, cur_ns, srv_com["host"].text)

    def _check_single_peer(self, clients, vpn_device, inst_name, peer_name, res_field):
        ret_state = limits.nag_STATE_OK
        p_ip = clients.get(peer_name, {}).get("client_ip", "")
        p_ip_str = " at {}".format(p_ip) if p_ip else ""
        if peer_name in clients and clients[peer_name].get("online", True):
            peer_dict = clients[peer_name]
            if "remote" in peer_dict:
                remote_ip = peer_dict["remote"]
                if p_ip:
                    # has p_ip, compare with remote_ip
                    if remote_ip == p_ip:
                        # same, ok
                        pass
                    else:
                        # differ, oh-oh
                        p_ip_str = "{} != {}".format(p_ip_str, remote_ip)
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                else:
                    # no p_ip, set p_ip_str according to
                    p_ip_str = " at {}".format(remote_ip)
            if "rxs" in peer_dict:
                res_field.append("%s (Srv on %s, client %s%s ok, %s/s %s/s) | rx=%d tx=%d" % (
                    inst_name,
                    vpn_device,
                    peer_name,
                    p_ip_str,
                    logging_tools.get_size_str(peer_dict["rxs"]),
                    logging_tools.get_size_str(peer_dict["txs"]),
                    peer_dict["rxs"],
                    peer_dict["txs"],
                ))
            else:
                res_field.append("%s (Srv on %s, client %s%s ok)" % (
                    inst_name,
                    vpn_device,
                    peer_name,
                    p_ip_str))
        else:
            res_field.append("%s (Srv via %s, client %s%s not found)" % (
                inst_name,
                vpn_device,
                peer_name,
                p_ip_str))
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state

    def _interpret(self, res_dict, cur_ns, host):
        inst_name = cur_ns.instance
        peer_name = cur_ns.peer
        if peer_name == "ALL":
            ret_state, res_field = (limits.nag_STATE_OK, [logging_tools.get_plural("instance", len(res_dict.keys()))])
        else:
            ret_state, res_field = (limits.nag_STATE_OK, [])
        if inst_name != "ALL":
            check_instances = [inst_name]
        else:
            check_instances = res_dict.keys()
        for inst_name in sorted(check_instances):
            # iterate over instances
            if inst_name in res_dict:
                # instance found
                if type(res_dict[inst_name]) is tuple:
                    # old kind of result
                    inst_ok, inst_str, clients = res_dict[inst_name]
                    i_type, vpn_device, _p_ip = (
                        "server",
                        "not set",
                        ""
                    )
                else:
                    # new kind
                    act_sdict = res_dict[inst_name]
                    inst_ok, inst_str, clients, i_type = (
                        act_sdict["state"],
                        act_sdict["status"],
                        act_sdict["dict"],
                        act_sdict["type"]
                    )
                    vpn_device = act_sdict.get("device", "not set")
                if inst_ok:
                    if i_type == "client":
                        res_field.append("{} (Client via {})".format(
                            inst_name,
                            vpn_device))
                    elif i_type == "server":
                        if not act_sdict.get("has_verify_script", False):
                            ret_state = max(ret_state, limits.nag_STATE_WARNING)
                            res_field.append("no tls-verify script")
                        # peer == client
                        if peer_name != "ALL":
                            if peer_name.count(","):
                                # check more than one peer
                                ok_peers = []
                                for _peer_name in peer_name.split(","):
                                    _field = []
                                    _local_state = self._check_single_peer(clients, vpn_device, inst_name, _peer_name, _field)
                                    if _local_state == limits.nag_STATE_OK:
                                        ok_peers.append(_peer_name)
                                    else:
                                        ret_state = max(ret_state, _local_state)
                                        res_field.extend(_field)
                                if ok_peers:
                                    res_field.append("{} ok: {}".format(logging_tools.get_plural("peer", len(ok_peers)), ", ".join(sorted(ok_peers))))
                            else:
                                ret_state = max(ret_state, self._check_single_peer(clients, vpn_device, inst_name, peer_name, res_field))
                        else:
                            if clients:
                                res_field.append(
                                    "{} (server via {}, {}: {})".format(
                                        inst_name,
                                        vpn_device,
                                        logging_tools.get_plural("client", len(clients.keys())),
                                        ",".join(sorted(clients.keys()))
                                    )
                                )
                            else:
                                res_field.append("{} (no clients)".format(inst_name))
                    else:
                        res_field.append("{} ({})".format(inst_name, i_type))
                else:
                    res_field.append("{} ({})".format(inst_name, inst_str))
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            else:
                res_field.append("no instance '{}' found".format(inst_name))
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state, ", ".join(res_field)
