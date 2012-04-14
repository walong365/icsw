#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011 Andreas Lang-Nevyjel, init.at
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
""" beautiful display of cluster status """

import functions
import logging_tools
import html_tools
import tools
import os
import array
import datetime
import pprint
try:
    import infograph
except ImportError:
    infograph = None
    
def module_info():
    return {"sc" : {"description"           : "Clusterinfo",
                    "default"               : True,
                    "enabled"               : True,
                    "left_string"           : "Status",
                    "right_string"          : "Information about the Cluster status",
                    "priority"              : -100,
                    "capability_group_name" : "info"}}

NAG_HOST_UNKNOWN     = -1
NAG_HOST_UP          = 0
NAG_HOST_DOWN        = 1
NAG_HOST_UNREACHABLE = 2

NAG_SERVICE_IGNORED  = -2
NAG_SERVICE_UNKNOWN  = -1
NAG_SERVICE_OK       = 0
NAG_SERVICE_WARNING  = 1
NAG_SERVICE_CRITICAL = 2

NO_DATA_CLASS = "center"

def get_diff_time_str(dt_check, dt_now):
    if dt_check.year == 1970:
        return "never"
    diff_days = abs((datetime.datetime(dt_now.year,
                                       dt_now.month,
                                       dt_now.day) - datetime.datetime(dt_check.year,
                                                                       dt_check.month,
                                                                       dt_check.day)).days)
    if diff_days == 0:
        td_diff = (dt_now.replace(2005, 1, 1) - dt_check.replace(2005, 1, 1)).seconds
        if td_diff > 600:
            return "today, %s" % (dt_check.strftime("%H:%M:%S"))
        else:
            mins = int(td_diff / 60)
            secs = td_diff - 60 * mins
            return "today, %s ago" % ("%02d:%02d" % (mins, secs))
    elif diff_days == 1:
        return "yesterday, %s" % (dt_check.strftime("%H:%M:%S"))
    else:
        return dt_check.strftime("%a, %d. %b %Y, %H:%M:%S")
    
def get_diff_time_str_2(dt_check, dt_now):
    if dt_check.year == 1970:
        return "---"
    diff_time = dt_now - dt_check
    diff_days, diff_seconds = (diff_time.days, diff_time.seconds)
    ret_f = []
    if diff_days:
        ret_f.append(logging_tools.get_plural("day", diff_days))
    hours = int(diff_seconds / 3600)
    mins = int((diff_seconds - 3600 * hours) / 60)
    secs = diff_seconds - 3600 * hours - 60 * mins
    ret_f.append("%02d:%02d:%02d" % (hours, mins, secs))
    return ", ".join(ret_f)
    
