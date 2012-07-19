#!/usr/bin/python -Otv
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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
""" main handler for accessing the webfrontend """

import time
import os.path
import sys
import process_tools
import logging_tools
import pprint
import crypt
import random
import cgi
import ipvx_tools
try:
    import mysql_tools
except:
    mysql_tools = None
from basic_defs import DEBUG, SESSION_ID_NAME
# for profiling
try:
    import profile
except ImportError:
    profile = None
else:
    import hotshot
    import hotshot.stats

from init.cluster.frontend.render_tools import render_me
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django.db.models import Q
from init.cluster.backbone.models import device, device_variable, user, capability, config, device_config, \
     net_ip,  hopcount, genstuff
from django.http import HttpResponse, HttpResponseRedirect

def module_info():
    return {}

#def headerparserhandler(pr):
    #pr.stdout, pr.stderr = ([], [])
    #return apache.OK

class dummy_ios(object):
    def __init__(self, req):
        self.req = req
    def write(self, what):
        self.req.write(cgi.escape(what).replace("\n", "<br>\n").replace(" ", "&nbsp;"))
    def close(self):
        pass
    def __del__(self):
        pass

VARS_FOR_LINK_LINE = ["dev"]
    
def read_standard_config(req):
    conf = {"genstuff"          : {},
            "server"            : {},
            "cluster_variables" : {}}
    for gen_var in genstuff.objects.all():
        conf["genstuff"][gen_var.name.upper()] = gen_var.value
        conf["genstuff"]["%s_DATE" % (gen_var.name.upper())] = gen_var.date
    full_server_name = req.environ["SERVER_NAME"]
    try:
        server_ipv4 = ipvx_tools.ipv4(full_server_name)
    except:
        pass
    else:
        # try to get server_name from IP
        req.dc.execute("SELECT d.name FROM device d, netdevice n, netip i WHERE d.device_idx=n.device AND n.netdevice_idx=i.netdevice AND i.ip=%s", (str(server_ipv4)))
        if req.dc.rowcount == 1:
            full_server_name = req.dc.fetchone()["name"]
    server_name = full_server_name.split(".")[0]
    conf["server_name"] = server_name
    cg_vars = device_variable.objects.filter(Q(device__device_group__cluster_device_group=True))
    for cg_var in cg_vars:
        conf["cluster_variables"][cg_var.name] = cg_var
##    print cg_vars
##    req.dc.execute("SELECT dv.* FROM device d, device_group dg, device_variable dv WHERE d.device_group=dg.device_group_idx AND dg.cluster_device_group")
##    for db_rec in req.dc.fetchall():
##        conf["cluster_variables"][db_rec["name"]] = db_rec
    if not conf["cluster_variables"].has_key("CLUSTER_NAME"):
        conf["cluster_variables"]["CLUSTER_NAME"] = device_variable(val_str="ClusterName not set")
    return conf

