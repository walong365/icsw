# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, discovery part """

import time

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models.license import LicenseUsage, LicenseLockListDeviceService
from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models import device
from initat.snmp.struct import ResultNode, simple_snmp_oid
from initat.snmp.functions import simplify_dict, oid_to_str
from initat.snmp.sink import SNMPSink
from initat.snmp.databasemap import Schemes
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools

from .config import global_config
from .hm_functions import hm_mixin


class SNMPBatch(object):
    def __init__(self, srv_com):
        self.srv_com = srv_com
        self.id = SNMPBatch.next_snmp_batch_id()
        SNMPBatch.add_batch(self)
        self.init_run(self.srv_com["*command"])
        self.batch_valid = True
        try:
            _dev = self.srv_com.xpath(".//ns:devices/ns:device")[0]
            self.device = device.objects.get(Q(pk=_dev.attrib["pk"]))
            self.log("device is {}".format(unicode(self.device)))
            self.set_snmp_props(
                int(_dev.attrib["snmp_version"]),
                _dev.attrib["scan_address"],
                _dev.attrib["snmp_community"],
            )
            self.flags = {
                "strict": True if int(_dev.attrib.get("strict", "0")) else False,
            }
        except:
            _err_str = "error setting device node: {}".format(process_tools.get_except_info())
            self.log(_err_str, logging_tools.LOG_LEVEL_ERROR, result=True)
            self.batch_valid = False
            self.finish()
        else:
            if SNMPBatch.process.device_is_idle(self.device, "snmp"):
                self.log("SNMP scan started", result=True)
                self.start_run()
            else:
                self.log("device is locked by scan '{}'".format(self.device.active_scan), logging_tools.LOG_LEVEL_ERROR, result=True)
                self.batch_valid = False
                self.finish()
        self.send_return()

    def init_run(self, command):
        self.command = command
        self.__snmp_results = {}
        # (optional) mapping from run_id to snmp_scheme pk
        self.__start_time = time.time()
        self.log("init new batch with command {}".format(self.command))

    def start_run(self):
        if self.command == "snmp_basic_scan":
            _all_schemes = Schemes(self.log)
            self.new_run(
                True,
                20,
                *[
                    ("T*", [simple_snmp_oid(_tl_oid.oid)]) for _tl_oid in _all_schemes.all_tl_oids()
                ]
            )
        else:
            self.log("unknown command '{}'".format(self.command), logging_tools.LOG_LEVEL_ERROR, result=True)
            self.finish()

    def set_snmp_props(self, version, address, com):
        self.snmp_version = version
        self.snmp_address = address
        self.snmp_community = com
        self.log("set snmp props to {}@{} (v{:d})".format(self.snmp_community, self.snmp_address, self.snmp_version))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, result=False):
        SNMPBatch.process.log("[batch {:d}] {}".format(self.id, what), log_level)
        if result:
            self.srv_com.set_result(
                what,
                server_command.log_level_to_srv_reply(log_level)
            )

    def new_run(self, flag, timeout, *oid_list, **kwargs):
        if self.batch_valid:
            _run_id = SNMPBatch.next_snmp_run_id(self.id)
            self.__snmp_results[_run_id] = None
            SNMPBatch.process.send_pool_message(
                "snmp_run",
                self.snmp_version,
                self.snmp_address,
                self.snmp_community,
                _run_id,
                flag,
                timeout,
                *oid_list,
                **kwargs
            )
        else:
            self.log("cannot start run, batch is marked invalid", logging_tools.LOG_LEVEL_ERROR)

    def __del__(self):
        # print("delete batch {:d}".format(self.id))
        pass

    def feed_snmp(self, run_id, error, src, results):
        _res_dict = simplify_dict(results, (2, 1))
        self.__snmp_results[run_id] = (error, src, results)
        self.check_for_result()

    def check_for_result(self):
        if all(self.__snmp_results.values()):
            self.__end_time = time.time()
            # unify results
            # pprint.pprint(self.__snmp_results)
            # unify dict
            _errors, _found, _res_dict = ([], set(), {})
            for _key, _value in self.__snmp_results.iteritems():
                _errors.extend(_value[0])
                _found |= _value[1]
                _res_dict.update(_value[2])
            self.log(
                "finished batch in {} ({}, {})".format(
                    logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
                    logging_tools.get_plural("run", len(self.__snmp_results)),
                    logging_tools.get_plural("error", len(_errors)),
                )
            )
            attr_name = "handle_{}".format(self.command)
            if hasattr(self, attr_name):
                getattr(self, attr_name)(_errors, _found, _res_dict)
            else:
                self.log("dont know how to handle {}".format(self.command), logging_tools.LOG_LEVEL_ERROR, result=True)
                self.finish()

    def handle_snmp_initial_scan(self, errors, found, res_dict):
        _all_schemes = Schemes(self.log)
        _found_struct = {}
        # reorganize oids to dict with scheme -> {..., oid_list, ...}
        for _oid in found:
            _found_scheme = _all_schemes.get_scheme_by_oid(_oid)
            if _found_scheme:
                _key = (_found_scheme.priority, _found_scheme.pk)
                if _key not in _found_struct:
                    _found_struct[_key] = {
                        "scheme": _found_scheme,
                        "oids": set(),
                        "full_name": _found_scheme.full_name,
                    }
                _found_struct[_key]["oids"].add(oid_to_str(_oid))
        _handler = SNMPSink(self.log)
        result = ResultNode(error=errors)
        for _key in sorted(_found_struct, reverse=True):
            _struct = _found_struct[_key]
            result.merge(
                _handler.update(
                    self.device,
                    _struct["scheme"],
                    _all_schemes.filter_results(res_dict, _struct["oids"]),
                    _struct["oids"],
                    self.flags,
                )
            )
        self.srv_com.set_result(*result.get_srv_com_result())
        self.finish()

    def handle_snmp_basic_scan(self, errors, found, res_dict):
        _all_schemes = Schemes(self.log)
        if found:
            # any found, delete all present schemes
            self.device.snmp_schemes.clear()
        _added_pks = set()
        for _oid in found:
            _add_scheme = _all_schemes.get_scheme_by_oid(_oid)
            if _add_scheme is not None and _add_scheme.pk not in _added_pks:
                _added_pks.add(_add_scheme.pk)
                self.device.snmp_schemes.add(_add_scheme)
        if _added_pks:
            _scan_schemes = [_all_schemes.get_scheme(_pk) for _pk in _added_pks if _all_schemes.get_scheme(_pk).initial]
            if _scan_schemes:
                self.init_run("snmp_initial_scan")
                for _scheme in _scan_schemes:
                    self.new_run(
                        True,
                        20,
                        *[
                            ("T", [simple_snmp_oid(_tl_oid.oid)]) for _tl_oid in _scheme.snmp_scheme_tl_oid_set.all()
                        ]
                    )
            else:
                self.log("found {}".format(logging_tools.get_plural("scheme", len(_added_pks))), result=True)
                self.finish()
        else:
            if errors:
                self.log(", ".join(errors), logging_tools.LOG_LEVEL_ERROR, result=True)
            else:
                self.log("initial scan was ok, but no schemes found", logging_tools.LOG_LEVEL_WARN, result=True)
            self.finish()

    def finish(self):
        if self.device.active_scan:
            SNMPBatch.process.clear_scan(self.device)
        # self.send_return()
        SNMPBatch.remove_batch(self)

    def send_return(self):
        self.process.send_pool_message("remote_call_async_result", unicode(self.srv_com))

    @staticmethod
    def glob_feed_snmp(_run_id, error, src, results):
        SNMPBatch.batch_dict[SNMPBatch.run_batch_lut[_run_id]].feed_snmp(_run_id, error, src, results)
        del SNMPBatch.run_batch_lut[_run_id]

    @staticmethod
    def setup(proc):
        SNMPBatch.process = proc
        SNMPBatch.snmp_batch_id = 0
        SNMPBatch.snmp_run_id = 0
        SNMPBatch.pending = {}
        SNMPBatch.run_batch_lut = {}
        SNMPBatch.batch_dict = {}

    @staticmethod
    def next_snmp_run_id(batch_id):
        SNMPBatch.snmp_run_id += 1
        SNMPBatch.run_batch_lut[SNMPBatch.snmp_run_id] = batch_id
        return SNMPBatch.snmp_run_id

    @staticmethod
    def next_snmp_batch_id():
        SNMPBatch.snmp_batch_id += 1
        return SNMPBatch.snmp_batch_id

    @staticmethod
    def add_batch(batch):
        SNMPBatch.batch_dict[batch.id] = batch

    @staticmethod
    def remove_batch(batch):
        del SNMPBatch.batch_dict[batch.id]
        del batch


