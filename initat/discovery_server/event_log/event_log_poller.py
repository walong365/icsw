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
import datetime
import django.utils.timezone
import traceback

from django.db import connection
import pymongo

from initat.cluster.backbone.models.functions import memoize_with_expiry
from initat.cluster.backbone.models import device, ComCapability, net_ip
from initat.cluster.backbone.routing import srv_type_routing
from initat.discovery_server.event_log.ipmi_event_log_scanner import IpmiLogJob
from initat.discovery_server.event_log.wmi_event_log_scanner import WmiLogEntryJob, WmiLogFileJob
from initat.tools import logging_tools, threading_tools, config_tools, process_tools

from initat.discovery_server.config import global_config


class EventLogPollerProcess(threading_tools.process_obj):

    PROCESS_NAME = 'event_log_poller'

    MAX_CONCURRENT_JOBS = 5

    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"],
                                                       zmq=True, context=self.zmq_context)
        connection.close()
        # self.register_func("wmi_scan", self._wmi_scan)

        self.register_timer(self.periodic_update, 60 * 1 if global_config["DEBUG"] else 60 * 15, instant=True)
        self.register_timer(self.job_control, 2 if global_config["DEBUG"] else 5, instant=True)

        self._init_db()

        # jobs are added here then processed sequentially
        self.run_queue = collections.deque()
        self.jobs_running = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _init_db(self):
        self._mongodb_client = pymongo.MongoClient(global_config["MONGODB_HOST"], global_config["MONGODB_PORT"],
                                                   tz_aware=True)
        self._mongodb_database = self._mongodb_client.icsw_event_log

        self._mongodb_database.wmi_event_log.create_index([('$**', 'text')], name="wmi_log_full_text_index")
        # self._mongodb_database.wmi_event_log.create_index([('device_pk', 'text')])

    def periodic_update(self):
        self._schedule_wmi_jobs()
        self._schedule_ipmi_jobs()

    def job_control(self):
        # called periodically
        self.log("Calling job_control on jobs: {}".format(self.jobs_running))
        for job in self.jobs_running[:]:
            do_continue = False
            try:
                # self.log("periodic_check on {}".format(job))
                do_continue = job.periodic_check()
            except Exception as e:
                self.log("Error for checking job {}: {}".format(job, e))
                self.log(traceback.format_exc())
            if not do_continue:
                self.log("Job {} finished".format(job))
                self.jobs_running.remove(job)

        have_new_job = True
        while len(self.jobs_running) < self.__class__.MAX_CONCURRENT_JOBS and have_new_job:
            new_job = self._select_next_job()
            if new_job is None:
                have_new_job = False
            else:
                try:
                    new_job.start()
                except Exception as e:
                    self.log("Error while starting job {}: {}".format(new_job, e))
                    self.log(traceback.format_exc())
                else:
                    self.log("Adding new job: {}".format(new_job))
                    self.jobs_running.append(new_job)

    def _select_next_job(self):
        chosen_one = None
        for job in self.run_queue:  # prefer first (fifo)
            # not too many per device
            not_too_many_jobs_on_same_machine =\
                sum(1 for _j in self.jobs_running if job.target_device == _j.target_device) < 2

            # the last scan job for this log might not have finished yet
            not_same_job_running = not any(job == _j for _j in self.jobs_running)

            if not_too_many_jobs_on_same_machine and not_same_job_running:
                chosen_one = job
                break

        if chosen_one is not None:
            self.run_queue.remove(chosen_one)
        return chosen_one

    def _schedule_wmi_jobs(self):
        self.log("scheduling new wmi jobs")
        wmi_capability = ComCapability.objects.get(matchcode=ComCapability.MatchCode.wmi.name)
        wmi_devices = device.objects.filter(com_capability_list=wmi_capability, enable_perfdata=True)
        print 'wmi devs', wmi_devices

        _last_entries_qs = self._mongodb_database.wmi_event_log.aggregate([{
            '$group': {
                '_id': {
                    'device_pk': '$device_pk',
                    'logfile_name': '$logfile_name',
                },
                'latest_record_number': {'$max': '$maximal_record_number'},
            }
        }])
        last_record_numbers_lut = {  # mapping { (device_pk, logfile_name) : latest_record_number }
            (entry['_id']['device_pk'], entry['_id']['logfile_name']): entry['latest_record_number']
            for entry in _last_entries_qs
        }

        logfiles_by_device = {entry['device_pk']: entry for entry in
                              self._mongodb_database.wmi_logfile.find()}
        logfiles_list_deprecation = django.utils.timezone.now() - datetime.timedelta(seconds=60 * 60 * 12)

        for wmi_dev, ip in self._get_ip_to_multiple_hosts(wmi_devices).iteritems():
            if wmi_dev.pk not in logfiles_by_device or \
                    logfiles_by_device[wmi_dev.pk]['date'] < logfiles_list_deprecation:
                # need to find the logfiles first
                self.log("updating wmi logfiles of {} using {}".format(wmi_dev, ip))
                try:
                    job = WmiLogFileJob(log=self.log, db=self._mongodb_database, target_device=wmi_dev,
                                        target_ip=ip)
                except RuntimeError as e:
                    self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.run_queue.append(job)

            else:
                logfiles = logfiles_by_device[wmi_dev.pk]['logfiles']
                self.log("updating wmi logs of {} using {} for logfiles: {}".format(wmi_dev, ip, logfiles))

                for logfile_name in logfiles:
                    last_known_record_number = last_record_numbers_lut.get((wmi_dev.pk, logfile_name))
                    try:
                        job = WmiLogEntryJob(log=self.log,
                                             db=self._mongodb_database,
                                             logfile_name=logfile_name,
                                             target_device=wmi_dev,
                                             target_ip=ip,
                                             last_known_record_number=last_known_record_number)
                    except RuntimeError as e:
                        self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.run_queue.append(job)

        self.log("finished scheduling new wmi jobs")

    def _schedule_ipmi_jobs(self):
        self.log("scheduling new ipmi jobs")
        ipmi_capability = ComCapability.objects.get(matchcode=ComCapability.MatchCode.ipmi.name)
        ipmi_devices = device.objects.filter(com_capability_list=ipmi_capability, enable_perfdata=True)
        print 'ipmi devs', ipmi_devices

        _last_entries_qs = self._mongodb_database.ipmi_event_log.aggregate([{
            '$group': {
                '_id': '$device_pk',
                'latest_record_id': {'$max': '$record_id'},
            }
        }])
        last_record_ids_lut = {  # mapping { device_pk : latest_record_id }
            entry['_id']: entry['latest_record_id'] for entry in _last_entries_qs
        }

        for ipmi_dev, ip in self._get_ip_to_multiple_hosts(ipmi_devices).iteritems():
            try:
                print 'ipmi de', ipmi_dev, ipmi_dev.pk, last_record_ids_lut.get(ipmi_dev.pk)
                job = IpmiLogJob(log=self.log,
                                 db=self._mongodb_database,
                                 target_device=ipmi_dev,
                                 target_ip=ip,
                                 last_known_record_id=last_record_ids_lut.get(ipmi_dev.pk))

            except RuntimeError as e:
                self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.run_queue.append(job)

        self.log("finished scheduling new ipmi jobs")

    def _get_ip_to_multiple_hosts(self, host_list):
        ret = {}
        for dev in host_list:
            try:
                ret[dev] = self._get_ip_to_host(dev)
            except RuntimeError as e:
                self.log("Failed to get ip to host {}: {}".format(dev, e))
                self.log(traceback.format_exc())
        return ret

    def _get_ip_to_host(self, to_dev):
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