def find_server_routes(req, when):
    if req.session_data:
        del_s_routes = False
        if req.session_data.has_property("server_routes_build_time"):
            # check change of hopcount_table
            if req.conf["cluster_variables"].has_key("hopcount_table_build_time"):
                rb_time, ht_time = (req.session_data.get_property("server_routes_build_time"),
                                    time.mktime(req.conf["cluster_variables"]["hopcount_table_build_time"].val_date.timetuple()))
                if rb_time <= ht_time:
                    del_s_routes = True
        else:
            del_s_routes = True
        if del_s_routes and req.session_data.has_property("server_routes"):
            req.session_data.del_property("server_routes")
        if req.session_data.get_property("signal_other_sessions", 0):
            import session_handler
            req.session_data.del_property("signal_other_sessions")
            # signal all other active sessions but mine
            req.dc.execute("UPDATE session_data SET rebuild_server_routes = 1 WHERE NOT logout_time AND session_id != %s", req.session_data.get_session_id())
            # set flags for all other shm-sessions
            all_shms = session_handler.get_act_shm_dict()
            for key, value in all_shms.iteritems():
                value.set_flags(value.get_flags() | session_handler.SHM_FLAG_REBUILD_SERVER_ROUTES)
        if req.session_data.has_property("server_routes"):
            req.conf["server"] = req.session_data.get_property("server_routes")
        else:
            req.conf["server"] = {}
            try:
                my_dev = device.objects.get(name=req.conf["server_name"])
            except device.DoesNotExist:
                my_dev = None
            if my_dev:
                s_time = time.time()
                # local server netdevices
                # get all device/config pairs with an 'server'-attribute
                sql_2_str = "SELECT d.device_idx, d.name AS dev_name, c2.name AS conf_name FROM " + \
                            "device_config dc, new_config c, device d INNER JOIN device_group dg LEFT JOIN " + \
                            "device md ON (md.device_group_id=dg.device_group_idx AND md.device_idx=dg.device) LEFT JOIN " + \
                            "device_config dc2 ON (dc2.device_id=d.device_idx OR dc2.device_id=md.device_idx) LEFT JOIN " + \
                            "new_config c2 ON c2.new_config_idx=dc2.new_config_id WHERE dc.new_config_id=c.new_config_idx AND " + \
                            "d.device_group_id=dg.device_group_idx AND (dc.device_id=d.device_idx OR dc.device_id=md.device_idx) AND " + \
                            "c.name='server' AND (c2.name LIKE('%server%') OR c2.name='nagios_master') ORDER BY d.name, c2.name"
                #print sql_2_str
                #req.dc.execute(sql_2_str)
                c_list = device_config.objects.filter(
                    (Q(config__name="nagios_master") | Q(config__name__icontains="server"))
                    ).select_related("config", "device").order_by("device__name", "config__name")
                server_dict = {}
                #print req.dc.rowcount
                #for db_rec in req.dc.fetchall():
                #    #print "*", db_rec
                #    server_dict.setdefault(db_rec["device_idx"], {"name"       : db_rec["dev_name"],
                #                                                  "configs"    : [],
                #                                                  "ips"        : {},
                #                                                  "netdevices" : #{}})["configs"].append(db_rec["conf_name"])
                for c_entry in c_list:
                    server_dict.setdefault(c_entry.device_id,
                                           {"name"       : c_entry.device.name,
                                            "configs"    : [],
                                            "ips"        : {},
                                            "netdevices" : {}})["configs"].append(c_entry.config.name)
                # get all ip-addresses 
                all_nds = []
                if server_dict.keys():
##                    sql_3_str = "SELECT i.ip, n.netdevice_idx, n.device_id, nt.identifier FROM " + \
##                                "netdevice n, netip i, network nw, network_type nt WHERE nw.network_type_id=nt.network_type_idx AND i.network_id=nw.network_idx AND i.netdevice_id=n.netdevice_idx AND (%s)" % (" OR ".join(["n.device_id=%d" % (x) for x in server_dict.keys()]))
##                    req.dc.execute(sql_3_str)
                    all_ips = net_ip.objects.filter(Q(netdevice__device__in=server_dict.keys())).select_related("netdevice", "netdevice__device", "network__network_type")
                    for db_rec in all_ips:
                        server_dict[db_rec.netdevice.device_id]["ips"].setdefault(
                            db_rec.network.network_type.identifier, []).append((db_rec.netdevice_id, db_rec.ip))
                        server_dict[db_rec.netdevice.device_id]["netdevices"].setdefault(
                            db_rec.netdevice_id, {"ips"    : {},
                                                  "values" : []})["ips"][db_rec.ip] = db_rec.network.network_type.identifier
                        if db_rec.netdevice_id not in all_nds:
                            all_nds.append(db_rec.netdevice_id)
                # get all connected devices with netdevices
                if all_nds:
                    all_hops = hopcount.objects.filter(
                        Q(d_netdevice__in=all_nds)).select_related("d_netdevice", "d_netdevice__device").order_by("value", "d_netdevice")