class DiscoveryProcess(threading_tools.process_obj, hm_mixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # self.add_process(build_process("build"), start=True)
        connection.close()
        self.register_func("fetch_partition_info", self._fetch_partition_info)
        self.register_func("scan_network_info", self._scan_network_info)
        self.register_func("snmp_basic_scan", self._snmp_basic_scan)
        self.register_func("snmp_result", self._snmp_result)
        self.__run_idx = 0
        self.__pending_commands = {}
        self._init_snmp()

    def _fetch_partition_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "fetch_partition_info", "hm")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _scan_network_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "scan_network_info", "hm")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _iterate(self, srv_com, c_name, scan_type):
        total_result = ResultNode()
        for _dev_xml in srv_com["devices"]:
            try:
                _dev = device.objects.get(Q(pk=int(_dev_xml.get("pk"))))
                if LicenseLockListDeviceService.objects.is_device_locked(LicenseEnum.discovery_server, _dev):
                    raise RuntimeError(u"Device {} is locked by license lock list for discovery server".format(_dev))
            except:
                res_node = ResultNode(error="device not available: {}".format(process_tools.get_except_info()))
            else:
                LicenseUsage.log_usage(LicenseEnum.discovery_server, LicenseParameterTypeEnum.device, _dev)

                if self.device_is_idle(_dev, scan_type):
                    s_time = time.time()
                    try:
                        res_node = getattr(self, c_name)(_dev_xml, _dev)
                    except:
                        res_node = ResultNode(error="device {}: error calling {}: {}".format(unicode(_dev), c_name, process_tools.get_except_info()))
                    self.clear_scan(_dev)
                else:
                    res_node = ResultNode(error="device {} is locked by scan {}".format(unicode(_dev), _dev.active_scan))
                e_time = time.time()
                self.log(u"calling {} for device {} took {}".format(c_name, unicode(_dev), logging_tools.get_diff_time_str(e_time - s_time)))
            total_result.merge(res_node)
        srv_com.set_result(*total_result.get_srv_com_result())

    def device_is_idle(self, dev, new_scan):
        # check if device dev is idle (no scans running)
        _idle = True
        if dev.active_scan:
            self.log(
                "device {} has an active scan running: '{}', cannot start new scan '{}'".format(
                    unicode(dev),
                    dev.active_scan,
                    new_scan,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _idle = False
        else:
            dev.active_scan = new_scan
            dev.save(update_fields=["active_scan"])
            self.log(
                "device {} has now the active scan '{}'".format(
                    unicode(dev),
                    new_scan,
                )
            )
        return _idle

    def clear_scan(self, dev):
        self.log("clearing active_scan '{}' of device {}".format(dev.active_scan, unicode(dev)))
        dev.active_scan = ""
        dev.save(update_fields=["active_scan"])

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(lev, what)

    def loop_post(self):
        self.__log_template.close()

    def _init_snmp(self):
        SNMPBatch.setup(self)

    def _snmp_basic_scan(self, *args, **kwargs):
        SNMPBatch(server_command.srv_command(source=args[0]))

    def _snmp_result(self, *args, **kwargs):
        _batch_id, _error, _src, _results = args
        SNMPBatch.glob_feed_snmp(_batch_id, _error, _src, _results)
