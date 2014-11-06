# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

""" rms-server, license monitoring part """

from django.db import connection, models
from django.db.models import Max, Min, Avg, Q, Count
from initat.host_monitoring import hm_classes
from initat.rms.config import global_config
from lxml import etree  # @UnresolvedImport @UnusedImport
from lxml.builder import E  # @UnresolvedImport @UnusedImport
from initat.cluster.backbone.models import ext_license_site, ext_license, ext_license_check, \
    ext_license_version, ext_license_state, ext_license_version_state, ext_license_vendor, \
    ext_license_usage, ext_license_client_version, ext_license_client, ext_license_user, \
    ext_license_check_coarse, ext_license_version_state_coarse, ext_license_state_coarse, \
    ext_license_usage_coarse
# from initat.cluster.backbone.models.functions import cluster_timezone
import commands
import datetime
import logging_tools
import os
import process_tools
import server_command
import sge_license_tools
import threading_tools
import time
import zmq
from pprint import pprint


EL_LUT = {
    "ext_license_site": ext_license_site,
    "ext_license": ext_license,
    "ext_license_version": ext_license_version,
    "ext_license_vendor": ext_license_vendor,
    "ext_license_client_version": ext_license_client_version,
    "ext_license_client": ext_license_client,
    "ext_license_user": ext_license_user,
}


def call_command(command, log_com=None):
    start_time = time.time()
    stat, out = commands.getstatusoutput(command)
    end_time = time.time()
    log_lines = ["calling '{}' took {}, result (stat {:d}) is {} ({})".format(
        command,
        logging_tools.get_diff_time_str(end_time - start_time),
        stat,
        logging_tools.get_plural("byte", len(out)),
        logging_tools.get_plural("line", len(out.split("\n"))))]
    if log_com:
        for log_line in log_lines:
            log_com(" - {}".format(log_line))
        if stat:
            for log_line in out.split("\n"):
                log_com(" - {}".format(log_line))
        return stat, out
    else:
        if stat:
            # append output to log_lines if error
            log_lines.extend([" - {}".format(line) for line in out.split("\n")])
        return stat, out, log_lines