##                    sql_4_str = "SELECT DISTINCT h.value, n2.device_id, n2.netdevice_idx FROM " + \
##                                "device d, netdevice n, hopcount h LEFT JOIN netdevice n2 ON n2.netdevice_idx=h.d_netdevice_id WHERE h.s_netdevice_id=n.netdevice_idx AND n.device_id=d.device_idx AND d.name='%s' AND (%s) ORDER BY h.value, h.d_netdevice_id" % (req.conf["server_name"], " OR ".join(["h.d_netdevice_id=%d" % (x) for x in all_nds]))
##                    req.dc.execute(sql_4_str)
                    for db_rec in all_hops:
                        server_dict[db_rec.d_netdevice.device_id]["netdevices"][db_rec.d_netdevice_id]["values"].append(db_rec.value)
                for dev_idx, dev_stuff in server_dict.iteritems():
                    # search nearest netdevice
                    min_value = None
                    for nd_idx, nd_stuff in dev_stuff["netdevices"].iteritems():
                        if nd_stuff["values"]:
                            act_min_value = min(nd_stuff["values"])
                            if min_value is None or act_min_value < min_value:
                                min_value, nearest_nd_idx = (act_min_value, nd_idx)
                    if min_value is not None:
                        nearest_nd = dev_stuff["netdevices"][nearest_nd_idx]
                        # get nearest ip-value
                        nearest_ip = None
                        for net_type in ["l", "p", "o", "s", "b"]:
                            if net_type in nearest_nd["ips"].values():
                                nearest_ip = nearest_nd["ips"].keys()[0]
                                break
                        if nearest_ip:
                            for conf in dev_stuff["configs"]:
                                req.conf["server"].setdefault(conf, {}).setdefault(dev_stuff["name"], nearest_ip)
                #pprint.pprint(req.conf["server"])
                req.session_data.set_property("server_routes", req.conf["server"])
                req.session_data.set_property("server_routes_build_time", time.time())
                #print "***", time.time()-s_time
                #print conf["server"]
                #pprint.pprint(req.conf["server"])
                if req.user_info and req.user_info.capability_ok("sql"):
                    req.info_stack.add_ok("Rebuilt server_routes [%s page] in %.2f seconds (%s and %s found)" % (when,
                                                                                                                 time.time() - s_time,
                                                                                                                 logging_tools.get_plural("server_type", len(req.conf["server"].keys())),
                                                                                                                 logging_tools.get_plural("server", len(server_dict.keys()))), "conf")
            else:
                if req.user_info:
                    if device.objects.all().count():
                        req.info_stack.add_error("Cannot rebuild server_routes (%s): failure: cannot determine webfrontend-host (check /etc/apache*/httpd.conf or /etc/sysconfig/apache2, name found there is '%s', used name is '%s')" % (
                            when,
                            req.environ["SERVER_NAME"],
                            req.conf["server_name"]),
                                                 "conf")
                    else:
                        req.info_stack.add_error(
                            "Cannot rebuild server_routes (%s): no devices defined" % (when),
                            "conf")

def fill_dict(val_dict, key_list, old_val_dict=None):
    new_dict = {}
    for f_key in [x for x in key_list if not x.endswith("_idx")]:
        if old_val_dict is None:
            if val_dict.has_key(f_key):
                new_dict[f_key] = val_dict[f_key]
        elif old_val_dict.has_key(f_key):
            if not val_dict.has_key(f_key):
                pass
            elif val_dict.get(f_key, old_val_dict[f_key]) != old_val_dict[f_key]:
                new_dict[f_key] = val_dict[f_key]
    return new_dict
    