class cluster(object):
    def __init__(self, action_log):
        self.__device_groups = {}
        self.__action_log = action_log
        # lookuptable device_name / device_idx -> device_group_name
        self.__dg_lut, self.__dg_idx_lut = ({}, {})
        # services, organized as {service_type -> {dict of description}}
        self.__services = {}
        # services are referenced via their description (FIXME)
        self.__descr_lut = {}
        self.__command_names_handled, self.__service_descriptions_handled = ([], [])
        # dg_names, d_names
        self.__dg_names, self.__d_names = ([], [])
        # dict device(group)_names -> idx and reverse
        self.__device_group_dict, self.__device_dict = ({}, {})
        self.__device_group_lut , self.__device_lut  = ({}, {})
        # init forbidden list
        self.set_forbidden_ngcct_idxs([])
        # init option field
        self.__options = {}
    def set_option(self, key, value):
        ok_list = ["ignore_timeouts"]
        if key in ok_list:
            self.__options[key] = value
        else:
            self.__action_log.add_error("Option for Cluster %s not known, should be one of %s" % (key,
                                                                                                  ", ".join(ok_list)),
                                        "internal")
    def get_num_device_groups(self):
        return len(self.__dg_names)
    def get_num_devices(self):
        return len(self.__d_names)
    def set_forbidden_ngcct_idxs(self, f_list):
        self.__forbidden_ngcct_idxs = f_list
        self.__forbidden_descrs = []
    def build_config_struct(self, what):
        if what["ng_check_command_type_idx"] in self.__forbidden_ngcct_idxs:
            self.__forbidden_descrs.append(what["description"])
        # handle special types
        s_type = what["service_type"]
        if not self.__services.has_key(s_type):
            self.__services[s_type] = {}
        if what["check_command_name"] not in self.__command_names_handled:
            cc_name = what["check_command_name"]
            self.__command_names_handled.append(cc_name)
            if cc_name.count("@"):
                # can now only be DISC or NET
                what["description"] = cc_name.split("@")[1]
        if what["description"] not in self.__service_descriptions_handled:
            if what["ng_check_command_type_idx"] not in self.__forbidden_ngcct_idxs:
                s_descr = what["description"]
                if s_type == "load":
                    new_s = load_service(what)
                elif s_type == "uptime":
                    new_s = uptime_service(what)
                elif s_type == "network":
                    new_s = network_service(what)
                elif s_type == "memory":
                    new_s = memory_service(what)
                elif s_type == "hw/temp":
                    new_s = hw_temp_service(what)
                elif s_type == "hw/fan":
                    new_s = hw_fan_service(what)
                elif s_type == "disk/df":
                    new_s = disk_df_service(what)
                else:
                    new_s = service(what)
                new_s.set_options(self.__options)
                self.__descr_lut[s_descr] = new_s
                self.__services[s_type][s_descr] = new_s
            #print dict([(k, self.__services[k].keys()) for k in self.__services.keys()])
    def build_device_tree(self, what):
        d_id = what["identifier"]
        if d_id in ["H", "AM", "S", "R"]:
            dg_name, d_name = (what["dg_name"], what["name"])
            if not self.__device_groups.has_key(dg_name):
                new_dg = device_group(dg_name, what["device_group_idx"])
                self.__device_groups[dg_name] = new_dg
                self.__dg_names.append(dg_name)
                self.__dg_names.sort()
                self.__device_group_dict[dg_name] = what["device_group_idx"]
                self.__device_group_lut[what["device_group_idx"]] = dg_name
            self.__device_groups[dg_name].build_device_tree(what)
            self.__dg_lut[d_name] = self.__device_groups[dg_name]
            self.__dg_idx_lut[what["device_idx"]] = self.__device_groups[dg_name]
            self.__device_dict[d_name] = what["device_idx"]
            self.__device_lut[what["device_idx"]] = d_name
            self.__d_names.append(d_name)
            self.__d_names.sort()
    def feed_nagios_result(self, what):
        # feed point for NagiosV1.x (host status + service status)
        d_name = what["host_name"]
        descr = what["service_description"]
        p_output = what["plugin_output"]
        # cast binary to string
        if type(p_output) == type(array.array("c")):
            p_output = p_output.tostring()
        if not self.__descr_lut.has_key(descr):
            if descr.startswith("/"):
                # disk description, not handled right now
                p_output = "%s (%s)" % (p_output, descr)
                descr = "DISC"
            else:
                # net description
                descr = "NET"
        if self.__dg_lut.has_key(d_name):
            # host status
            self.__dg_lut[d_name].feed_nagios_result(what)
            # service status
            if self.__descr_lut.has_key(descr):
                self.__dg_lut[d_name].get_device(d_name).add_check()
                self.__descr_lut[descr].feed_nagios_result(what, p_output, what, self.__device_dict[d_name])
    def feed_nagios_host_result(self, what):
        # feed point for NagiosV2.x (only host status)
        d_name = what["host_name"]
        if self.__dg_lut.has_key(d_name):
            # host status
            self.__dg_lut[d_name].feed_nagios_result(what)
    def feed_nagios_service_result(self, what):
        # feed point for NagiosV2.x (only service status)
        d_name = what["host_name"]
        descr = what["service_description"]
        if descr in self.__forbidden_descrs:
            return
        p_output = what["plugin_output"]
        # cast binary to string
        if type(p_output) == type(array.array("c")):
            p_output = p_output.tostring()
        if not self.__descr_lut.has_key(descr):
            if descr.startswith("/"):
                # disk description, not handled right now
                p_output = "%s (%s)" % (p_output, descr)
                descr = "DISC"
            else:
                # net description
                descr = "NET"
        if self.__dg_lut.has_key(d_name):
            # service status
            if self.__descr_lut.has_key(descr):
                self.__dg_lut[d_name].get_device(d_name).add_check()
                self.__descr_lut[descr].feed_nagios_result(what, p_output, what, self.__device_dict[d_name])
    def get_device_group_by_device_name(self, d_name):
        return self.__dg_lut[d_name]
    def get_device_group_name(self, dg_idx):
        return self.__dg_lut[dg_idx]
    def get_device_name(self, d_idx):
        return self.__device_lut[d_idx]
    def get_device_group_names(self, dg_idxs):
        if dg_idxs:
            return sorted([v for k, v in self.__device_group_lut.iteritems() if k in dg_idxs])
        else:
            return self.__dg_names
    def get_device_names(self, d_idxs):
        if d_idxs:
            return sorted([v for k, v in self.__device_lut.iteritems() if k in d_idxs])
        else:
            return self.__d_names
    def get_device_group(self, dg_name):
        return self.__device_groups[dg_name]
    def get_device(self, d_name):
        return self.__dg_lut[d_name].get_device(d_name)
    def get_device_status_dict(self, d_idxs):
        ds_dict = {}
        for dg_name in self.__dg_names:
            for d_stat, d_names in self.__device_groups[dg_name].get_device_status_dict(d_idxs).iteritems():
                ds_dict.setdefault(d_stat, []).extend(d_names)
        return ds_dict
    def get_device_type_info(self):
        dt_dict = {}
        for d_group in self.__device_groups.values():
            for dt_type, names in d_group.get_device_type_dict().iteritems():
                dt_dict.setdefault(dt_type, []).extend(names)
        return ", ".join(["%d %s" % (len(dt_dict[k]), k) for k in sorted(dt_dict.keys())])
    def get_service_types(self):
        all_keys = []
        for key in self.__services.keys():
            if sum([value.get_num_host_results() for value in self.__services[key].values()]):
                all_keys.append(key)
        return all_keys
    def get_max_fan(self, d_idxs):
        # returns the maximum load for a given dg_name
        s_descrs = self.__services.get("hw/fan", {}).keys()
        max_fan = 0.
        for s_descr in s_descrs:
            for dev_key, dev_list in self.__descr_lut[s_descr].get_decoded_status_fields(d_idxs).iteritems():
                max_fan = max(max_fan, max([value["decoded_value"] for value in dev_list if value["decoded"]] + [0.]))
        return max_fan
    def get_max_temp(self, d_idxs):
        # returns the maximum load for a given dg_name
        s_descrs = self.__services.get("hw/temp", {}).keys()
        max_temp = 0.
        for s_descr in s_descrs:
            for dev_key, dev_list in self.__descr_lut[s_descr].get_decoded_status_fields(d_idxs).iteritems():
                max_temp = max(max_temp, max([value["decoded_value"] for value in dev_list if value["decoded"]] + [0.]))
        return max_temp
    def get_max_load(self, d_idxs):
        # returns the maximum load for a given dg_name
        s_descrs = self.__services.get("load", {}).keys()
        max_load = 0.
        for s_descr in s_descrs:
            for dev_key, dev_list in self.__descr_lut[s_descr].get_decoded_status_fields(d_idxs).iteritems():
                max_load = max(max_load, max([max(value["decoded_value"]) for value in dev_list if value["decoded"]] + [0.]))
        return max_load
    def get_max_net(self, d_idxs):
        # returns the maximum load for a given dg_name
        s_descrs = self.__services.get("network", {}).keys()
        max_net = 0.
        for s_descr in s_descrs:
            for dev_key, dev_list in self.__descr_lut[s_descr].get_decoded_status_fields(d_idxs).iteritems():
                max_net = max(max_net, max([max(value["decoded_value"]) for value in dev_list if value["decoded"]] + [0.]))
        return max_net
    def get_service_status(self, s_type, d_idxs):
        s_descrs = self.__services.get(s_type, {}).keys()
        ss_dict = {}
        for s_descr in s_descrs:
            for dev_key, dev_list in self.__descr_lut[s_descr].get_decoded_status_fields(d_idxs).iteritems():
                ss_dict.setdefault(dev_key, []).extend(dev_list)
        return ss_dict
    def get_service_status_2(self, s_types, d_idxs, stats_to_check):
        #if s_types == None:
        s_types = self.__services.keys()
        ss_dict = {}
        for s_type in s_types:
            for s_descr in self.__services[s_type].keys():
                for dev_key, dev_list in self.__descr_lut[s_descr].get_decoded_status_fields(d_idxs, stats_to_check).iteritems():
                    ss_dict.setdefault(s_type, {}).setdefault(s_descr, {}).setdefault(dev_key, []).extend(dev_list)
        return ss_dict
    def get_service_status_undecoded(self, s_types, d_idxs, stats_to_check=[]):
        if s_types == None:
            s_types = self.__services.keys()
        ss_dict = {}
        for s_type in s_types:
            for s_descr in self.__services[s_type].keys():
                for dev_key, dev_list in self.__descr_lut[s_descr].get_undecoded_status_fields(d_idxs, stats_to_check).iteritems():
                    ss_dict.setdefault(s_type, {}).setdefault(s_descr, {}).setdefault(dev_key, []).extend(dev_list)
        return ss_dict
    def get_device_idxs(self, dg_names, d_names):
        """ return all device idxs which are part of dg_name or are equal to d_names, if dg_name and d_names are
        empty return all device_idxs"""
        if not dg_names and not d_names:
            d_idxs = []
            for d_group in self.__device_groups.values():
                d_idxs.extend(d_group.get_device_idxs())
        elif dg_names:
            d_idxs = []
            for d_group in [self.__device_groups[x] for x in dg_names]:
                d_idxs.extend(d_group.get_device_idxs())
        else:
            d_idxs = [v for k, v in self.__device_dict.iteritems() if k in d_names]
        return d_idxs
    def get_up_device_idxs(self, d_idxs):
        return [x for x in d_idxs if self.__dg_idx_lut[x].get_device_by_idx(x).get_status() == NAG_HOST_UP]
    
class device_group(object):
    def __init__(self, name, idx):
        self.__name = name
        self.__device_names, self.__device_dict, self.__device_idx_lut, self.__device_lut = ([], {}, {}, {})
        self.__device_group_idx = idx
    def get_device_group_idx(self):
        return self.__device_group_idx
    def get_name(self):
        return self.__name
    def build_device_tree(self, what):
        d_name = what["name"]
        if not d_name in self.__device_names:
            self.__device_names.append(d_name)
            self.__device_names.sort()
            self.__device_idx_lut[d_name] = what["device_idx"]
            new_d = device(d_name, what["identifier"], what["device_idx"])
            self.__device_dict[d_name] = new_d
            self.__device_lut[what["device_idx"]] = new_d
    def get_device(self, d_name):
        return self.__device_dict[d_name]
    def get_device_by_idx(self, d_idx):
        return self.__device_lut[d_idx]
    def get_device_idxs(self):
        return [self.__device_idx_lut[n] for n in self.__device_names]
    def get_device_type_dict(self):
        dt_dict = {}
        for d_name, d_struct in self.__device_dict.iteritems():
            dt_dict.setdefault(d_struct.get_device_type(), []).append(d_name)
        return dt_dict
    def get_device_type_info(self):
        dt_dict = self.get_device_type_dict()
        return ", ".join([logging_tools.get_plural({"H" : "Host",
                                                    "S" : "Switch"}.get(k, k), len(dt_dict[k])) for k in sorted(dt_dict.keys())])
    def get_device_status_dict(self, d_idxs):
        ds_dict = {}
        for d_name, d_struct in self.__device_dict.iteritems():
            if self.__device_idx_lut[d_name] in d_idxs:
                for key, value in d_struct.get_device_status_dict(d_idxs).iteritems():
                    ds_dict.setdefault(key, []).extend(value)
        return ds_dict
    def feed_nagios_result(self, what):
        self.__device_dict[what["host_name"]].feed_nagios_result(what)

