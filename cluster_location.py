#!/usr/bin/python-init -Ot
#
# Copyright (C) 2012 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone-sql
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
""" module for checking current server status and extracting routes to other server """

import os
import os.path
import re
import sys
import process_tools
import logging_tools
import array
import socket
import datetime
import configfile
import config_tools
import types
import pprint
from django.db.models import Q
from init.cluster.backbone.models import device_variable, new_config, device, config_blob, config_bool, config_int, config_str, net_ip
import netifaces

def read_config_from_db(g_config, server_type, init_list=[], host_name="", **kwargs):
    if not host_name:
        # AL 20120401 **kwargs delete, FIXME ?
        host_name = process_tools.get_machine_name()
    g_config.add_config_entries(init_list, database=True)
    if not kwargs.get("dummy_run", False):
        num_serv, serv_idx, s_type, s_str, config_idx, real_config_name=is_server(server_type.replace("%", ""), True, False, host_name.split(".")[0], dc=kwargs.get("dc", None))
        #print num_serv, serv_idx, s_type, s_str, config_idx, real_config_name
        if num_serv:
            # dict of local vars without specified host
            l_var_wo_host = {}
            for short in ["str",
                          "int",
                          "blob",
                          "bool"]:
                # very similiar code appears in config_tools.py
                #sql_str = "SELECT cv.* FROM new_config c INNER JOIN device_config dc LEFT JOIN config_%s cv ON cv.new_config=c.new_config_idx WHERE (cv.device=0 OR cv.device=%d) AND dc.device=%d AND dc.new_config=c.new_config_idx AND c.name='%s' ORDER BY cv.device, cv.name" % (short, config_idx, serv_idx, real_config_name)
                #dc.execute(sql_str)
                src_sql_obj = globals()["config_%s" % (short)].objects
                if init_list:
                    src_sql_obj = src_sql_obj.filter(Q(name__in=[var_name for var_name, var_value in init_list]))
                for db_rec in src_sql_obj.filter(
                    (Q(device=0) | Q(device=None) | Q(device=serv_idx)) &
                    (Q(new_config__name=real_config_name)) &
                    (Q(new_config__device_config__device=serv_idx))):
                    if db_rec.name.count(":"):
                        var_global = False
                        local_host_name, var_name = db_rec.name.split(":", 1)
                    else:
                        var_global = True
                        local_host_name, var_name = (host_name, db_rec.name)
                    if type(db_rec.value) == type(array.array("b")):
                        new_val = configfile.str_c_var(db_rec.value.tostring(), source="%s_table" % (short))
                    elif short == "int":
                        new_val = configfile.int_c_var(int(db_rec.value), source="%s_table" % (short))
                    elif short == "bool":
                        new_val = configfile.bool_c_var(bool(db_rec.value), source="%s_table" % (short))
                    else:
                        new_val = configfile.str_c_var(db_rec.value, source="%s_table" % (short))
                    present_in_config = var_name in g_config
                    if present_in_config:
                        # copy settings from config
                        new_val.database = g_config.database(var_name)
                    new_val.is_global = var_global
                    if local_host_name == host_name:
                        if var_name.upper() in g_config and g_config.fixed(var_name.upper()):
                            # present value is fixed, keep value, only copy global / local status
                            g_config[var_name.upper].is_global = new_val.is_global
                        else:
                            g_config.add_config_entries([(var_name.upper(), new_val)])
                    elif local_host_name == "":
                        l_var_wo_host[var_name.upper()] = new_val
            # check for vars to insert
            for wo_var_name, wo_var in l_var_wo_host.iteritems():
                if not wo_var_name in g_config or g_config.get_source(wo_var_name) == "default":
                    g_config.add_config_entries([(wo_var_name, wo_var)])
    
def read_global_config(dc, server_type, init_dict=None, host_name=""):
    if init_dict is None:
        init_dict = {}
    gcd = configfile.configuration(server_type.replace("%", ""), init_dict)
    # FIXME
    #reload_global_config(dc, gcd, server_type, host_name)
    return gcd

class db_device_variable(object):
    def __init__(self, dev_idx, var_name, **kwargs):
        self.__dev_idx = dev_idx
        self.__var_name = var_name
        self.__var_type, self.__description = (None, "not set")
        try:
            act_dv = device_variable.objects.get(Q(name=var_name) & Q(device=dev_idx))
        except device_variable.DoesNotExist:
            self.__act_dv = None
        else:
            self.__act_dv = act_dv
            self.set_stuff(var_type = act_dv.var_type,
                           description = act_dv.description)
            self.set_value(getattr(act_dv, "val_%s" % (self.__var_type_name)), type_ok=True)
        self.set_stuff(**kwargs)
        if "value" in kwargs:
            self.set_value(kwargs["value"])
        if (not self.__act_dv and "value" in kwargs) or kwargs.get("force_update", False):
            # update if device_variable not found and kwargs[value] is set
            self.update()
    def update(self):
        if self.__act_dv:
            self.__act_dv.description = self.__description
            self.__act_dv.var_type = self.__var_type
            setattr(self.__act_dv, "val_%s" % (self.__var_type_name), self.__var_value)