def rescan_files(req):
    load_times = 0.0
    #old_capg_dict, old_cap_dict = ({}, {})
    cap_keys  = ["name", "priority", "description", "defvalue", "enabled",
                 "mother_capability", "mother_capability_name",
                 "left_string", "right_string",
                 "capability_idx", "modulename"]
    # remove netbotz-config, cluster-contact, application install
    capability.objects.filter(Q(name__in=["ac", "cnc", "nbc", "ai"]) | Q(description="unset")).delete()
    # ignore handling of capabilities, FIXME
    return
    # read old cap_dict
    req.dc.execute("SELECT %s FROM capability c " % (", ".join(["c.%s" % (x) for x in cap_keys])))
    old_cap_dict = dict([(db_rec["name"], dict([(key, db_rec[key]) for key in cap_keys])) for db_rec in req.dc.fetchall()])
    #pprint.pprint(old_cap_dict)
    dir_name = os.path.dirname(req.environ["SCRIPT_FILENAME"])
    # dict of found names (name -> mod_name)
    found_dict = {}
    for entry in os.listdir(dir_name):
        if entry.endswith(".py") and not entry.startswith("sub_"):
            mod_name = entry[:-3]
            act_l_time = time.time()
            try:
                mod = __import__(mod_name, globals(), locals(), ["module_info"])
            except ImportError:
                pass
            except AssertionError:
                pass
            else:
                #if DEBUG:
                #    mod = reload(mod)
                load_times += time.time() - act_l_time
                if "module_info" in dir(mod):
                    cap_dict = mod.module_info()
                    for cap_name, cap_stuff in cap_dict.iteritems():
                        if cap_name in found_dict.keys():
                            print "Capability %s found in file %s already defined in file %s" % (cap_name,
                                                                                                 mod_name,
                                                                                                 found_dict[cap_name])
                        else:
                            found_dict[cap_name] = mod_name
                            cap_stuff["defvalue"] = cap_stuff.get("default", 0)
                            if cap_stuff.has_key("capability_group_name"):
                                cap_stuff["mother_capability_name"] = cap_stuff["capability_group_name"]
                                del cap_stuff["capability_group_name"]
                            if cap_stuff.has_key("mother_capability_name"):
                                cap_stuff["modulename"] = mod_name
                            cap_stuff["name"] = cap_name
                            if old_cap_dict.has_key(cap_name):
                                new_dict = fill_dict(cap_stuff, cap_keys, old_cap_dict[cap_name])
                                if new_dict:
                                    #print "**", new_dict
                                    new_keys = new_dict.keys()
                                    sql_str, sql_tuple = ("UPDATE capability SET %s WHERE capability_idx=%d" % (", ".join(["%s=%%s" % (k) for k in new_keys]), old_cap_dict[cap_name]["capability_idx"]),
                                                          tuple([new_dict[k] for k in new_keys]))
                                    req.dc.execute(sql_str, sql_tuple)
                            else:
                                new_dict = fill_dict(cap_stuff, cap_keys)
                                new_dict["name"] = cap_name
                                new_keys = new_dict.keys()
                                sql_str, sql_tuple = ("INSERT INTO capability SET %s" % (", ".join(["%s=%%s" % (k) for k in new_keys])),
                                                      tuple([new_dict[k] for k in new_keys]))
                                #print "in", sql_str, sql_tuple
                                req.dc.execute(sql_str, sql_tuple)
                                # to prevent double inserts
                                old_cap_dict[cap_name] = new_dict
    # link mother-capabilites
    req.dc.execute("SELECT c1.capability_idx, c2.name, c2.mother_capability, c2.mother_capability_name, c2.capability_idx AS c2idx FROM capability c1 LEFT JOIN capability c2 ON c2.mother_capability_name=c1.name WHERE c2.mother_capability_name LIKE ('%')")
    new_mc_dict = {}
    for db_rec in req.dc.fetchall():
        if db_rec["mother_capability"] != db_rec["capability_idx"]:
            new_mc_dict.setdefault(db_rec["capability_idx"], []).append(db_rec["c2idx"])
    for mc_idx, idx_fields in new_mc_dict.iteritems():
        sql_str = "UPDATE capability SET mother_capability=%d WHERE %s" % (mc_idx, " OR " .join(["capability_idx=%d" % (x) for x in idx_fields]))
        req.dc.execute(sql_str)
    # set all capabilites for group admin if none are set
    req.dc.execute("SELECT dg.ggroup_idx, gc.ggroup FROM ggroup dg LEFT JOIN ggroupcap gc ON gc.ggroup=dg.ggroup_idx WHERE dg.ggroupname='admin'")
    if req.dc.rowcount:
        admin_part = req.dc.fetchone()
        admin_idx = admin_part["ggroup_idx"]
        if not admin_part["ggroup"]:
            req.dc.execute("DELETE FROM ggroupcap WHERE ggroup=%d" % (admin_idx))
            req.dc.execute("SELECT capability_idx FROM capability")
            if req.dc.rowcount:
                req.dc.execute("INSERT INTO ggroupcap VALUES%s" % ("," .join(["(0, %d, %d, null)" % (admin_idx, x["capability_idx"]) for x in req.dc.fetchall()])))
    #print "***", time.time() - start_time, load_times
    