class device(object):
    # devices, only used to store the hoststatus
    def __init__(self, name, dev_type, dev_idx):
        self.__name = name
        self.__status = NAG_HOST_UNKNOWN
        self.__dev_type = dev_type
        self.__device_idx = dev_idx
        self.__num_checks = 0
    def add_check(self):
        self.__num_checks += 1
    def get_num_checks(self):
        return self.__num_checks
    def get_device_type(self):
        return self.__dev_type
    def get_status(self):
        return self.__status
    def feed_nagios_result(self, what):
        h_stat = what["host_status"]
        if self.__status == NAG_HOST_UNKNOWN:
            if type(h_stat) == type(0):
                # Nagios V2.x returns Integers
                self.__status = h_stat
            else:
                if h_stat == "UP":
                    self.__status = NAG_HOST_UP
                elif h_stat == "DOWN":
                    self.__status = NAG_HOST_DOWN
                elif h_stat == "UNREACHABLE":
                    self.__status = NAG_HOST_UNREACHABLE
    def get_device_status_dict(self, d_idxs):
        if self.__device_idx in d_idxs:
            return {self.__status : [self.__name]}
        else:
            return {}
    def get_device_idx(self):
        return self.__device_idx
            
class service(object):
    def __init__(self, sql_line):
        self.__description  = sql_line["description"]
        self.__service_type = sql_line["service_type"]
        self.__host_results = {}
        self.__decoded_idxs = []
    def set_options(self, opt_dict):
        self.option_dict = opt_dict
    def get_num_host_results(self):
        return len(self.__host_results.keys())
    def get_host_results(self):
        return self.__host_results
    def feed_nagios_result(self, what, output, db_rec, idx):
        s_stat = what["service_status"]
        if type(s_stat) == type(0):
            # Nagios V2.x returns the correct integer value
            pass
        else:
            if s_stat == "OK":
                s_stat = NAG_SERVICE_OK
            elif s_stat == "WARNING":
                s_stat = NAG_SERVICE_WARNING
            elif s_stat == "CRITICAL":
                s_stat = NAG_SERVICE_CRITICAL
            elif s_stat in ["UNKNOWN", "PENDING"]:
                s_stat = NAG_SERVICE_UNKNOWN
            else:
                print "*** Unknown service_status: %s ***" % (str(s_stat))
                s_stat = 66666
        is_timeout = len([True for ms in ["timed", "timeout"] if output.lower().count(ms)]) and True or False
        is_invalid = len([True for ms in ["invalid"] if output.lower().count(ms)]) and True or False
        self.__host_results.setdefault(idx, []).append({"state"             : is_timeout and self.option_dict["ignore_timeouts"] and NAG_SERVICE_IGNORED or s_stat,
                                                        "output"            : output,
                                                        "last_check"        : db_rec["last_check"],
                                                        "last_state_change" : db_rec["last_state_change"],
                                                        "timeout"           : is_timeout,
                                                        "invalid"           : is_invalid,
                                                        "decoded"           : False})
        self.__decoded_idxs = []
    def get_status_fields(self, idx_list):
        return dict([(x, self.__host_results[x]) for x in idx_list if self.__host_results.has_key(x)])
    def get_decoded_status_fields(self, idx_list, stats_to_check=[]):
        to_dc = [x for x in idx_list if not x in self.__decoded_idxs and x in self.__host_results.keys()]
        if to_dc:
            for rec in to_dc:
                self.decode_result(self.__host_results[rec])
        if stats_to_check == []:
            return dict([(x, self.__host_results[x]) for x in idx_list if self.__host_results.has_key(x)])
        else:
            return dict([(k, v) for k, v in [(x, [ab for ab in self.__host_results[x] if ab["state"] in stats_to_check]) for x in idx_list if self.__host_results.has_key(x)] if v])
    def get_undecoded_status_fields(self, idx_list, stats_to_check=[]):
        if stats_to_check == []:
            return dict([(x, self.__host_results[x]) for x in idx_list if self.__host_results.has_key(x)])
        else:
            return dict([(k, v) for k, v in [(x, [ab for ab in self.__host_results[x] if ab["state"] in stats_to_check]) for x in idx_list if self.__host_results.has_key(x)] if v])
    def decode_result(self, in_list):
        pass

class disk_df_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        for df_stuff in in_list:
            if df_stuff["output"].count("%"):
                df_split = df_stuff["output"].replace("(", "").replace(")", "").split()
                # try to be clever
                perc_index = df_split.index("%")
                df_rel = float(df_split[perc_index - 1])
                df_used, df_total = (self._scan_string(df_split[perc_index + 1], df_split[perc_index + 2][:-1]),
                                     self._scan_string(df_split[perc_index + 4], df_split[perc_index + 5][:-1]))
                df_stuff["decoded"] = True
                df_stuff["decoded_value"] = {"relative" : df_rel,
                                             "used"     : df_used,
                                             "total"    : df_total}
    def _scan_string(self, pfix, factor):
        return float(pfix) * {"k" : 1024,
                              "m" : 1024 * 1024,
                              "g" : 1024 * 1024 * 1024,
                              "t" : 1024 * 1024 * 1024 * 1024}.get(factor.lower(), 1.)
    
class hw_temp_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        for hw_temp_stuff in in_list:
            str_spl = hw_temp_stuff["output"].split()
            if len(str_spl) > 2 and str_spl[-1] == "C":
                hw_temp_stuff["decoded"] = True
                hw_temp_stuff["decoded_value"] = float(str_spl[-2])
    
class hw_fan_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        for hw_fan_stuff in in_list:
            str_spl = hw_fan_stuff["output"].split()
            if len(str_spl) > 2 and str_spl[-1] == "RPM":
                hw_fan_stuff["decoded"] = True
                hw_fan_stuff["decoded_value"] = float(str_spl[-2])
    
class load_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        for load_stuff in in_list:
            str_spl = load_stuff["output"].split()
            if len(str_spl) > 3:
                try:
                    str_f = [float(x) for x in str_spl[-3:]]
                except:
                    pass
                else:
                    load_stuff["decoded"] = True
                    load_stuff["decoded_value"] = str_f

class uptime_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        for load_stuff in in_list:
            if load_stuff["output"].count("min"):
                up_minutes = 0
                # at least we should find minutes
                str_spl = load_stuff["output"].split()
                prev_part = None
                for str_p in str_spl:
                    if str_p.count("day"):
                        up_minutes += 24 * 60 * int(prev_part)
                    elif str_p.count("hour"):
                        up_minutes += 60 * int(prev_part)
                    if str_p.count("min"):
                        up_minutes += int(prev_part)
                    prev_part = str_p
                load_stuff["decoded"] = True
                load_stuff["decoded_value"] = up_minutes

class network_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        for net_stuff in in_list:
            try:
                str_spl = net_stuff["output"].split(":")
                if len(str_spl) > 2:
                    str_spl.pop(0)
                    stuff = [float(s_num) * {"b"  : 1,
                                             "kb" : 1024,
                                             "mb" : 1024 * 1024,
                                             "gb" : 1024 * 1024 * 1024}[s_pf.lower()] for s_num, s_pf in [v.split(",")[-1][:-5].split() for k, v in zip(["rx", "tx"], str_spl[0:2])]]
                    if min(stuff) < 0:
                        pass
                    else:
                        net_stuff["decoded"] = True
                        net_stuff["decoded_value"] = stuff
            except:
                pass

class memory_service(service):
    def __init__(self, sql_line):
        service.__init__(self, sql_line)
    def decode_result(self, in_list):
        def str_to_int(s_num, s_pf):
            return int(float(s_num) * {"b" : 1,
                                       "k" : 1024,
                                       "m" : 1024 * 1024,
                                       "g" : 1024 * 1024 * 1024}[s_pf[0].lower()])
        for mem_stuff in in_list:
            try:
                str_spl = mem_stuff["output"].split(":")
                act_type = str_spl[1]
                act_dict = dict([(sub_type, {"rel" : int(perc),
                                             "abs" : str_to_int(size_num, size_pf)}) for perc, bla1, bla2, size_num, size_pf, sub_type in [y for y in [x.strip().split() for x in str_spl.pop().strip().split(",")] if len(y) == 6]])
            except:
                pass
            else:
                mem_stuff["decoded"] = True
                mem_stuff["decoded_value"] = act_dict