##            dc.execute("UPDATE device_variable SET val_%s=%%s, description=%%s, var_type=%%s WHERE device_variable_idx=%%s" % (self.__var_type_name),
##                       (self.__var_value,
##                        self.__description,
##                        self.__var_type,
##                        self.__var_idx))
        else:
            self.__act_dv = device_variable(
                description=self.__description,
                var_type=self.__var_type,
                name=self.__var_name,
                device=device.objects.get(Q(pk=self.__dev_idx)))
            setattr(self.__act_dv, "val_%s" % (self.__var_type_name), self.__var_value)
        self.__act_dv.save()
##            dc.execute("INSERT INTO device_variable SET val_%s=%%s, description=%%s, var_type=%%s, name=%%s, device=%%s" % (self.__var_type_name),
##                       (self.__var_value,
##                        self.__description,
##                        self.__var_type,
##                        self.__var_name,
##                        self.__dev_idx))
##            self.__var_idx = dc.insert_id()
    def is_set(self):
        return True if self.__act_dv else False
    def set_stuff(self, **kwargs):
        if "value" in kwargs:
            self.set_value(kwargs["value"])
        if "var_type" in kwargs:
            self.__var_type = kwargs["var_type"]
            self.__var_type_name = {"s" : "str",
                                    "i" : "int" ,
                                    "b" : "blob",
                                    "t" : "time",
                                    "d" : "date"}[self.__var_type]
        if "description" in kwargs:
            self.__description = kwargs["description"]
    def set_value(self, value, type_ok=False):
        if not type_ok:
            if type(value) == type(""):
                v_type = "s"
            elif type(value) in [type(0), type(0L)]:
                v_type = "i"
            elif type(value) == type(datetime.datetime(2007, 3, 8)):
                v_type = "d"
            elif type(value) == type(datetime.time()):
                v_type = "t"
            else:
                v_type = "b"
            self.set_stuff(var_type=v_type)
        self.__var_value = value
    def get_value(self):
        return self.__var_value
        
def write_config(server_type, config, **kwargs):
    dc = kwargs.get("dc", None)
    log_lines = []
    full_host_name = socket.gethostname()
    host_name = full_host_name.split(".")[0]
    srv_info = config_tools.server_check(dc=dc, server_type=server_type, short_host_name=host_name)
    if srv_info.num_servers and srv_info.config_idx:
        for key in config.keys():
            #print k,config.get_source(k)
            #print "write", k, config.get_source(k)
            #if config.get_source(k) == "default":
            # only deal with int and str-variables
            tab_type = {"i" : "int",
                        "s" : "str",
                        "b" : "bool"}.get(config.get_type(key), None)
            if tab_type and config.database(key):
                # var global / local
                var_range_name = config.is_global(key) and "global" or "local"
                # build real var name
                real_k_name = config.is_global(key) and key or "%s:%s" % (host_name, key)
                var_obj = globals()["config_%s" % (tab_type)]
                try:
                    cur_var = var_obj.objects.get(
                        Q(name=real_k_name) &
                        (Q(device=0) | Q(device=None) | Q(device=srv_info.server_device_idx)) &
                        Q(new_config__device_config__device__device_group__device_group=srv_info.server_device_idx)
                    )
                except var_obj.DoesNotExist:
                    var_obj(name=real_k_name,
                            descr="%s default value from %s on %s" % (
                                var_range_name,
                                srv_info.config_name,
                                full_host_name),
                            new_config=new_config.objects.get(Q(pk=srv_info.config_idx)),
                            value=config[key]).save()
                else:
                    if config[key] != cur_var.value:
                        cur_var.value = config[key]
                        cur_var.save()
            else:
                #print "X", key
                pass
    return log_lines

class device_recognition(object):
    def __init__(self, **kwargs):
        dc = kwargs.get("dc", None)
        self.short_host_name = kwargs.get("short_host_name", socket.getfqdn(socket.gethostname()).split(".")[0])
        try:
            self.device_idx = device.objects.get(Q(name=self.short_host_name)).pk
        except device.DoesNotExist:
            self.device_idx = 0
        self.device_dict = {}
        # get IP-adresses (from IP)
        self.local_ips = net_ip.objects.filter(Q(netdevice__device__name=self.short_host_name)).values_list("ip", flat=True)
        # get configured IP-Adresses
        if_names = netifaces.interfaces()
        ipv4_dict = dict([(cur_if_name, [ip_tuple["addr"] for ip_tuple in value[2]][0]) for cur_if_name, value in [(if_name, netifaces.ifaddresses(if_name)) for if_name in netifaces.interfaces()] if 2 in value])
        self_ips = ipv4_dict.values()
        if self_ips:
            self.device_dict = dict([(cur_dev.pk, cur_dev.name) for cur_dev in device.objects.filter(Q(netdevice__net_ip__ip__in=self_ips))])
