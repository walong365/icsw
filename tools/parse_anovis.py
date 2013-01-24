#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-backbone-tools
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
""" parse anovis CSV file and create objects """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import csv
import logging_tools
import configfile
import process_tools
import threading_tools
import zmq
import time
import pprint
import ipvx_tools
import net_tools
from lxml import etree
from lxml.builder import E
from django.db.models import Q
from initat.cluster.backbone.models import device, device_group, device_type, \
     netdevice, device_class, netdevice_speed, net_ip, peer_information, \
     mon_host_cluster, mon_service_cluster, mon_service_templ, device_config, config, \
     user, group, mon_ext_host
import server_command

VERSION_STRING = "0.2"

global_config = configfile.get_global_config(process_tools.get_programm_name())

class anovis_site(object):
    def __init__(self, log_com, csv_line):
        self.__log_com = log_com
        # object dict
        self.site_xml = E.site()
        # db cache
        self.__db_cache = {}
        self.parsed = 0
        for key, value in csv_line.iteritems():
            try:
                self.feed(key, value)
            except:
                self.log("error while feeding key %s (value %s): %s" % (key, value, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                raise
            self.parsed += 1
        self.feed("root_name", self.name.lower().replace(" ", "_").replace("-", "_"))
        self.feed("root_ip", "0.0.0.0")
        self.log("init site (%d keys parsed)" % (self.parsed))
        self.remove_empty_objects()
        self._log_xml("before validate")
        self.validate()
    def get_db_obj(self, obj_name, search_spec, **kwargs):
        obj_class = globals()[obj_name]
        self.__db_cache.setdefault(obj_name, {})
        kw_pk = kwargs.get("pk", None)
        if kw_pk:
            kw_pk = int(kw_pk)
            if kw_pk not in self.__db_cache[obj_name]:
                self.__db_cache[obj_name][kw_pk] = obj_class.objects.get(pk=kw_pk)
            return self.__db_cache[obj_name][kw_pk]
        cur_obj = obj_class.objects.get(search_spec)
        self.__db_cache[obj_name][cur_obj.pk] = cur_obj
        return cur_obj
    def remove_empty_objects(self):
        removed = 0
        for xpath_str in [
            ".//hosts/host[@name='']",
            ".//firewalls/firewall[@name='']",
            ".//isp/routers/router[@name='']",
            ".//isp/fws/fw[@name='']",
            ]:
            for cur_del in self.site_xml.xpath(xpath_str):
                while True:
                    removed += 1
                    cur_parent = cur_del.getparent()
                    cur_parent.remove(cur_del)
                    cur_del = cur_parent
                    # check for empty child list
                    if len(cur_del):
                        break
        self.log("removed %s" % (logging_tools.get_plural("element", removed)))
    def validate(self):
        for obj_name, keys_needed, sub_el_needed, obj_needed in [
            ("root"      , set(["name", "ip"])                         , set(), True),
            ("fw_service", set(["name", "ip", "check_template"])       , set(), True),
            ("firewall"  , set(["name", "ip", "num", "check_template"]), set(), False),
            ("host"      , set(["name", "ip", "num", "check_template"]), set(), True),
            ("general"   , set()                                       , set(["customer", "relayer", "nagvis_template", "usergroup"]), True)]:
            obj_list = self.site_xml.findall(".//%s" % (obj_name))
            if not len(obj_list) and obj_needed:
                raise KeyError, "no %s objects found in site '%s'" % (obj_name, self.name)
            for cur_obj in obj_list:
                found_keys = set(cur_obj.attrib.keys())
                if found_keys != keys_needed:
                    raise KeyError, "keys mismatch for object '%s' in site '%s': %s" % (obj_name, self.name, ", ".join(list(keys_needed ^ found_keys)))
                #if obj_name == "host":
                    # reformat services
                    #for service_name in cur_obj.attrib["service"].split("/"):
                    #    cur_obj.append(E.service(service_name))
                for sub_el in sub_el_needed:
                    if not len(cur_obj.findall(sub_el)):
                        raise KeyError, "sub_element '%s' not found beneath %s" % (sub_el, obj_name)
                if "ip" in keys_needed:
                    cur_obj.append(E.network(E.netdevice(E.ip(cur_obj.attrib["ip"]), devname="eth0")))
            self.log("validated %s" % (
                logging_tools.get_plural(
                    "%s %s object" % (
                        "needed" if obj_needed else "optional",
                        obj_name), len(obj_list))))
    def _log_xml(self, info_str):
        if global_config["SHOW_XML"]:
            self.log("content of XML (%s)" % (info_str))
            for line in etree.tostring(self.site_xml, pretty_print=True).split("\n"):
                self.log(line)
    def add_object(self, xpath_str, **kwargs):
        create_parents_mode = kwargs.pop("create_parents_mode", False)
        if not create_parents_mode:
            parent_list = xpath_str.split("/")[:-1]
            p_list = []
            for cur_p in parent_list:
                if not p_list:
                    p_list.append(cur_p)
                else:
                    p_list.append("%s/%s" % (p_list[-1], cur_p))
            for entry in p_list:
                self.add_object(entry, create_parents_mode=True)
            #print xpath_str, parent_list
        f_list = self.site_xml.xpath("%s%s" % (
            xpath_str,
            "[%s]" % (" and ".join(["@%s='%s'" % (key, str(value)) for key, value in kwargs.iteritems()])) if kwargs else ""))
        if len(f_list):
            return f_list[0]
        else:
            c_obj_name = xpath_str.split("/")[-1].split("[")[0]
            new_obj = getattr(E, c_obj_name)()
            for key, value in kwargs.iteritems():
                new_obj.attrib[key] = str(value)
            if xpath_str.count("/"):
                self.site_xml.find("/".join(xpath_str.split("/")[:-1])).append(new_obj)
            else:
                self.site_xml.append(new_obj)
            return new_obj
    def feed(self, key, value):
        parts = key.split("_")
        try:
            if key == "site_name":
                self.name = value
            elif key in ["customer", "relayer", "nagvis_template", "usergroup"]:
                gen_obj = self.add_object("general/%s" % (key))
                gen_obj.text = value
            elif key.startswith("root"):
                fw_obj = self.add_object("root")
                lut_key = parts[-1]
                if len(parts) == 2 and lut_key in ["name", "ip"]:
                    fw_obj.attrib[lut_key] = str(value)
            elif parts[0] == "isp":
                obj_num = parts[-1]
                if parts[1] in ["router", "fw"]:
                    lut_key = parts[-2]
                    if lut_key in ["name", "ip"]:
                        self.add_object("%s/%ss/%s" % (parts[0], parts[1], parts[1]), num=obj_num).attrib[lut_key] = unicode(value)
                    else:
                        raise KeyError
            elif key.startswith("check_template"):
                if parts[2] == "service":
                    ref_spec = "fw_service"
                    obj_num = None
                else:
                    obj_num = parts.pop(-1)
                    ref_spec = {("box",) : "firewalls/firewall",
                                ("site", "host") : "hosts/host"}[tuple(parts[2:])]
                self.add_object(ref_spec, **({"num" : obj_num} if obj_num else {})).attrib["check_template"] = value
            elif key.startswith("site_fw_service"):
                lut_key = parts[-1] 
                if lut_key in ["name", "ip"] and len(parts) == 4:
                    self.add_object("fw_service").attrib[lut_key] = str(value)
                else:
                    raise KeyError
            elif key.startswith("site_host"):
                host_num = int(parts[-1])
                lut_key = parts[2] 
                if len(parts) == 4 and lut_key in ["name", "ip", "service"]:
                    self.add_object("hosts/host", num=host_num).attrib[lut_key] = str(value)
                else:
                    raise KeyError
            elif key.startswith("site_fw_box"):
                fw_num = int(parts[-1])
                lut_key = parts[3]
                if len(parts) == 5 and lut_key in ["name", "ip"]:
                    self.add_object("firewalls/firewall", num=fw_num).attrib[lut_key] = str(value)
                else:
                    raise KeyError
            else:
                raise KeyError
        except KeyError:
            raise KeyError, "unknown key '%s' (value=%s)" % (key, value)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[site %s] %s" % (self.name, what), log_level)
    def _update_object(self, db_obj, **kwargs):
        changed = []
        for key, value in kwargs.iteritems():
            if getattr(db_obj, key) != value:
                self.log("changing %s of %s '%s' from '%s' to '%s'" % (
                    key,
                    db_obj._meta.object_name,
                    unicode(db_obj),
                    unicode(getattr(db_obj, key)),
                    unicode(value)))
                setattr(db_obj, key, value)
                changed.append(key)
        if changed:
            db_obj.save()
    def db_sync(self):
        """ database sync """
        self.log("start syncing")
        self._log_xml("before sync")
        relayer_name = self.site_xml.findtext(".//general/relayer")
        self.log("relayer is specified by '%s'" % (relayer_name))
        try:
            con_dev = device.objects.prefetch_related("netdevice_set").get(Q(name=relayer_name) | Q(netdevice__net_ip__ip=relayer_name))
        except device.DoesNotExist:
            self.log("relayer specified by '%s' does not exist, connecting to master" % (relayer_name), logging_tools.LOG_LEVEL_CRITICAL)
            con_dev = None
        # check if conn_dev is a monitoring_slave
        if con_dev is not None:
            try:
                device_config.objects.get(Q(config__name="monitor_slave") & Q(device=con_dev))
            except device_config.DoesNotExist:
                mon_master = None
            else:
                mon_master = con_dev
        else:
            mon_master = None
        if mon_master is None:
            mon_master = device.objects.get(Q(device_config__config__name="monitor_server") | Q(device_config__config__name="monitor_master"))
            if con_dev is None:
                self.log("also using monitor_master '%s' als con_dev" % (unicode(mon_master)), logging_tools.LOG_LEVEL_WARN)
                con_dev = mon_master
        self.log("monitoring_master is '%s'" % (unicode(mon_master)))
        con_nd = [cur_nd for cur_nd in con_dev.netdevice_set.all() if cur_nd.devname.startswith("eth")]
        if not con_nd:
            raise ValueError, "no valid netdevices found"
        con_nd = con_nd[0]
        self.log("connecting to netdevice %s (device %s)" % (unicode(con_nd), unicode(con_nd.device)))
        # user access
        user_name = self.site_xml.findtext(".//general/usergroup")
        if user_name.strip():
            group_name = global_config["GROUP_NAME"]
            self.log("groupname/username is '%s' / '%s'" % (group_name, user_name))
            try:
                my_group = group.objects.get(Q(groupname=group_name))
            except group.DoesNotExist:
                raise ValueError, "group '%s' not found" % (group_name)
            try:
                my_user = user.objects.get(Q(login=user_name))
            except user.DoesNotExist:
                my_user = user(
                    login=user_name,
                    active=True,
                    uid=max(list(user.objects.all().values_list("uid", flat=True))) + 1,
                    group=my_group,
                    first_name="",
                    last_name="",
                )
                my_user.save()
            my_user.password = user_name
            my_user.save()
            self.log("group / user is %s / %s" % (unicode(my_group), unicode(my_user)))
        else:
            self.log("username is empty, skipping user creation", logging_tools.LOG_LEVEL_WARN)
            my_user = None
        devg_name = self.site_xml.findtext(".//general/customer").lower().replace(" ", "_")
        try:
            my_devg = device_group.objects.get(Q(name=devg_name))
        except device_group.DoesNotExist:
            self.log("creating device_group")
            my_devg = device_group(
                name=devg_name,
                description="auto created by script")
            my_devg.save()
        if my_user is not None:
            if my_devg.pk not in my_user.allowed_device_groups.all().values_list("pk", flat=True):
                self.log("adding device_group %s to user" % (unicode(my_devg)))
                my_user.allowed_device_groups.add(my_devg)
        my_devt = device_type.objects.get(Q(identifier="H"))
        my_devc = device_class.objects.get(Q(pk=1))
        my_nd_speed = netdevice_speed.objects.get(Q(full_duplex=True) & Q(speed_bps=1000000000))
        hc_srv_template = mon_service_templ.objects.get(Q(name=global_config["HC_TEMPLATE"]))
        # iterate over devices
        for dev_xpath in ["fw_service", "firewall", "host", "root"]:
            dev_list = self.site_xml.findall(".//%s" % (dev_xpath))
            for cur_dev in dev_list:
                try:
                    db_dev = self.get_db_obj("device", Q(name=cur_dev.attrib["name"]))
                except device.DoesNotExist:
                    db_dev = device(
                        name=cur_dev.attrib["name"],
                        device_group=my_devg,
                        device_type=my_devt,
                        device_class=my_devc,
                    )
                    db_dev.save()
                cur_dev.attrib["pk"] = str(db_dev.pk)
                # get mon_ext_host
                img_name = {"fw_service" : "linux40",
                            "firewall"   : "firewall",
                            "host"       : "my_server",
                            "root"       : "hub"}.get(dev_xpath, None)
                if img_name:
                    try:
                        new_meh = mon_ext_host.objects.get(Q(name=img_name))
                    except mon_ext_host.DoesNotExist:
                        self.log("image with name '%s' not found" % (img_name))
                        new_meh = None
                self._update_object(db_dev, comment=self.name, monitor_server=mon_master, device_group=my_devg, automap_root_nagvis=dev_xpath in ["root"], mon_ext_host=new_meh)
                for cur_nd in cur_dev.findall(".//netdevice"):
                    try:
                        cur_ndev = self.get_db_obj("netdevice", Q(devname=cur_nd.attrib["devname"]) & Q(device=db_dev))
                    except netdevice.DoesNotExist:
                        cur_ndev = netdevice(
                            device=db_dev,
                            devname=cur_nd.attrib["devname"],
                            netdevice_speed=my_nd_speed,
                        )
                        cur_ndev.save()
                    self._update_object(cur_ndev, routing=dev_xpath in ["firewall", "root"])
                    cur_nd.attrib["pk"] = str(cur_ndev.pk)
                    cur_ip = cur_nd.find("ip")
                    try:
                        db_ip = self.get_db_obj("net_ip", Q(netdevice=cur_ndev))
                    except net_ip.DoesNotExist:
                        db_ip = net_ip(
                            netdevice=cur_ndev,
                            ip=cur_ip.text,
                        )
                        db_ip.save()
                    cur_ip.attrib["pk"] = str(db_ip.pk)
        # root device
        root_dev = self.get_db_obj("device", None, pk=self.site_xml.find(".//root").attrib["pk"])
        self.log("root device is '%s'" % (unicode(root_dev)))
        # get all pks
        nd_pks = self.site_xml.xpath(".//netdevice[@pk]/@pk")
        # generate a list of (source_ndev, target_ndev) tuples
        conn_pairs = [
            # connections from fw to monitoring server
            #con_nd, self.get_db_obj("netdevice", None, pk=int(cur_obj.attrib["pk"]))) for cur_obj in self.site_xml.xpath(".//firewall//netdevice")
        ]
        root_nd = self.get_db_obj("netdevice", None, pk=int(self.site_xml.find(".//root//netdevice").attrib["pk"]))
        # connection from root to monitoring server
        conn_pairs.append(
            (con_nd, root_nd)
        )
        # connections from fw to root
        conn_pairs.extend(
            [(root_nd, self.get_db_obj("netdevice", None, pk=int(cur_obj.attrib["pk"]))) for cur_obj in self.site_xml.xpath(".//firewall//netdevice")]
        )
        # connections from devices to firewalls
        conn_pairs.extend(
            sum([[(self.get_db_obj("netdevice", None, pk=int(fw_obj.attrib["pk"])), self.get_db_obj("netdevice", None, pk=int(other_obj.attrib["pk"]))) for fw_obj in self.site_xml.xpath(".//firewall//netdevice")] for other_obj in self.site_xml.xpath(".//fw_service//netdevice|.//host//netdevice")], [])
        )
        pure_list = [(s_nd.pk, d_nd.pk) for s_nd, d_nd in conn_pairs]
        present_cons = peer_information.objects.filter(Q(s_netdevice__in=nd_pks) | Q(d_netdevice__in=nd_pks))
        present_cons_pure = [(cur_pi.s_netdevice_id, cur_pi.d_netdevice_id) for cur_pi in present_cons]
        created, deleted = (0, 0)
        for s_nd, d_nd in conn_pairs:
            if (s_nd.pk, d_nd.pk) in present_cons_pure or (d_nd.pk, s_nd.pk) in present_cons_pure:
                pass
            else:
                created += 1
                peer_information(
                    s_netdevice=s_nd,
                    d_netdevice=d_nd,
                    penalty=1).save()
        for cur_pi in present_cons:
            if (cur_pi.s_netdevice_id, cur_pi.d_netdevice_id) not in pure_list:
                if cur_pi.s_netdevice_id == root_nd.pk:
                    # do not remove connections from root_device downwards, may be other sites
                    self.log("skipping pi deletion (multi-line site CSV ?)", logging_tools.LOG_LEVEL_WARN)
                else:
                    deleted += 1
                    cur_pi.delete()
        self.pi_created, self.pi_deleted = (created, deleted)
        self.log("connections created / deleted: %d / %d" % (created, deleted))
        # host cluster
        try:
            cur_hc = self.get_db_obj("mon_host_cluster", Q(name=self.name))
        except mon_host_cluster.DoesNotExist:
            cur_hc = mon_host_cluster(
                name=self.name,
                main_device=root_dev,
                mon_service_templ=hc_srv_template,
            )
            cur_hc.save()
        #present_hc_devs = cur_hc.devices.all()
        for del_dev in cur_hc.devices.all():
            cur_hc.devices.remove(del_dev)
        new_hc_devs = [self.get_db_obj("device", None, pk=int(fw_obj.attrib["pk"])) for fw_obj in self.site_xml.xpath(".//firewall")]
        for new_dev in new_hc_devs:
            cur_hc.devices.add(new_dev)
        self._update_object(cur_hc, description=self.name, main_device=root_dev, mon_service_templ=hc_srv_template)
        # get configs
        for dev_struct in self.site_xml.xpath(".//firewall|.//fw_service|.//host"):
            if "pk" in dev_struct.attrib and "check_template" in dev_struct.attrib:
                cur_dev = self.get_db_obj("device", None, pk=dev_struct.attrib["pk"])
                # delete previous configs
                cur_dev.device_config_set.all().delete()
                conf_name = dev_struct.attrib["check_template"].strip().replace("-", "_")
                try:
                    cur_conf = config.objects.get(Q(name=conf_name))
                except config.DoesNotExist:
                    self.log("no config with name '%s' found" % (conf_name), logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    device_config(
                        device=cur_dev,
                        config=cur_conf,
                        ).save()
                    self.log("adding check '%s' to %s" % (
                        dev_struct.attrib["check_template"],
                        unicode(cur_dev)))
            else:
                self.log("pk or check_template attribute missing in %s" % (dev_struct.tag), logging_tools.LOG_LEVEL_ERROR)
        self._log_xml("after sync")
        self.log("done")
        
class anvois_parser(object):
    def __init__(self):
        self.zmq_context = zmq.Context()
        self.__verbose = global_config["VERBOSE"]
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        self.log("init parser")
        self.__start_time = time.time()
        self.__key_mapping = None
        self.__site_list = []
    def parse(self):
        self.__ret_state = 0
        self.log("start parsing")
        try:
            dict_reader = csv.DictReader(file(global_config["SOURCE"], "r"), delimiter=";")
            sites_parsed, sites_skipped = (0, 0)
            for csv_line in dict_reader:
                if not csv_line[dict_reader.fieldnames[0]].strip().startswith("#"):
                    sites_parsed += 1
                    csv_line = self._fix_line(csv_line)
                    self.__site_list.append(anovis_site(self.log, csv_line))
                else:
                    sites_skipped += 1
            self.log("parsed %s (skipped %d)" % (logging_tools.get_plural("site", sites_parsed), sites_skipped))
        except:
            self.log("something bad happened: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log("    %s" % (line), logging_tools.LOG_LEVEL_CRITICAL)
            self.__ret_state = 1
        return self.__ret_state
    def db_sync(self):
        self.log("starting db_sync for %s" % (logging_tools.get_plural("site", len(self.__site_list))))
        # start creation of DB-objects
        [an_site.db_sync() for an_site in self.__site_list]
        self.log("validated %s" % (logging_tools.get_plural("site", len(self.__site_list))))
        pi_created = sum([cur_site.pi_created for cur_site in self.__site_list])
        pi_deleted = sum([cur_site.pi_deleted for cur_site in self.__site_list])
        self.log("pi(s) created / deleted: %d / %d" % (pi_created, pi_deleted))
        self.pi_created, self.pi_deleted = (pi_created, pi_deleted)
    def notify_servers(self):
        if self.pi_created or self.pi_deleted:
            self._contact_server(8004, "rebuild_hopcount")
        else:
            self.log("peer_information not changed", logging_tools.LOG_LEVEL_WARN)
        self._contact_server(8010, "rebuild_host_config")
    def _contact_server(self, dst_port, command):
        self.log("sending command '%s' to localhost (port %d)" % (command, dst_port))
        srv_com = server_command.srv_command(command=command)
        dst_addr = "tcp://localhost:%d" % (dst_port)
        result = net_tools.zmq_connection("parse_anovis", timeout=5).add_connection(dst_addr, srv_com)
        if not result:
            self.log("error contacting server", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("sent %s to %s" % (command, dst_addr))
    def _fix_line(self, in_line):
        if not self.__key_mapping:
            # generate key mapping
            _map = {}
            for key in set(in_line.keys()):
                orig_key = key
                key = key.split("(=")[0]
                parts = [{"firewall"  : "fw"}.get(part, part) for part in key.lower().split()]
                t_key = "_".join(parts)
                t_key = t_key.replace("-", "_").replace(":_", ":").replace("_:", ":")
                _map[orig_key] = t_key
            self.__key_mapping = _map
            for key in sorted(_map):
                self.log("key %-64s => %s" % (key, self.__key_mapping[key]))
        ret_dict = dict([(self.__key_mapping[key], value) for key, value in in_line.iteritems()])
        # check ips
        ret_dict = dict([(key, (ipvx_tools.ipv4(value) if value.strip() != "" else "") if key.count("_ip") else value) for key, value in ret_dict.iteritems()])
        return ret_dict
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
        if self.__verbose:
            print "[%-5s] %s" % (logging_tools.get_log_level_str(log_level), what)
    def close(self):
        self.__end_time = time.time()
        self.log("run took %s" % (logging_tools.get_diff_time_str(self.__end_time - self.__start_time)))
        self.__log_template.close()
        self.zmq_context.term()
            
def main():
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("SOURCE"         , configfile.str_c_var("", help_string="file to parse [%(default)s]")),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"       , configfile.str_c_var(prog_name)),
        ("VERBOSE"        , configfile.bool_c_var(False, help_string="be verbose [%(default)s]")),
        ("HC_TEMPLATE"    , configfile.str_c_var("notset", help_string="serivce template for host cluster [%(default)s]", choices=mon_service_templ.objects.all().values_list("name", flat=True))),
        ("DB_SYNC"        , configfile.bool_c_var(False, help_string="sync to database [%(default)s]", action="store_true")),
        ("NOTIFY"         , configfile.bool_c_var(False, help_string="notify servers [%(default)s]", action="store_true")),
        ("GROUP_NAME"     , configfile.str_c_var("", help_string="name of group [%(default)s]", action="store_true")),
        ("SHOW_XML"       , configfile.bool_c_var(False, help_string="show XML-structures [%(default)s]", action="store_true")),
    ])
    options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=False,
        positional_arguments=False)
    my_parser = anvois_parser()
    ret_state = my_parser.parse()
    if not ret_state and global_config["DB_SYNC"]:
        my_parser.db_sync()
        if global_config["NOTIFY"]:
            my_parser.notify_servers()
    my_parser.close()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
    