def get_short_uptime_str(uptime):
    # 1 month = 30 days
    if uptime > 30 * 24 * 60:
        return "> %dM" % (int(uptime / (30 * 24 * 60)))
    elif uptime > 7 * 24 * 60:
        return "> %dw" % (int(uptime / (7 * 24 * 60)))
    elif uptime > 24 * 60:
        return "> %dd" % (int(uptime / (24 * 60)))
    elif uptime > 60:
        return "> %dh" % (int(uptime / 60))
    else:
        return "%dm" % (uptime)
    
def get_device_status_string(ds_dict, du_dict):
    # thresholds
    UPT_ERROR, UPT_WARN, UPT_DEFAULT = (10, 60, 666666)
    # interpret uptime dict
    uptime_list = [rec[0]["decoded_value"] for rec in du_dict.itervalues() if rec and rec[0]["decoded"]] or [UPT_DEFAULT]
    min_uptime = min(uptime_list)
    if ds_dict.has_key(NAG_HOST_DOWN) or min_uptime < UPT_ERROR:
        td_state = "errorcenter"
    elif ds_dict.has_key(NAG_HOST_UNKNOWN) or ds_dict.has_key(NAG_HOST_UNREACHABLE) or min_uptime < UPT_WARN:
        td_state = "warncenter"
    else:
        td_state = "center"
    if len(ds_dict.keys()) == 1:
        act_key = ds_dict.keys()[0]
        state_str = {NAG_HOST_DOWN        : "down",
                     NAG_HOST_UP          : "up",
                     NAG_HOST_UNKNOWN     : "not set",
                     NAG_HOST_UNREACHABLE : "unreach"}[act_key]
        if len(ds_dict[act_key]) == 1:
            if min_uptime != UPT_DEFAULT and act_key == NAG_HOST_UP:
                # add uptime to single-host output if host is up
                stat_str = "is %s (%s)" % (state_str,
                                           get_short_uptime_str(min_uptime))
            else:
                stat_str = "is %s" % (state_str)
        else:
            stat_str = "all %d %s" % (len(ds_dict[act_key]), state_str)
    else:
        stat_str = ", ".join(["%d %s" % (len(ds_dict[s_ref]), what) for s_ref, what in [(NAG_HOST_DOWN       , "down"   ),
                                                                                        (NAG_HOST_UP         , "up"     ),
                                                                                        (NAG_HOST_UNKNOWN    , "not set"),
                                                                                        (NAG_HOST_UNREACHABLE, "unreach")] if ds_dict.has_key(s_ref)])
    return td_state, stat_str

def interpret_load_dict(l_dict, draw_dict, tot_max_load):
    min_nag_state, max_nag_state = (NAG_SERVICE_OK, NAG_SERVICE_OK)
    min_load = None
    for dev_idx, dev_list in l_dict.iteritems():
        for nag_f in dev_list:
            if nag_f["decoded"]:
                if min_load is None:
                    min_load = min(nag_f["decoded_value"])
                    mean_load = nag_f["decoded_value"]
                    max_load = max(nag_f["decoded_value"])
                else:
                    min_load = min(min_load, min(nag_f["decoded_value"]))
                    max_load = max(max_load, max(nag_f["decoded_value"]))
                    mean_load.extend(nag_f["decoded_value"])
                min_nag_state = min(min_nag_state, nag_f["state"])
                max_nag_state = max(max_nag_state, nag_f["state"])
    if min_load is None:
        td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
    else:
        if max_nag_state == NAG_SERVICE_CRITICAL:
            td_state = "errorcenter"
        elif min_nag_state == max_nag_state and min_nag_state == NAG_SERVICE_OK:
            td_state = "center"
        else:
            td_state = "warncenter"
        if len(mean_load) == 1:
            perc_vals = [min_load * 100 / tot_max_load]
        else:
            mean_load = sum(mean_load) / len(mean_load)
            perc_vals = [v * 100 / tot_max_load for v in [min_load, mean_load, max_load]]
            perc_vals.reverse()
        if draw_dict["DRAW_GFX"]:
            draw_dict["IG_STRUCT"].create_graph("load", dict([(k, (x, infograph.get_rgb_val(x, draw_dict["COLORPATH1"]))) for k, x in zip(range(len(perc_vals)), perc_vals)]))
            state_str = "<img src=\"../graphs/%s\"/>" % (draw_dict["IG_STRUCT"].get_last_name())
        else:
            state_str = "%.2f / %.2f / %.2f" % (min_load, mean_load, max_load)
    return [(td_state, state_str)]

def interpret_hw_temp_dict(l_dict, draw_dict, tot_max_temp):
    min_nag_state, max_nag_state = (NAG_SERVICE_OK, NAG_SERVICE_OK)
    min_temp = None
    for dev_idx, dev_list in l_dict.iteritems():
        for nag_f in dev_list:
            if nag_f["decoded"]:
                if min_temp is None:
                    min_temp, max_temp, mean_temp = (nag_f["decoded_value"],
                                                     nag_f["decoded_value"],
                                                     [nag_f["decoded_value"]])
                else:
                    min_temp = min(min_temp, nag_f["decoded_value"])
                    max_temp = max(max_temp, nag_f["decoded_value"])
                    mean_temp.extend([nag_f["decoded_value"]])
                min_nag_state = min(min_nag_state, nag_f["state"])
                max_nag_state = max(max_nag_state, nag_f["state"])
    if min_temp is None:
        td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
    else:
        if max_nag_state == NAG_SERVICE_CRITICAL:
            td_state = "errorcenter"
        elif min_nag_state == max_nag_state and min_nag_state == NAG_SERVICE_OK:
            td_state = "center"
        else:
            td_state = "warncenter"
        if len(mean_temp) == 1:
            perc_vals = [min_temp * 100 / tot_max_temp]
        else:
            mean_temp = sum(mean_temp) / len(mean_temp)
            perc_vals = [v * 100 / tot_max_temp for v in [min_temp, mean_temp, max_temp]]
            perc_vals.reverse()
        if draw_dict["DRAW_GFX"]:
            draw_dict["IG_STRUCT"].create_graph("temp", dict([(k, (x, infograph.get_rgb_val(x, draw_dict["COLORPATH1"]))) for k, x in zip(range(len(perc_vals)), perc_vals)]))
            state_str = "<img src=\"../graphs/%s\"/>" % (draw_dict["IG_STRUCT"].get_last_name())
        else:
            state_str = "%.2f / %.2f / %.2f" % (min_temp, mean_temp, max_temp)
    return [(td_state, state_str)]

def interpret_hw_fan_dict(l_dict, draw_dict, tot_max_fan):
    min_nag_state, max_nag_state = (NAG_SERVICE_OK, NAG_SERVICE_OK)
    min_fan = None
    for dev_idx, dev_list in l_dict.iteritems():
        for nag_f in dev_list:
            if nag_f["decoded"]:
                if min_fan is None:
                    min_fan, max_fan, mean_fan = (nag_f["decoded_value"],
                                                  nag_f["decoded_value"],
                                                  [nag_f["decoded_value"]])
                else:
                    min_fan = min(min_fan, nag_f["decoded_value"])
                    max_fan = max(max_fan, nag_f["decoded_value"])
                    mean_fan.extend([nag_f["decoded_value"]])
                min_nag_state = min(min_nag_state, nag_f["state"])
                max_nag_state = max(max_nag_state, nag_f["state"])
    if min_fan is None:
        td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
    else:
        if max_nag_state == NAG_SERVICE_CRITICAL:
            td_state = "errorcenter"
        elif min_nag_state == max_nag_state and min_nag_state == NAG_SERVICE_OK:
            td_state = "center"
        else:
            td_state = "warncenter"
        if len(mean_fan) == 1:
            perc_vals = [min_fan * 100 / tot_max_fan]
        else:
            mean_fan = sum(mean_fan) / len(mean_fan)
            perc_vals = [v * 100 / tot_max_fan for v in [min_fan, mean_fan, max_fan]]
            perc_vals.reverse()
        if draw_dict["DRAW_GFX"]:
            draw_dict["IG_STRUCT"].create_graph("fan", dict([(k, (x, infograph.get_rgb_val(100 - x, draw_dict["COLORPATH1"]))) for k, x in zip(range(len(perc_vals)), perc_vals)]))
            state_str = "<img src=\"../graphs/%s\"/>" % (draw_dict["IG_STRUCT"].get_last_name())
        else:
            state_str = "%.2f / %.2f / %.2f" % (min_fan, mean_fan, max_fan)
    return [(td_state, state_str)]