##            sql_str = "SELECT d.name, d.device_idx FROM device d, netdevice n, netip i WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND (%s)" % (" OR ".join(["i.ip='%s'" % (ip) for ip in self_ips]))
##            dc.execute(sql_str)
##            self.device_dict = dict([(x["device_idx"], x["name"]) for x in dc.fetchall()])

def is_server(server_type, long_mode=False, report_real_idx=False, short_host_name="", **kwargs):
    dc = kwargs.get("dc", None)
    server_idx, s_type, s_str, config_idx, real_server_name = (0, "unknown", "not configured", 0, server_type)
    if server_type.count("%"):
        match_str = " LIKE('%s')" % (server_type)
        dmatch_str = "name__icontains"
        server_info_str = "%s (with wildcard)" % (server_type.replace("%", ""))
    else:
        match_str = "='%s'" % (server_type)
        dmatch_str = "name"
        server_info_str = server_type
    if dc:
        if not short_host_name:
            short_host_name = socket.getfqdn(socket.gethostname()).split(".")[0]
        # old version
        try:
            dev_pk = device.objects.get(Q(name=short_host_name)).pk
        except device.DoesNotExist:
            dev_pk = 0
        my_confs = new_config.objects.filter(
            Q(device_config__device__device_group__device_group__name=short_host_name) &
            Q(**{dmatch_str : server_type})
            ).distinct().values_list(
                "device_config__device", "pk", "name",
                "device_config__device__device_group__device_group__name")
##        sql_str = "SELECT d.name, d.device_idx, dc.new_config, c.name AS confname, dc.device FROM device d " + \
##            "INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg " + \
##            "LEFT JOIN device d2 ON d2.device_idx = dg.device WHERE d.device_group=dg.device_group_idx " + \
##            "AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name%s AND d.name='%s'" % (match_str, short_host_name)
##        dc.execute(sql_str)
##        all_servers = dc.fetchall()
        num_servers = len(my_confs)
        #print "*", num_servers
        if num_servers == 1:
            my_conf = my_confs[0]
            if my_conf[0] == dev_pk:
                s_type = "real"
            else:
                s_type = "meta"
            server_idx, s_type, s_str, config_idx, real_server_name = (my_conf[0] if report_real_idx else dev_pk,
                                                                       s_type,
                                                                       "%s '%s'-server via hostname '%s'" % (s_type, server_type, short_host_name),
                                                                       my_conf[1],
                                                                       my_conf[2])
        else:
            # get local devices
            local_ips = net_ip.objects.filter(Q(netdevice__device__name=short_host_name)).values_list("ip", flat=True)
            # get all ips for the given config
            my_confs = new_config.objects.filter(
                Q(**{dmatch_str : server_type})
                ).values_list(
                    "device_config__device",
                    "pk",
                    "name",
                    "device_config__device__device_group__device_group",
                    "device_config__device__device_group__device_group__name",
                    "device_config__device__device_group__device_group__netdevice__net_ip__ip")
            my_confs = [entry for entry in my_confs if entry[-1] and entry[-1] not in ["127.0.0.1"]]
            #pprint.pprint(my_confs)
            # check for virtual-device
##            dc.execute("SELECT d.name, d.device_idx, dc.new_config_id, c.name AS confname, dc.device_id, i.ip FROM netip i " + \
##                       "INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device d INNER JOIN device_group dg " + \
##                       "LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group_id=dg.device_group_idx AND n.device_id=d.device_idx AND i.netdevice_id=n.netdevice_idx " + \
##                       "AND (d2.device_idx=dc.device_id OR n.device_id=dc.device_id) AND dc.new_config_id=c.new_config_idx AND c.name%s" % (match_str))
##            pprint.pprint(dc.fetchall())
            all_ips = {}
            # still to change, FIXME
            if False:
                for d_x in [y for y in dc.fetchall() if y["ip"] != "127.0.0.1"]:
                    if d_x["ip"] not in local_ips:
                        all_ips[d_x["ip"]] = (d_x["device_idx"], d_x["device_idx"], d_x["name"])
            if_names = netifaces.interfaces()
            ipv4_dict = dict([(cur_if_name, [ip_tuple["addr"] for ip_tuple in value[2]][0]) for cur_if_name, value in [(if_name, netifaces.ifaddresses(if_name)) for if_name in netifaces.interfaces()] if 2 in value])
            self_ips = ipv4_dict.values()
            for ai in all_ips.keys():
                if ai in self_ips:
                    #dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (short_host_name))
                    num_servers, server_idx, s_type, s_str, config_idx, real_server_name = (1,
                                                                                            all_ips[ai][0],
                                                                                            "virtual",
                                                                                            "virtual '%s'-server via IP-address %s" % (server_info_str, ai),
                                                                                            all_ips[ai][1],
                                                                                            all_ips[ai][2])
    else:
        num_servers = 0
    if long_mode:
        return num_servers, server_idx, s_type, s_str, config_idx, real_server_name
    else:
        return num_servers, server_idx