##def make_basic_entries(req, def_admin, def_passwd):
##    req.info_stack.add_ok("Generating standard table entries", "setup")
##    req.info_stack.add_ok("creating default group/user with all rights", "setup")
    # now handled via commandline and permissions
##    req.dc.execute("INSERT INTO ggroup SET active=1, ggroupname='admin', gid=666, respemail='lang-nevyjel@init.at', respvname='Andreas', respnname='Lang-Nevyjel', resptitan='DI Dr.'")
##    ggroup_idx = req.dc.insert_id()
##    req.dc.execute("INSERT INTO user SET active=1, login=%s, uid=666, ggroup=%s, useremail='lang-nevyjel@init.at', cluster_contact=1, password=%s", (def_admin or "admin",
##                                                                                                                                                     ggroup_idx,
##                                                                                                                                                     crypt.crypt(def_passwd or "init4u",
##                                                                                                                                                                 "".join([chr(random.randint(97, 122)) for x in range(16)]))))
##    # fetch capabilities
##    req.dc.execute("SELECT c.capability_idx FROM capability c")
##    if req.dc.rowcount:
##        req.dc.execute("INSERT INTO ggroupcap VALUES%s" % (",".join(["(0, %d, %d, null)" % (ggroup_idx, x["capability_idx"]) for x in req.dc.fetchall()])))
##    req.info_stack.add_ok("@creating standard tables", "setup")
##    req.dc.execute("INSERT INTO device_type VALUES%s" % (",".join(["(0, '%s', '%s', null)" % (st, lt) for st, lt in [("H"  , "Host"             ),
##                                                                                                                     ("AM" , "APC Masterswitch" ),
##                                                                                                                     ("NB" , "Netbotz"          ),
##                                                                                                                     ("S"  , "Manageable Switch"),
##                                                                                                                     ("R"  , "Raid box"         ),
##                                                                                                                     ("P"  , "Printer"          ),
##                                                                                                                     ("MD" , "Meta device"      ),
##                                                                                                                     ("IBC", "IBM Blade Center" )]])))
    # old config-types
##    req.dc.execute("INSERT INTO config_type VALUES%s" % (",".join(["(0, '%s', '%s', '', null)" % (lt, st) for st, lt in [("s", "Server properties"  ),
##                                                                                                                         ("n", "Node properties"    ),
##                                                                                                                         ("h", "Hardware properites"),
##                                                                                                                         ("e", "Export entries"     )]])))
    # partition_fs
##    req.dc.execute("INSERT INTO `partition_fs` VALUES (1,'reiserfs','f','ReiserFS Filesystem','83','2006-06-01 09:44:27'),(2,'ext2','f','Extended 2 Filesystem','83','2006-06-01 09:44:27')," \
## "(3,'ext3','f','Extended 3 Filesystem','83','2006-06-01 09:44:27'),(4,'swap','s','SwapSpace','82','2006-06-01 09:44:27'),(5,'ext','e','Extended Partition','f','2006-06-01 09:44:27'),(6,'empty','d','Empty Partition','0','2006-06-01 09:44:27'),(7,'lvm','l','LVM Partition','8e','2007-06-08 08:21:19')")
    # log status