def interpret_memory_dict(l_dict, draw_dict):
    act_types = ["phys", "swap", "tot"]
    min_dict, mean_dict, max_dict = ({}, {}, {})
    min_serv_state, max_serv_state = (dict([(k, NAG_SERVICE_OK) for k in act_types]),
                                      dict([(k, NAG_SERVICE_OK) for k in act_types]))
    min_load = None
    for dev_idx, dev_list in l_dict.iteritems():
        for nag_f in dev_list:
            if nag_f["decoded"]:
                for act_type in [x for x in act_types if nag_f["decoded_value"].has_key(x)]:
                    min_serv_state[act_type] = min(min_serv_state[act_type], nag_f["state"])
                    max_serv_state[act_type] = max(max_serv_state[act_type], nag_f["state"])
                    if draw_dict["VALUES_ABS"]:
                        mem_val = int(nag_f["decoded_value"][act_type]["rel"] * nag_f["decoded_value"][act_type]["abs"] / 100)
                    else:
                        mem_val = nag_f["decoded_value"][act_type]["rel"]
                    if min_dict.has_key(act_type):
                        min_dict[act_type] = min(min_dict[act_type], mem_val)
                        max_dict[act_type] = max(max_dict[act_type], mem_val)
                        mean_dict[act_type].append(mem_val)
                    else:
                        min_dict[act_type] = mem_val
                        max_dict[act_type] = mem_val
                        mean_dict[act_type] = [mem_val]
    ret_list = []
    for act_type in act_types:
        if not min_dict.has_key(act_type):
            td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
        else:
            num_data = len(mean_dict[act_type])
            mean_dict[act_type] = sum(mean_dict[act_type]) / num_data
            if max_serv_state[act_type] == NAG_SERVICE_CRITICAL:
                td_state = "errorcenter"
            elif min_serv_state[act_type] == max_serv_state[act_type] and min_serv_state[act_type] == NAG_SERVICE_OK:
                td_state = "center"
            else:
                td_state = "warncenter"
            if num_data == 1:
                d_list = [mean_dict[act_type]]
            else:
                d_list = [max_dict[act_type], mean_dict[act_type], min_dict[act_type]]
            if draw_dict["DRAW_GFX"]:
                draw_dict["IG_STRUCT"].create_graph("mem", dict([(k, (x, infograph.get_rgb_val(x, draw_dict["COLORPATH1"]))) for k, x in zip(range(len(d_list)), d_list)]))
                state_str = "<img src=\"../graphs/%s\"/>" % (draw_dict["IG_STRUCT"].get_last_name())
            else:
                d_list.reverse()
                if draw_dict["VALUES_ABS"]:
                    state_str = " / ".join([get_size_str(x) for x in d_list])
                else:
                    state_str = " / ".join(["%d%%" % (x) for x in d_list])
        ret_list.append((td_state, state_str))
    return ret_list

def get_size_str(val):
    for pf in ["", "k", "M", "G"]:
        if val < 1024:
            break
        else:
            val /= 1024.
    if pf:
        return "%.2f %sB" % (val, pf)
    else:
        return "%d B" % (val)
    
def interpret_network_dict(l_dict, draw_dict, tot_max_net):
    act_types = ["rx", "tx"]
    min_dict, mean_dict, max_dict = ({}, {}, {})
    min_serv_state, max_serv_state = (dict([(k, NAG_SERVICE_OK) for k in act_types]),
                                      dict([(k, NAG_SERVICE_OK) for k in act_types]))
    min_load = None
    for dev_idx, dev_list in l_dict.iteritems():
        for nag_f in dev_list:
            if nag_f["decoded"]:
                for act_type, act_speed in zip(act_types, nag_f["decoded_value"]):
                    if draw_dict["VALUES_ABS"]:
                        pass
                    else:
                        act_speed = 100. * float(act_speed) / float(max(1, tot_max_net))
                    if min_dict.has_key(act_type):
                        min_dict[act_type] = min(min_dict[act_type], act_speed)
                        max_dict[act_type] = max(max_dict[act_type], act_speed)
                        mean_dict[act_type].append(act_speed)
                    else:
                        min_dict[act_type] = act_speed
                        max_dict[act_type] = act_speed
                        mean_dict[act_type] = [act_speed]
                min_serv_state[act_type] = min(min_serv_state[act_type], nag_f["state"])
                max_serv_state[act_type] = max(max_serv_state[act_type], nag_f["state"])
    ret_list = []
    for act_type in act_types:
        if not min_dict.has_key(act_type):
            td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
        else:
            num_data = len(mean_dict[act_type])
            mean_dict[act_type] = sum(mean_dict[act_type]) / num_data
            if max_serv_state[act_type] == NAG_SERVICE_CRITICAL:
                td_state = "errorcenter"
            elif min_serv_state[act_type] == max_serv_state[act_type] and min_serv_state[act_type] == NAG_SERVICE_OK:
                td_state = "center"
            else:
                td_state = "warncenter"
            if num_data == 1:
                d_list = [mean_dict[act_type]]
            else:
                d_list = [max_dict[act_type], mean_dict[act_type], min_dict[act_type]]
            if draw_dict["DRAW_GFX"]:
                draw_dict["IG_STRUCT"].create_graph("net", dict([(k, (x, infograph.get_rgb_val(x, draw_dict["COLORPATH1"]))) for k, x in zip(range(len(d_list)), d_list)]))
                state_str = "<img src=\"../graphs/%s\"/>" % (draw_dict["IG_STRUCT"].get_last_name())
            else:
                d_list.reverse()
                if draw_dict["VALUES_ABS"]:
                    state_str = " / ".join([get_size_str(x) for x in d_list])
                else:
                    state_str = " / ".join(["%d%%" % (x) for x in d_list])
        ret_list.append((td_state, state_str))
    return ret_list

def get_state_str(in_dict):
    return " / ".join(["%d %s" % (in_dict.count(k), v) for k, v in [(NAG_SERVICE_UNKNOWN , "unk" ),
                                                                    (NAG_SERVICE_OK      , "ok"  ),
                                                                    (NAG_SERVICE_WARNING , "warn"),
                                                                    (NAG_SERVICE_CRITICAL, "crit"),
                                                                    (NAG_SERVICE_IGNORED , "ign" )] if in_dict.count(k)])

def interpret_disk_hw_dict(l_dict):
    states = []
    for dev_list in l_dict.itervalues():
        states.extend([x["state"] for x in dev_list])
    if not states:
        td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
    else:
        min_serv_state = min(states)
        max_serv_state = max(states)
        if max_serv_state == NAG_SERVICE_CRITICAL:
            td_state = "errorcenter"
        elif min_serv_state == max_serv_state and min_serv_state == NAG_SERVICE_OK:
            td_state = "center"
        else:
            td_state = "warncenter"
        state_str = get_state_str(states)
    return [(td_state, state_str)]

def interpret_disk_df_dict(l_dict, draw_dict):
    min_nag_state, max_nag_state = (NAG_SERVICE_OK, NAG_SERVICE_OK)
    min_df = None
    for dev_idx, dev_list in l_dict.iteritems():
        for nag_f in dev_list:
            if nag_f["decoded"]:
                min_nag_state = min(min_nag_state, nag_f["state"])
                max_nag_state = max(max_nag_state, nag_f["state"])
                if draw_dict["VALUES_ABS"]:
                    df_val = nag_f["decoded_value"]["used"]
                else:
                    df_val = nag_f["decoded_value"]["relative"]
                if min_df is None:
                    min_df, max_df, mean_df = (df_val,
                                               df_val,
                                               [df_val])
                else:
                    min_df = min(min_df, df_val)
                    max_df = max(max_df, df_val)
                    mean_df.extend([df_val])
    if min_df is None:
        td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
    else:
        num_data = len(mean_df)
        mean_df = sum(mean_df) / num_data
        if max_nag_state == NAG_SERVICE_CRITICAL:
            td_state = "errorcenter"
        elif min_nag_state == max_nag_state and min_nag_state == NAG_SERVICE_OK:
            td_state = "center"
        else:
            td_state = "warncenter"
        if num_data == 1:
            d_list = [mean_df]
        else:
            d_list = [max_df, mean_df, min_df]
        if draw_dict["DRAW_GFX"]:
            draw_dict["IG_STRUCT"].create_graph("mem", dict([(k, (x, infograph.get_rgb_val(x, draw_dict["COLORPATH1"]))) for k, x in zip(range(len(d_list)), d_list)]))
            state_str = "<img src=\"../graphs/%s\"/>" % (draw_dict["IG_STRUCT"].get_last_name())
        else:
            d_list.reverse()
            if draw_dict["VALUES_ABS"]:
                state_str = " / ".join([get_size_str(x) for x in d_list])
            else:
                state_str = " / ".join(["%d%%" % (x) for x in d_list])
    return [(td_state, state_str)]

