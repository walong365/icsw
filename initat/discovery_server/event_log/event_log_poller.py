# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
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
import collections

from django.db import connection
import pymongo

from initat.cluster.backbone.models.functions import memoize_with_expiry
from initat.cluster.backbone.models import device, ComCapability, net_ip
from initat.cluster.backbone.routing import srv_type_routing
from initat.discovery_server.event_log.wmi_event_log_scanner import WmiEventLogScanner
from initat.tools import logging_tools, threading_tools, config_tools, process_tools

from initat.discovery_server.config import global_config


class EventLogPollerProcess(threading_tools.process_obj):

    MAX_CONCURRENT_JOBS = 5

    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"],
                                                       zmq=True, context=self.zmq_context)
        connection.close()
        # self.register_func("wmi_scan", self._wmi_scan)

        self.register_timer(self.periodic_update, 60 * 5 if global_config["DEBUG"] else 60 * 15, instant=True)
        self.register_timer(self.job_control, 5, instant=True)

        self._init_db()

        # jobs are added here then processed sequentially
        self.run_queue = collections.deque()
        self.jobs_running = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _init_db(self):
        self._mongodb_client = pymongo.MongoClient(global_config["MONGODB_HOST"], global_config["MONGODB_PORT"])
        self._mongodb_database = self._mongodb_client.icsw_event_log

        self._mongodb_database.wmi_event_log.create_index([('$**', 'text')], name="wmi_log_full_text_index")
        # self._mongodb_database.wmi_event_log.create_index([('device_pk', 'text')])

    def periodic_update(self):
        self._schedule_wmi_updates()
        # ipmi_capability = ComCapability.objects.get(matchcode=ComCapability.MatchCode.ipmi.name)
        # print 'ipmi devs', device.objects.filter(com_capability_list=ipmi_capability, enable_perfdata=True)

    def job_control(self):
        # called periodically
        self.log("Calling job_control")
        for job in self.jobs_running[:]:
            do_continue = False
            try:
                self.log("periodic_check on {}".format(job))
                do_continue = job.periodic_check()
            except Exception as e:
                self.log("Error while checking job {}: {}".format(job, e))
                self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
            if not do_continue:
                self.jobs_running.remove(job)

        while len(self.jobs_running) < self.__class__.MAX_CONCURRENT_JOBS and self.run_queue:
            new_job = self.run_queue.popleft()
            try:
                new_job.start()
            except Exception as e:
                self.log("Error while starting job {}: {}".format(new_job, e))
                self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.jobs_running.append(new_job)

    def _schedule_wmi_updates(self):
        self.log("updating wmi logs")
        wmi_capability = ComCapability.objects.get(matchcode=ComCapability.MatchCode.wmi.name)
        wmi_devices = device.objects.filter(com_capability_list=wmi_capability, enable_perfdata=True)
        print 'wmi devs', wmi_devices

        _last_entries_qs = self._mongodb_database.wmi_event_log.aggregate([{
            '$group': {
                '_id': '$device_pk',
                'latest_event_id': {'$max': '$event_id'},
            }
        }])
        last_entries_lut = {entry['_id']: entry['latest_event_id'] for entry in _last_entries_qs}

        # self._mongodb_database.wmi_event_log.find_one(sort=[("id", -1)])

        for wmi_dev in wmi_devices:
            try:
                ip = self._get_ip_to(wmi_dev)
            except RuntimeError as e:
                self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
            else:



                self.log("updating wmi logs of {} using {}".format(wmi_dev, ip))
                # TODO: get entries up to last_entry or all of them
                #if wmi_dev.pk in last_entries_lut:
                #    last_entries[wmi_pk]

                try:
                    scanner = WmiEventLogScanner(log=self.log, target_device=wmi_dev, target_ip=ip,
                                                 last_known_record_number=last_entries_lut.get(wmi_dev.pk))
                except RuntimeError as e:
                    self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.run_queue.append(scanner)

        self.log("finished updating wmi logs")

    def _get_ip_to(self, to_dev):
        from_server_check = config_tools.server_check(device=srv_type_routing().local_device, config=None,
                                                      server_type="node")
        to_server_check = config_tools.server_check(device=to_dev, config=None, server_type="node")

        route = from_server_check.get_route_to_other_device(self._get_router_obj(), to_server_check,
                                                            allow_route_to_other_networks=True,
                                                            prefer_production_net=True)

        if route:
            ip = route[-1][3][1][0]
        else:
            ip_db = net_ip.objects.filter(netdevice__device=to_dev).first()
            if ip_db:
                ip = ip_db.ip
            else:
                raise RuntimeError("Failed to find IP address of {}".format(to_dev))
        return ip

    @memoize_with_expiry(10)
    def _get_router_obj(self):
        return config_tools.router_object(self.log)