##    req.dc.execute("INSERT INTO log_status VALUES%s" % (",".join(["(0, '%s', %d, '%s', null)" % (st, sev, lt) for st, sev, lt in [("c", 200, "critical"),
##                                                                                                                                  ("e", 100, "error"   ),
##                                                                                                                                  ("w",  50, "warning" ),
##                                                                                                                                  ("i",   0, "info"    ),
##                                                                                                                                  ("n", -50, "notice"  )]])))
    # hardware entry types
##    req.dc.execute("INSERT INTO hw_entry_type VALUES%s" % (",".join(["(0, '%s', '%s', '%s', '%s', '%s', '%s', null)" % (hw_id, descr, ia0d, ia1d, sa0d, sa1d) for
##                                                                     hw_id, descr, ia0d, ia1d, sa0d, sa1d in [("cpu"   , "CPU"         , "Speed in MHz"       , ""              , "Model Type" , ""),
##                                                                                                              ("mem"   , "Memory"      , "Phyiskal Memory"    , "Virtual Memory", ""           , ""),
##                                                                                                              ("disks" , "Harddisks"   , "Number of harddisks", "total Size"    , ""           , ""),
##                                                                                                              ("cdroms", "CDRoms"      , "Number of CD-Roms"  , ""              , ""           , ""),
##                                                                                                              ("gfx"   , "Graphicscard", ""                   , ""              , "Type of Gfx", "")]])))
##    # SNMP classes
##    req.dc.execute("INSERT INTO snmp_class SET name='default_class', snmp_version=2, descr='Standard Class for SNMP-devices (v2c)'")
##    req.dc.execute("INSERT INTO snmp_class SET name='default_class', snmp_version=1, descr='Standard Class for SNMP-devices (v1)'")
##    # device classes
##    req.dc.execute("INSERT INTO device_class SET classname='normal'")
##    # device location
##    req.dc.execute("INSERT INTO device_location SET location='room00'")
    # user log source
##    req.dc.execute("INSERT INTO log_source SET identifier='user', name='Cluster user', description='Clusteruser'")
    # target states
##    req.dc.execute("INSERT INTO status VALUES%s" % (",".join(["(0, '%s', %d, null)" % (stat, p_link) for stat, p_link in [("memtest"           , 0),
##                                                                                                                          ("boot_local"        , 0),
##                                                                                                                          ("boot_clean"        , 1),
##                                                                                                                          ("installation_clean", 1),
##                                                                                                                          ("boot"              , 1),
##                                                                                                                          ("installation"      , 1)]])))
    # generic stuff
##    req.dc.execute("INSERT INTO genstuff SET name='AUTO_RELOAD', description='default auto_reload time', value='60'")
    
def log_handler(log_stuff, req):
    max_len = 800
    src, what, diff_time = log_stuff
    req.sql_exec_time += diff_time
    for p0, p1 in ([("\\", r"\ "),
                    ("|" , "| ")]):
        what = what.replace(p0, p1)
    if len(what) > max_len:
        what = "%s *** %s left" % (what[:max_len],
                                   logging_tools.get_plural("byte", len(what) - max_len))
    req.sql_stack.log_ok(("%s (%s): %s" % (logging_tools.get_diff_time_str(diff_time),
                                           src,
                                           what), "sql"))

def err_handler(log_stuff, req):
    src, what, diff_time = log_stuff
    req.info_stack.add_error("%s %s" % (str(src), str(what)), "error")
    