def interpret_services_dict(l_dict):
    states = []
    for dev_list in l_dict.itervalues():
        states.extend([x["state"] for x in dev_list])
    if len(states) == 0:
        td_state, state_str = (NO_DATA_CLASS, "--- no data ---")
    else:
        min_serv_state = min(states)
        max_serv_state = max(states)
        if max_serv_state == NAG_SERVICE_CRITICAL:
            td_state = "errorcenter"
        elif min_serv_state == max_serv_state and min_serv_state == NAG_SERVICE_OK:
            td_state = "center"
        else:
            td_state = "warncenter"
        state_str = get_state_str(states)
    return [(td_state, state_str)]

def cluster_list_view(req, dev_tree, c_struct, draw_dict, href_str):
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    # transfrom idxs to names
    dg_sel_eff = c_struct.get_device_group_names(dg_sel_eff)
    if d_sel:
        detailed_view = True
        h_cells = ["Devicename", "Status"]
    else:
        detailed_view = False
        h_cells = ["Groupname", "Status", "Devtype"]
    d_sel = c_struct.get_device_names(d_sel)
    # get all device_idxs
    all_dev_idxs = c_struct.get_device_idxs([], d_sel)
    num_stypes = 0
    s_types = c_struct.get_service_types()
    if "load" in s_types:
        num_stypes += 1
        max_load = c_struct.get_max_load(all_dev_idxs)
        if max_load < 5:
            max_load = int(max_load) + 1
        else:
            max_load = 5 * (int(max_load + 4.999999) / 5)
        h_cells.extend(["Load (max=%d)" % (max_load)])
    if "memory" in s_types:
        num_stypes += 1
        h_cells.extend(["Mem phys", "Mem swap", "Mem tot"])
    if "network" in s_types:
        num_stypes += 1
        max_net_m = c_struct.get_max_net(all_dev_idxs)
        max_net = 16
        while max_net_m >= max_net:
            max_net = max_net * 2
        h_cells.extend(["Net rx(max=%s)/s" % (get_size_str(max_net)),
                        "Net tx(max=%s)/s" % (get_size_str(max_net))])
    if "hw/temp" in s_types:
        num_stypes += 1
        max_temp = c_struct.get_max_temp(all_dev_idxs)
        max_temp = 5 * (int(max_temp + 4.999999) / 5)
        h_cells.extend(["Temp (max=%d C)" % (max_temp)])
    if "hw/fan" in s_types:
        num_stypes += 1
        max_fan = c_struct.get_max_fan(all_dev_idxs)
        max_fan = 1000 * (int(max_fan + 1000) / 1000)
        h_cells.extend(["RPMs (max=%d RPM)" % (max_fan)])
    if "disk/hw" in s_types:
        num_stypes += 1
        h_cells.extend(["Disk hw"])
    if "disk/df" in s_types:
        num_stypes += 1
        h_cells.extend(["Disk df"])
    if "services" in s_types:
        num_stypes += 1
        h_cells.extend(["Services"])
    out_table = html_tools.html_table(cls="normal")
    line_h = "line00"
    out_table[0]["class"] = line_h
    for h_cell in h_cells:
        out_table[None][0] = html_tools.content(h_cell, cls="center", type="th")
    any_checks_found = False
    # devices to remove from total-view
    tot_idx_remove_list = []
    line_idx = 1
    if c_struct.detail_mode:
        detail_devg_idx = c_struct.get_device_group(dg_sel_eff[0]).get_device_group_idx()
    for dg_name in dg_sel_eff + ["total"]:
        if detailed_view:
            if dg_name == "total":
                act_dev_idx_list = [c_struct.get_device_idxs([], d_sel)]
            else:
                act_dev_idx_list = [[x] for x in c_struct.get_device_group(dg_name).get_device_idxs() if x in all_dev_idxs]
                out_table[0]["class"] = "line01"
                out_table[None][0 : len(h_cells)] = html_tools.content("Devicegroup %s (%s selected)" % (dg_name, logging_tools.get_plural("device", len(act_dev_idx_list))), cls="center", type="th")
        else:
            if dg_name == "total":
                act_dev_idx_list = [[x for x in c_struct.get_device_idxs(dg_sel_eff, []) if x not in tot_idx_remove_list]]
            else:
                act_dev_idx_list = [c_struct.get_device_idxs([dg_name], [])]
        for act_dev_idxs in act_dev_idx_list:
            # list of device idxs which are up
            up_dev_idx_list = c_struct.get_up_device_idxs(act_dev_idxs)
            num_checks = sum([c_struct.get_device(x).get_num_checks() for x in c_struct.get_device_names(act_dev_idxs)])
            if num_checks:
                any_checks_found = True
                line_idx = 1 - line_idx
                out_table[0]["class"] = dg_name == "total" and line_h or "line1%d" % (line_idx)
                if detailed_view:
                    if dg_name == "total":
                        act_struct = c_struct
                        if not c_struct.detail_mode:
                            out_name = "<a href=\"%s.py?%s&%s\">%s</a>" % (req.module_name,
                                                                           functions.get_sid(req),
                                                                           href_str,
                                                                           dg_name)
                        else:
                            out_name = "<a href=\"%s.py?%s&devg[]=%d&%s\">%s</a>" % (req.module_name,
                                                                                     functions.get_sid(req),
                                                                                     detail_devg_idx,
                                                                                     href_str,
                                                                                     dg_name)
                    else:
                        d_name = c_struct.get_device_name(act_dev_idxs[0])
                        act_struct = c_struct.get_device(d_name)
                        if not c_struct.detail_mode:
                            out_name = "<a href=\"%s.py?%s&dev[]=%d&%s&devicedetail=1\">%s</a>" % (req.module_name,
                                                                                                   functions.get_sid(req),
                                                                                                   act_struct.get_device_idx(),
                                                                                                   href_str,
                                                                                                   d_name)
                        else:
                            out_name = d_name
                else:
                    if dg_name == "total":
                        out_name = "Cluster"
                        act_struct = c_struct
                    else:
                        act_struct = c_struct.get_device_group(dg_name)
                        out_name = "<a href=\"%s.py?%s&devg[]=%d&%s\">%s</a>" % (req.module_name,
                                                                                 functions.get_sid(req),
                                                                                 act_struct.get_device_group_idx(),
                                                                                 href_str,
                                                                                 dg_name)
                td_state, state_str = get_device_status_string(act_struct.get_device_status_dict(act_dev_idxs),
                                                               c_struct.get_service_status("uptime", act_dev_idxs))
                out_table[None][0] = html_tools.content(out_name, cls="left")
                out_table[None][0] = html_tools.content(state_str, cls=td_state)
                if not detailed_view:
                    out_table[None][0] = html_tools.content(act_struct.get_device_type_info(), cls="center")
                line_cache = []
                if "load" in s_types:
                    line_cache.extend(interpret_load_dict(c_struct.get_service_status("load", act_dev_idxs), draw_dict, max_load))
                if "memory" in s_types:
                    line_cache.extend(interpret_memory_dict(c_struct.get_service_status("memory", act_dev_idxs), draw_dict))
                if "network" in s_types:
                    line_cache.extend(interpret_network_dict(c_struct.get_service_status("network", act_dev_idxs), draw_dict, max_net))
                if "hw/temp" in s_types:
                    line_cache.extend(interpret_hw_temp_dict(c_struct.get_service_status("hw/temp", act_dev_idxs), draw_dict, max_temp))
                if "hw/fan" in s_types:
                    line_cache.extend(interpret_hw_fan_dict(c_struct.get_service_status("hw/fan", act_dev_idxs), draw_dict, max_fan))
                if "disk/hw" in s_types:
                    line_cache.extend(interpret_disk_hw_dict(c_struct.get_service_status("disk/hw", up_dev_idx_list)))
                if "disk/df" in s_types:
                    line_cache.extend(interpret_disk_df_dict(c_struct.get_service_status("disk/df", up_dev_idx_list), draw_dict))
                if "services" in s_types:
                    line_cache.extend(interpret_services_dict(c_struct.get_service_status("services", up_dev_idx_list)))
                last_state, last_str, repeat = (None, None, 0)
                for act_state, act_str in line_cache:
                    if act_state != last_state or last_str != act_str or not act_str.count("no data"):
                        if last_state:
                            out_table[None][0:repeat] = html_tools.content(last_str, cls=last_state)
                        last_state, last_str, repeat = (act_state, act_str, 0)
                    repeat += 1
                if last_state:
                    out_table[None][0:repeat] = html_tools.content(last_str, cls=last_state)
            else:
                # remove this devices from total-list
                tot_idx_remove_list.extend(act_dev_idxs)
    if any_checks_found:
        req.write(html_tools.gen_hline("Showing %s data for %s (%s), %s:" % (detailed_view and "detailed" or "overview",
                                                                             logging_tools.get_plural("device group", len(dg_sel_eff)),
                                                                             logging_tools.get_plural("device", len(d_sel)),
                                                                             logging_tools.get_plural("service type", num_stypes)), 3))
        req.write(out_table(""))
    else:
        req.write(html_tools.gen_hline("No checks defined for %s (%s)" % (detailed_view and "detailed" or "overview",
                                                                          logging_tools.get_plural("device", len(d_sel))), 3))