class license_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self._init_sge_info()
        self._init_network()
        # job stop/start info
        self.__elo_obj = None
        self.register_timer(self._update, 30, instant=True)
        
        # for proper use:
        #self.register_timer(self._update_coarse_data, 60*15, instant=True)
        # for testing:
        self._update_coarse_data()

    def _init_sge_info(self):
        self._license_base = global_config["LICENSE_BASE"]
        self._track = global_config["TRACK_LICENSES"]
        self._track_in_db = global_config["TRACK_LICENSES_IN_DB"]
        self._modify_sge = global_config["MODIFY_SGE_GLOBAL"]
        # license tracking cache
        self.__lt_cache = {}
        # store currently configured values, used for logging
        self._sge_lic_set = {}
        self.__lc_dict = {}
        self.log(
            "init sge environment for license tracking in {} ({}, database tracing is {})".format(
                self._license_base,
                "enabled" if self._track else "disabled",
                "enabled" if self._track_in_db else "disabled",
            )
        )
        # set environment
        os.environ["SGE_ROOT"] = global_config["SGE_ROOT"]
        os.environ["SGE_CELL"] = global_config["SGE_CELL"]
        # get sge environment
        self._sge_dict = sge_license_tools.get_sge_environment()
        self.log(sge_license_tools.get_sge_log_line(self._sge_dict))

    def _init_network(self):
        _v_conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
        vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        vector_socket.connect(_v_conn_str)
        self.vector_socket = vector_socket

    def get_lt_cache_entry(self, obj_type, **kwargs):
        _obj_cache = self.__lt_cache.setdefault(obj_type, {})
        full_key = ",".join(
            [
                "{}={}".format(
                    _key,
                    unicode(_value) if (isinstance(_value, basestring) or type(_value) in [int, long]) else str(_value.pk)
                ) for _key, _value in kwargs.iteritems()
            ]
        )
        if full_key not in _obj_cache:
            db_obj = EL_LUT[obj_type]
            try:
                _obj = db_obj.objects.get(**kwargs)
            except db_obj.DoesNotExist:
                self.log("creating new '{}' (key: {})".format(obj_type, full_key))
                _obj = db_obj.objects.create(**kwargs)
            _obj_cache[full_key] = _obj
        return _obj_cache[full_key]

    def _write_db_entries(self, act_site, elo_obj, lic_xml):
        # print etree.tostring(lic_xml, pretty_print=True)  # @UndefinedVariable
        # site object
        license_site = self.get_lt_cache_entry("ext_license_site", name=act_site)
        _now = datetime.datetime.now()
        # check object
        cur_lc = ext_license_check.objects.create(
            ext_license_site=license_site,
            run_time=float(lic_xml.get("run_time")),
        )
        for _lic in lic_xml.findall(".//license"):
            ext_license = self.get_lt_cache_entry("ext_license", ext_license_site=license_site, name=_lic.get("name"))
            # save license usage
            _lic_state = ext_license_state.objects.create(
                ext_license=ext_license,
                ext_license_check=cur_lc,
                used=int(_lic.get("used", "0")),
                free=int(_lic.get("free", "0")),
                issued=int(_lic.get("issued", "0")),
                reserved=int(_lic.get("reserved", "0")),
            )
            # build local version dict
            # vers_dict = {}
            for _lic_vers in _lic.findall("version"):
                _cur_vers = self.get_lt_cache_entry(
                    "ext_license_version",
                    version=_lic_vers.get("version"),
                    ext_license=ext_license,
                )
                # vers_dict[_lic_vers.get("version")] = _cur_vers
                _lv_state = ext_license_version_state.objects.create(
                    ext_license_check=cur_lc,
                    ext_license_version=_cur_vers,
                    ext_license_state=_lic_state,
                    is_floating=True if _lic_vers.get("floating", "true").lower()[0] in ["1", "y", "t"] else False,
                    vendor=self.get_lt_cache_entry("ext_license_vendor", name=_lic_vers.get("vendor"))
                )
                for _usage in _lic_vers.findall("usages/usage"):
                    _vers = self.get_lt_cache_entry(
                        "ext_license_client_version",
                        client_version=_usage.get("client_version", "N/A"),
                        ext_license=ext_license,
                    )
                    # print etree.tostring(_usage, pretty_print=True)
                    ext_license_usage.objects.create(
                        ext_license_version_state=_lv_state,
                        ext_license_client=self.get_lt_cache_entry(
                            "ext_license_client",
                            long_name=_usage.get("client_long", ""),
                            short_name=_usage.get("client_short", "N/A")
                        ),
                        ext_license_user=self.get_lt_cache_entry(
                            "ext_license_user",
                            name=_usage.get("user", "N/A")
                        ),
                        ext_license_client_version=_vers,
                        checkout_time=int(float(_usage.get("checkout_time", "0"))),
                        num=int(_usage.get("num", "1")),
                    )

    def _update(self):
        if not self._track:
            return
        _act_site_file = sge_license_tools.text_file(
            os.path.join(sge_license_tools.BASE_DIR, sge_license_tools.ACT_SITE_NAME),
            ignore_missing=True,
        )
        if _act_site_file.lines:
            act_site = _act_site_file.lines[0]
            if not self.__elo_obj:
                self.__elo_obj = sge_license_tools.ExternalLicenses(
                    sge_license_tools.BASE_DIR,
                    act_site,
                    self.log,
                    verbose=True,
                )
            lic_xml = self._update_lic(self.__elo_obj)
            if self._track_in_db:
                self._write_db_entries(act_site, self.__elo_obj, lic_xml)
        else:
            self.log("no actual site defined, no license tracking", logging_tools.LOG_LEVEL_ERROR)

    def _update_coarse_data(self):
        '''
        Updates archive data (coarse data) from raw data in database
        '''

        def create_timespan_entry_from_raw_data(start, end, duration_type, site):
            #last_earlier_time = ext_license_check.objects.filter(date__lte=start, ext_license_site=site).aggregate(Max('date')).itervalues().next()
            #last_earlier_check = ext_license_check.objects.filter(date=last_earlier_time)[0]

            #first_later_time = ext_license_check.objects.filter(date__gt=start, ext_license_site=site).aggregate(Max('date')).itervalues().next()
            #first_later_check = ext_license_check.objects.filter(date=first_later_time)[0]

            timespan_state_data = ext_license_state.objects.filter(
                ext_license_check__date__range=(start, end), ext_license_check__ext_license_site=site)

            timespan_version_state_data = ext_license_version_state.objects.filter(
                ext_license_check__date__range=(start, end), ext_license_check__ext_license_site=site)

            # this indirection is 10 times faster than using timespan_version_state_data as possible indices for ext_license_version_state
            timespan_usage_data = ext_license_usage.objects.filter(ext_license_version_state__ext_license_check__date__range=(start, end),
                                                                   ext_license_version_state__ext_license_check__ext_license_site=site)

            print("num checks: {}, fst: {}".format(len(ext_license_check.objects.filter(date__range=(start, end))),
                  ext_license_check.objects.filter(date__range=(start, end))[0].pk)  )
            print("found {} state entries from {} to {}".format(len(timespan_state_data), start, end))
            print("found {} version state entries from {} to {}".format(len(timespan_version_state_data), start, end))
            print("found {} usage entries".format(len(timespan_usage_data)))

            check_coarse = ext_license_check_coarse.objects.create(
                start_date=start,
                end_date=end,
                duration=(end-start).total_seconds(),
                duration_type=duration_type.ID,
                ext_license_site=site,
            )

            print 'created coarse with start {}'.format(check_coarse.start_date)

            _freq_cnt_sanity = 0
            for lic in timespan_state_data.values("ext_license").distinct():
                lic_id = lic["ext_license"]

                lic_state_data = timespan_state_data.filter(ext_license=lic_id)

                print("\nfound {} lic {} state entries".format(len(lic_state_data), lic_id))

                # TODO: this is the cheap, wrong version for avg. implement proper one (integral) later
                used = lic_state_data.aggregate(Avg('used')).itervalues().next()
                used_min = lic_state_data.aggregate(Min('used')).itervalues().next()
                used_max = lic_state_data.aggregate(Max('used')).itervalues().next()

                # TODO
                issued = lic_state_data.aggregate(Avg('issued')).itervalues().next()
                issued_min = lic_state_data.aggregate(Min('issued')).itervalues().next()
                issued_max = lic_state_data.aggregate(Max('issued')).itervalues().next()

                state_coarse = ext_license_state_coarse.objects.create(
                    ext_license_check_coarse=check_coarse,
                    ext_license_id=lic_id,
                    used=used,
                    used_min=used_min,
                    used_max=used_max,
                    issued=issued,
                    issued_min=issued_min,
                    issued_max=issued_max,
                    data_points=len(lic_state_data),
                )

                for vendor_lic_version in timespan_version_state_data.filter(ext_license_state__ext_license_id=lic_id).values("vendor", "ext_license_version").annotate(frequency=Count("pk")):
                    freq = vendor_lic_version['frequency']
                    ext_lic_id = vendor_lic_version['ext_license_version']
                    vendor_id = vendor_lic_version['vendor']
                    version_state_coarse = ext_license_version_state_coarse.objects.create(
                        ext_license_check_coarse=check_coarse,
                        ext_license_state_coarse=state_coarse,
                        ext_license_version_id=ext_lic_id,
                        vendor_id=vendor_id,
                        frequency=freq,
                    )

                    print 'version_state:', 'ver', vendor_lic_version['ext_license_version'], 'vendor', vendor_lic_version['vendor'], 'freq', vendor_lic_version['frequency']
                    _freq_cnt_sanity += freq
                    if freq == 0 and used_max != 0:
                        self.log("Warning: No license state state entries for license which is used. version: {}, license: {}, start: {}, end: {}".format(
                            vendor_lic_version['ext_license_version'], lic_id, start, end))

                    # usage:
                    version_state_usage_data = timespan_usage_data.filter(ext_license_version_state__ext_license_version_id=ext_lic_id,
                                                                          ext_license_version_state__vendor_id=vendor_id)
                    for usage_data in version_state_usage_data.values("ext_license_client", "ext_license_user", "num").annotate(frequency=Count("pk")):
                        ext_license_usage_coarse.objects.create(
                            ext_license_version_state_coarse=version_state_coarse,
                            ext_license_client_id=usage_data['ext_license_client'],
                            ext_license_user_id=usage_data['ext_license_user'],
                            num=usage_data['num'],
                            frequency=usage_data['frequency']
                        )

                        #print 'lic ver {} client {} user {} num {} freq {}'.format(ext_lic_id, usage_data['ext_license_client'], usage_data['ext_license_user'], usage_data['num'], usage_data['frequency'])

            print 'state freq counted: ', _freq_cnt_sanity
            if _freq_cnt_sanity != len(timespan_version_state_data):
                self.log("Warning: Lost version time entries ({}, {}), start: {}, end: {}".format(_freq_cnt_sanity, len(timespan_version_state_data), start, end))

        # check which data to collect
        for site in ext_license_site.objects.all():

            for duration_type in (ext_license_check_coarse.Duration.Month, ext_license_check_coarse.Duration.Day):
                try:
                    # make sure to only get date from db to stay consistent with its timezone
                    last_day = ext_license_check_coarse.objects.filter(duration_type=duration_type.ID, ext_license_site=site).latest('start_date')
                    next_start_time = last_day.end_date
                    self.log("Last archive data for duration {}: {}".format(duration_type.__name__, next_start_time))
                except ext_license_check_coarse.DoesNotExist:
                    # first run
                    self.log("No archive data found for duration {}, creating".format(duration_type.__name__))
                    earliest_datetime = ext_license_check.objects.filter(ext_license_site=site).earliest('date')
                    print earliest_datetime
                    next_start_time = duration_type.get_time_frame_start(earliest_datetime.date)
                    print next_start_time

                do_loop = True
                last_time = time.time()
                while do_loop:
                    print 'took ', time.time() - last_time 
                    last_time = time.time()
                    # check if we can calculate next day
                    next_end_time = duration_type.get_end_time_for_start(next_start_time)
                    print 'end', next_end_time
                    try:
                        first_later_check = ext_license_check.objects.filter(date__gt=next_end_time, ext_license_site=site).earliest('date')
                    except ext_license_check.DoesNotExist:
                        # no check later then the end time found, we have to wait until first next check is here
                        first_later_check = None
                        do_loop = False
                        self.log("No data after {} found, not archiving further".format(next_end_time))

                    if first_later_check:
                        self.log("creating entry for {} {}".format(duration_type.__name__, next_start_time))
                        print("creating entry for {} {}".format(duration_type.__name__, next_start_time))
                        create_timespan_entry_from_raw_data(next_start_time, next_end_time, duration_type=duration_type, site=site)

                        next_start_time = next_end_time

    def _update_lic(self, elo_obj):
        elo_obj.read()
        lic_xml = self._parse_actual_license_usage(elo_obj.licenses, elo_obj.config)
        elo_obj.feed_xml_result(lic_xml)
        # sge_license_tools.update_usage(actual_licenses, srv_result)
        # sge_license_tools.set_sge_used(actual_licenses, sge_license_tools.parse_sge_used(self._sge_dict))
        # for log_line, log_level in sge_license_tools.handle_complex_licenses(actual_licenses):
        #    if log_level > logging_tools.LOG_LEVEL_WARN:
        #        self.log(log_line, log_level)
        # sge_license_tools.calculate_usage(actual_licenses)
        configured_lics = [_key for _key, _value in elo_obj.licenses.iteritems() if _value.is_used]
        self.write_ext_data(elo_obj.licenses)
        if self._modify_sge:
            self._set_sge_global_limits(elo_obj.licenses, configured_lics)
        return lic_xml

    def _set_sge_global_limits(self, actual_licenses, configured_lics):
        _new_dict = {}
        for _cl in configured_lics:
            _lic = actual_licenses[_cl]
            _new_dict[_lic.name] = _lic.get_sge_available()
        # log differences
        _diff_keys = [_key for _key in _new_dict.iterkeys() if _new_dict[_key] != self._sge_lic_set.get(_key, None)]
        if _diff_keys:
            self.log(
                "changing {}: {}".format(
                    logging_tools.get_plural("global exec_host complex", len(_diff_keys)),
                    ", ".join(
                        [
                            "{}: {}".format(
                                _key,
                                "{:d} -> {:d}".format(
                                    self._sge_lic_set[_key],
                                    _new_dict[_key],
                                ) if _key in self._sge_lic_set else "{:d}".format(_new_dict[_key])
                            ) for _key in sorted(_diff_keys)
                        ]
                    )
                )
            )
        ac_str = ",".join(["{}={:d}".format(_lic_to_use, _new_dict[_lic_to_use]) for _lic_to_use in configured_lics])
        if ac_str:
            _mod_stat, _mod_out = sge_license_tools.call_command(
                "{} -mattr exechost complex_values {} global".format(self._sge_dict["QCONF_BIN"], ac_str),
                0,
                True,
                self.log
            )

    def _parse_actual_license_usage(self, actual_licenses, act_conf):
        # build different license-server calls
        # see loadsensor.py
        all_server_addrs = set(
            [
                "{:d}@{}".format(act_lic.get_port(), act_lic.get_host()) for act_lic in actual_licenses.values() if act_lic.license_type == "simple"
            ]
        )
        # print "asa:", all_server_addrs
        q_s_time = time.time()
        for server_addr in all_server_addrs:
            if server_addr not in self.__lc_dict:
                self.log("init new license_check object for server {}".format(server_addr))
                self.__lc_dict[server_addr] = sge_license_tools.license_check(
                    lmutil_path=os.path.join(
                        act_conf["LMUTIL_PATH"]
                    ),
                    port=int(server_addr.split("@")[0]),
                    server=server_addr.split("@")[1],
                    log_com=self.log
                )
            lic_xml = self.__lc_dict[server_addr].check(license_names=actual_licenses)
            # FIXME, srv_result should be stored in a list and merged
        q_e_time = time.time()
        self.log(
            "{} to query, took {}: {}".format(
                logging_tools.get_plural("license server", len(all_server_addrs)),
                logging_tools.get_diff_time_str(q_e_time - q_s_time),
                ", ".join(all_server_addrs)
            )
        )
        return lic_xml

    def write_ext_data(self, actual_licenses):
        drop_com = server_command.srv_command(command="set_vector")
        add_obj = drop_com.builder("values")
        cur_time = time.time()
        for lic_stuff in actual_licenses.itervalues():
            for cur_mve in lic_stuff.get_mvect_entries(hm_classes.mvect_entry):
                cur_mve.valid_until = cur_time + 120
                add_obj.append(cur_mve.build_xml(drop_com.builder))
        drop_com["vector_loadsensor"] = add_obj
        drop_com["vector_loadsensor"].attrib["type"] = "vector"
        send_str = unicode(drop_com)
        self.log("sending {:d} bytes to vector_socket".format(len(send_str)))
        self.vector_socket.send_unicode(send_str)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.vector_socket.close()
        self.__log_template.close()