def handle_normal_module_call(req, module_name):
    # import modules
    import index_page
    import functions
    import session_handler
    import html_tools
    # init html_tools
    html_tools.init_html_vars()
    # info message stack
    req.info_stack = html_tools.message_log()
    # sql message stack
    req.sql_stack  = html_tools.message_log()
    # sql execution time
    req.sql_exec_time = 0.0
    if mysql_tools:
        dbcon = mysql_tools.dbcon_container(with_logging=True, add_data=req, log_handler=log_handler, err_handler=err_handler)
    else:
        req.write("<br>mysql_tools not found<br>")
        return
    try:
        dc = dbcon.get_connection("cluster_full_access")
    except:
        req.write("<br>Unable to initialise a database connection: %s<br>" % (process_tools.get_except_info()))
        del dbcon
        return
    req.dbcon = dbcon
    req.dc = dc
    req.conf = read_standard_config(req)
    # clear user_info
    req.user_info = None
    # check for session
    if req.sys_args.has_key(SESSION_ID_NAME):
        session_handler.read_session(req, req.sys_args[SESSION_ID_NAME])
    else:
        return HttpResponseRedirect(reverse("session:logout"))
        req.session_data = None
    special_module = module_name.startswith("fetch")
    no_auth_required = module_name in ["fetch_xml"]
    if not special_module:
        # write html-header
        functions.html_head(req)
    # which page to display
    if module_name == "logincheck":
        req.conf["genstuff"]["AUTO_RELOAD"] = 30
        # set to one if we directly continue to the index-page
        pass_through = False
        if not req.session_data:
            #req.dc.execute("SELECT u.login FROM user u LIMIT 1")
            #if not req.dc.rowcount:
            #    make_basic_entries(req, req.sys_args.get("username", "admin"), req.sys_args.get("password", "init4u"))
            # check for given username and password
            if not req.sys_args.get("username", "") or not req.sys_args.get("password", ""):
                if req.sys_args.has_key("username") or req.sys_args.has_key("password"):
                    req.info_stack.add_error("Authentication not possible: username or password not given", "auth")
                    req.conf["genstuff"]["RELOAD_TARGET"] = "index.py"
                else:
                    pass_through = True
            else:
                sys_user_name = req.sys_args["username"]
                # FIXME, contains is not a good option here to deal with aliases (needed for LH / Nenzing)
                user_info = user.objects.filter(Q(active=True) & Q(group__active=True) & (Q(login=sys_user_name) | Q(aliases__contains=sys_user_name))).select_related("group")
                if user_info:
                    user_info = user_info[0]
                    if user_info.aliases is None:
                        user_info.aliases = ""
                        user_info.save()
                    db_aliases = [x for x in user_info.aliases.strip().split() if x]
                    if sys_user_name in db_aliases or sys_user_name == user_info.login:
                        if crypt.crypt(req.sys_args["password"], user_info.password) == user_info.password:
                            # check for invalid passwords
                            if req.sys_args["password"] in ["init4u"]:
                                new_pwd = process_tools.create_password(length=8)
                                req.info_stack.add_error("Invalid password, changed to '%s', please login with new password" % (new_pwd), "auth")
                                req.conf["genstuff"]["RELOAD_TARGET"] = "index.py"
                                req.dc.execute("UPDATE user SET password=%s WHERE user_idx=%s", (crypt.crypt(new_pwd, "".join([chr(random.randint(97, 122)) for x in range(16)])),
                                                                                                 user_info["user_idx"]))
                            else:
                                alias_login = sys_user_name != user_info.login
                                sess_id = "".join([chr(random.randint(97, 122)) for x in range(16)])
                                sess_dict = {"session_id" : sess_id}
                                session_handler.init_session(req, sess_id, user_info, sess_dict)
                                pass_through = True
                                rescan_files(req)
                        else:
                            req.info_stack.add_error("Authentication not possible: username '%s' not valid or invalid password" % (sys_user_name), "auth")
                            req.conf["genstuff"]["RELOAD_TARGET"] = "index.py"
                    else:
                        # parse error in LIKE-statements above
                        req.info_stack.add_error("Authentication not possible: username '%s' not valid or invalid password" % (sys_user_name), "auth")
                        req.conf["genstuff"]["RELOAD_TARGET"] = "index.py"
                else:
                    req.info_stack.add_error("Authentication not possible: username '%s' not found or not active" % (sys_user_name), "auth")
                    req.conf["genstuff"]["RELOAD_TARGET"] = "index.py"
                    # check for inserting of default tables
        else:
            session_handler.delete_session(req)
            pass_through = True
        if not pass_through:
            functions.write_header(req)
            functions.write_body(req)
        else:
            #del req.conf["AUTO_RELOAD"]
            req.module_name = "index"
            module_name = req.module_name
            req.title = req.module_name
    index_page.build_cap_dict(req)
    #find_server_routes(req, "before")
    if module_name in ["logincheck", "index"]:
        return HttpResponseRedirect(reverse("main:index"))
    else:
        # build list of allowed modules
        #module_list = req.cap_stack.get_long_modules_names()
        #if module_name in module_list or special_module:
        if True:
            s_path = "/srv/www/htdocs/python"
            if s_path not in sys.path:
                sys.path.append(s_path)
            try:
                mod = __import__(module_name, globals(), locals(), [])
            except ImportError, why:
                req.info_stack.add_error("Module %s not found (ImportError '%s'), using index" % (module_name, str(why)), "internal")
                module_name = "index"
                req.module_name = module_name
            else:
                process_mod = True
                if req.user_info or no_auth_required:
                    if not special_module:
                        #short_name = req.cap_stack[module_name].name
                        if True:#req.user_info.capability_ok(short_name):
                            #req.user_info.set_act_short_module_name(short_name)
                            act_p_list = req.session_data.get_property("pages", ["index"])
                            if module_name in act_p_list:
                                act_p_list.remove(module_name)
                            act_p_list.append(module_name)
                            # up to 6 quick-links in headline
                            while len(act_p_list) > 5:
                                act_p_list.pop(1)
                            req.session_data.set_property("pages", act_p_list)
                            vars_to_add = []
                            for var_fll in VARS_FOR_LINK_LINE:
                                if req.sys_args.has_key(var_fll):
                                    if type(req.sys_args[var_fll]) == type([]):
                                        vars_to_add.extend(["%s[]=%s" % (var_fll, x) for x in req.sys_args[var_fll]])
                                    else:
                                        vars_to_add.append("%s=%s" % (var_fll, req.sys_args[var_fll]))
                            functions.write_link_line(req, vars_to_add)
                        else:
                            process_mod = False
                    if process_mod:
                        req.conf["process_start_time"] = time.time()
                        try:
                            if no_auth_required:
                                mod.process_page(req)
                            else:
                                if req.user_info.capability_ok("prf") and profile:
                                    profile_name = "/tmp/.webfrontend_profile_%s" % (req.session_data.get_session_id())
                                    prof = hotshot.Profile(profile_name)
                                    prof.runcall(mod.process_page, req)
                                    prof.close()
                                    req.conf["stats"] = hotshot.stats.load(profile_name)
                                    try:
                                        os.unlink(profile_name)
                                    except:
                                        pass
                                else:
                                    mod.process_page(req)
                        except:
                            tb = sys.exc_info()[2]
                            except_info = process_tools.exception_info()
                            out_lines = ["Exception in module '%s':" % (module_name)]
                            req.info_stack.add_error(out_lines[-1], "internal")
                            for line in except_info.log_lines:
                                req.info_stack.add_warn(line, "traceback")
                                out_lines.append(line)
                            # write to logging-server
                            err_h = process_tools.io_stream("/var/lib/logging-server/py_err")
                            err_h.write("\n".join(out_lines))
                            err_h.close()
                        req.conf["process_end_time"] = time.time()
                    else:
                        req.info_stack.add_error("You are not allowed to access module %s (%s), using index" % (module_name,
                                                                                                                short_name), "internal")
                        module_name = "index"
                        req.module_name = module_name
                else:
                    req.info_stack.add_error("You are not authenticated", "internal")
                    module_name = "index"
                    req.module_name = module_name
        else:
            req.info_stack.add_error("Module %s not known, using index" % (module_name), "internal")
            module_name = "index"
            req.module_name = module_name
##    if module_name == "index":
##        index_page.process_page(req)
    if not special_module:
        find_server_routes(req, "after")
        # check for cluster-support
        req.cluster_support = user.objects.exclude(Q(useremail=""))
        session_handler.update_session(req)
        functions.write_footer(req)
        functions.write_error_footer(req)
        functions.write_simple_footer(req)
    # remove reference
    req.dc.release()
    del req.dc
    req.dbcon.close()
    del req.dbcon
    #return apache.OK
    return None