def cluster_show_problems(req, dev_tree, c_struct, min_level):
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    # transfrom idxs to names
    dg_sel_eff = c_struct.get_device_group_names(dg_sel_eff)
    d_sel_names = c_struct.get_device_names(d_sel)
    h_cells = ["Type", "Service", "Group", "Device", "Status", "last check", "duration", "Info"]
    out_table = html_tools.html_table(cls="normal")
    line_h = "line00"
    out_table[0]["class"] = line_h
    for h_cell in h_cells:
        out_table[None][0] = html_tools.content(h_cell, cls="center", type="th")
    num_problems, prob_devices = (0, [])
    act_dev_idx_list = []
    for dg_name in dg_sel_eff:
        act_dev_idx_list.extend(c_struct.get_device_idxs([dg_name], []))
    # list of device idxs which are up
    if d_sel:
        up_dev_idx_list = c_struct.get_up_device_idxs(d_sel)
    else:
        up_dev_idx_list = c_struct.get_up_device_idxs(act_dev_idx_list)
    if c_struct.detail_mode:
        s_status = c_struct.get_service_status_undecoded(c_struct.get_service_types(), up_dev_idx_list)
    else:
        show_selection = {0 : [-1, 1, 2],
                          1 : [2],
                          2 : [1],
                          3 : [-1, 0, 1, 2]}[min_level]
        s_status = c_struct.get_service_status_2([], up_dev_idx_list, show_selection)
    problem_groups = []
    dt_now = datetime.datetime(2005, 1, 1).now()
    if s_status:
        line_idx, act_line = (0, 2)
        type_line    = act_line
        service_line = act_line
        dev_line     = act_line
        for s_type in sorted(s_status.keys()):
            type_problems = 0
            for service in sorted(s_status[s_type].keys()):
                service_problems = 0
                dev_idxs = [x for x in up_dev_idx_list if x in s_status[s_type][service]]
                for dev_idx in dev_idxs:
                    dev_name = c_struct.get_device_name(dev_idx)
                    if dev_idx not in prob_devices:
                        prob_devices.append(dev_idx)
                    for act_stuff in s_status[s_type][service][dev_idx]:
                        line_idx = 1 - line_idx
                        out_table[act_line]["class"] = "line1%d" % (line_idx)
                        act_class = {-2 : "warncenter",
                                     -1 : "warncenter",
                                     0  : "okcenter",
                                     1  : "warncenter",
                                     2  : "errorcenter"}.get(act_stuff["state"], "error")
                        out_table[None][5] = html_tools.content({-2 : "IGNORED",
                                                                 -1 : "UNKNOWN",
                                                                 0  : "OK",
                                                                 1  : "WARN",
                                                                 2  : "CRITICAL"}.get(act_stuff["state"], "???"), cls=act_class)
                        out_table[None][0] = html_tools.content(get_diff_time_str(act_stuff["last_check"], dt_now), cls="left")
                        out_table[None][0] = html_tools.content(get_diff_time_str_2(act_stuff["last_state_change"], dt_now), cls="left")
                        out_table[None][0] = html_tools.content(act_stuff["output"], cls="left")
                        act_line += 1
                        num_problems += 1
                        service_problems += 1
                        type_problems += 1
                    devg_name = c_struct.get_device_group_by_device_name(dev_name).get_name()
                    out_table[dev_line : act_line - 1][3] = html_tools.content(devg_name, cls="center")
                    out_table[dev_line : act_line - 1][4] = html_tools.content(dev_name, cls="center")
                    dev_line = act_line
                    if devg_name not in problem_groups:
                        problem_groups.append(devg_name)
                out_table[service_line : dev_line - 1][2] = html_tools.content("%s%s" % (service, service_problems > 1 and " [%d]" % (service_problems) or ""), cls="left")
                service_line = act_line
            out_table[type_line : service_line - 1][1] = html_tools.content("%s%s" % (s_type, type_problems > 1 and " [%d]" % (type_problems) or ""), cls="left")
            type_line = service_line
    if num_problems:
        req.write(html_tools.gen_hline("Showing %s on %s (%s):" % (logging_tools.get_plural("problem", num_problems),
                                                                   logging_tools.get_plural("device", len(prob_devices)),
                                                                   logging_tools.get_plural("group", len(problem_groups))), 3))
        req.write(out_table(""))
    else:
        req.write(html_tools.gen_hline("No problems", 3))
    
def process_page(req):
    functions.write_header(req)
    functions.write_body(req)
    dev_tree = tools.display_list(req)
    dev_tree.add_regexp_field()
    dev_tree.add_devsel_fields(tools.get_device_selection_lists(req.dc, req.user_info.get_idx()))
    dev_tree.query([],
                   ["comment", "bootserver"])
    # what to display
    disp_list = html_tools.selection_list(req, "dt", {"l" : "List View",
                                                      "m" : "Matrix View"})
    act_disp = disp_list.check_selection("", "l")
    # action log
    action_log = html_tools.message_log()
    # gfx stuff
    if infograph:
        gfx_list = html_tools.selection_list(req, "gf", {"np" : "Numeric (perc)",
                                                         "na" : "Numeric (abs)",
                                                         "b" :  "Bargraph"})
        show_mode = gfx_list.check_selection("", "b")
    else:
        gfx_list = html_tools.selection_list(req, "gf", {"np" : "Numeric (perc)",
                                                         "na" : "Numeric (abs)"})
        show_mode = gfx_list.check_selection("", "na")
    detail_mode = html_tools.checkbox(req, "devicedetail")
    # act_ng_check_command_types
    act_ng_check_command_types = tools.ng_check_command_types(req.dc, action_log)
    endis_list = html_tools.selection_list(req, "endil", {0 : "enable",
                                                          1 : "disable"}, sort_new_keys=0)
    ng_cctd_list = html_tools.selection_list(req, "nctd", {}, sort_new_keys=0, multiple=True, size=3)
    for key, value in act_ng_check_command_types.iteritems():
        ng_cctd_list[key] = value["name"]
    ng_cctds = ng_cctd_list.check_selection("", [])
    ng_todo = endis_list.check_selection("", 1)
    # select button
    select_button = html_tools.submit_button(req, "select", ext_name="select")
    select_pressed = select_button.check_selection("") == "select"
    # ignore list
    ignore_flag = html_tools.checkbox(req, "ign")
    saved_ignore = req.user_info.get_user_var_value("_ci_ignto", False)
    if select_pressed:
        ignore_timeouts = ignore_flag.check_selection("")
    else:
        ignore_timeouts = ignore_flag.check_selection("", saved_ignore)
    if select_pressed:
        req.user_info.modify_user_var("_ci_ignto", ignore_timeouts)
    # min_service display
    min_service_disp = html_tools.selection_list(req, "msld", {-1 : "no errors",
                                                               0  : "all errors",
                                                               1  : "only critical",
                                                               2  : "only warning",
                                                               3  : "everything"})
    act_min_service_level = min_service_disp.check_selection("", 0)
    if not dev_tree.devices_found():
        req.write(html_tools.gen_hline("No devices found", 2))
    else:
        for dg in dev_tree.get_sorted_devg_idx_list():
            for dev in dev_tree.get_sorted_dev_idx_list(dg):
                dev_struct = dev_tree.get_dev_struct(dev)
                if dev_struct["bootserver"]:
                    bs_name = dev_tree.get_dev_name(dev_struct["bootserver"])
                    bs_string = "bs=%s" % (bs_name)
                else:
                    bs_string = "no bs"
                dev_struct["post_str"] = ", %s" % (bs_string)
        ds_dict = dev_tree.get_device_selection_lists()
        sel_table = html_tools.html_table(cls="blindsmall")
        sel_table[0][0] = html_tools.content(dev_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
        if ds_dict:
            sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
            col_span = 3
        else:
            col_span = 2
        # report for problem devices
        sel_table[0][1:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(), " and devices ", dev_tree.get_dev_re_field(),
                                                       "\n, ", dev_tree.get_devsel_action_field(), " selection", dev_tree.get_devsel_field()], cls="center")
        info_line = ["Display type: ", disp_list,
                     ", show values as ", gfx_list,
                     ", ", endis_list, " ", ng_cctd_list,
                     ", show ", min_service_disp,
                     " ignore timeouts: ", ignore_flag,
                     ",\n ", select_button]
        draw_dict = {"DRAW_GFX" : show_mode in ["b"]}
        draw_dict["VALUES_ABS"] = show_mode in ["na"]
        # init info_graph struct
        if infograph:
            ig_struct = infograph.info_graph("/".join(os.path.dirname(req.environ["SCRIPT_FILENAME"]).split("/")[:-1] + ["graphs"]))
            ig_struct["type"]   = "rectgr"
            ig_struct["width"]  = 100
            ig_struct["height"] = 16
            ig_struct["bordercolor"]  = "666666"
            ig_struct["outlinecolor"] = "000000"
            ig_struct["bordersize"] = 1
            ig_struct["ystride"]    = 2
            ig_struct["add_name"]   = functions.get_sid_value(req)
        else:
            ig_struct = None
        draw_dict["IG_STRUCT"] = ig_struct
        draw_dict["COLORPATH1"] = ["00aa00", "ffff00", "ff2222"]
        sel_table[0][1:col_span] = html_tools.content(info_line, cls="center")
        my_cluster = cluster(action_log)
        my_cluster.set_option("ignore_timeouts", ignore_timeouts)
        # little hack...
        my_cluster.detail_mode = detail_mode.check_selection("")
        if ng_todo:
            my_cluster.set_forbidden_ngcct_idxs(ng_cctds)
        else:
            my_cluster.set_forbidden_ngcct_idxs([x for x in act_ng_check_command_types.keys() if x not in ng_cctds])
        # fetch basic nagios-stuff
        req.dc.execute("SELECT cc.name AS check_command_name, nct.name AS service_type, cc.description, nct.ng_check_command_type_idx FROM "+ \
                       "new_config nc INNER JOIN ng_check_command cc INNER JOIN ng_check_command_type nct WHERE cc.new_config=nc.new_config_idx AND nct.ng_check_command_type_idx=cc.ng_check_command_type")
        for db_rec in req.dc.fetchall():
            # build config structs for all service types
            my_cluster.build_config_struct(db_rec)
        # add device-tree
        req.dc.execute("SELECT d.name, dg.name AS dg_name, d.device_idx, dg.device_group_idx, dt.identifier FROM device d " + \
                       "INNER JOIN device_group dg INNER JOIN device_type dt WHERE d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx")
        # fetch nagios-stuff
        for db_rec in req.dc.fetchall():
            my_cluster.build_device_tree(db_rec)
        # determine Nagios / Icinga Version
        sql_str = "SELECT dv.val_str FROM device_variable dv, device d, device_group dg WHERE dg.cluster_device_group AND d.device_group=dg.device_group_idx AND dv.device=d.device_idx AND dv.name='md_type'"
        req.dc.execute(sql_str)
        if req.dc.rowcount:
            md_type = req.dc.fetchone()["val_str"]
            sql_str = "SELECT dv.val_str FROM device_variable dv, device d, device_group dg WHERE dg.cluster_device_group AND d.device_group=dg.device_group_idx AND dv.device=d.device_idx AND dv.name='md_version'"
        else:
            md_type = "nagios"
            sql_str = "SELECT dv.val_str FROM device_variable dv, device d, device_group dg WHERE dg.cluster_device_group AND d.device_group=dg.device_group_idx AND dv.device=d.device_idx AND dv.name='nagios_version'"
        req.dc.execute(sql_str)
        if req.dc.rowcount:
            md_vers = req.dc.fetchone()["val_str"]
        else:
            md_vers = "unknown"
        if md_type == "icinga" or (md_type == "nagios" and md_vers[0] in ["2", "3"]):
            md_newer = True
        else:
            md_newer = False
        if md_newer:
            # NagiosV2.x query
            # hoststatus checks
            sql_str = "SELECT nhs.current_state AS host_status, nh.display_name AS host_name FROM nagiosdb.%s_hoststatus nhs, nagiosdb.%s_hosts nh WHERE nhs.host_object_id=nh.host_object_id" % (md_type, md_type)
            req.dc.execute(sql_str)
            for db_rec in req.dc.fetchall():
                my_cluster.feed_nagios_host_result(db_rec)
            # servicestatus checks
            sql_str = "SELECT ns.service_id, ns.service_object_id, nh.display_name AS host_name, nss.output AS plugin_output, nss.last_check, nss.last_state_change, nss.current_state AS service_status, ns.display_name AS service_description FROM nagiosdb.%s_services ns, nagiosdb.%s_hosts nh, nagiosdb.%s_servicestatus nss WHERE ns.host_object_id=nh.host_object_id AND nss.service_object_id=ns.service_object_id" % (md_type, md_type, md_type)
            req.dc.execute(sql_str)
            for db_rec in req.dc.fetchall():
                my_cluster.feed_nagios_service_result(db_rec)
        else:
            # NagiosV1.x query
            sql_str = "SELECT h.host_name, h.host_status, s.service_status, s.service_description, s.plugin_output, s.last_check, s.last_state_change " + \
                    "FROM nagiosdb.hoststatus h INNER JOIN nagiosdb.servicestatus s WHERE h.host_name=s.host_name"
            req.dc.execute(sql_str)
            for db_rec in req.dc.fetchall():
                my_cluster.feed_nagios_result(db_rec)
        href_str = "&".join(["%s=%s" % (gfx_list.get_name(), show_mode)] +
                            ["%s=%s" % (disp_list.get_name(), act_disp)] +
                            ["%s=%d" % (min_service_disp.get_name(), act_min_service_level)] +
                            (ignore_timeouts and ["%s=1" % (ignore_flag.get_name())] or []) +
                            ["%s=%d" % (endis_list.get_name(), ng_todo)] +
                            ["%s[]=%d" % (ng_cctd_list.get_name(), y) for y in ng_cctds])
        req.write("<form action=\"%s.py\" method=get>%s%s</form>\n" % (req.module_name,
                                                                       functions.get_hidden_sid(req),
                                                                       sel_table("")))
        req.write(action_log.generate_stack("Log"))
        # what to do
        if act_disp == "l":
            cluster_list_view(req, dev_tree, my_cluster, draw_dict, href_str)
            if act_min_service_level >= 0:
                cluster_show_problems(req, dev_tree, my_cluster, act_min_service_level)
        del my_cluster
        del draw_dict
