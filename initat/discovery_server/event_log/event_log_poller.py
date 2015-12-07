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
import traceback

import django.utils.timezone
import pymongo
from pymongo.errors import PyMongoError

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, ComCapability, net_ip
from initat.cluster.backbone.models.functions import memoize_with_expiry
from initat.cluster.backbone.routing import SrvTypeRouting
from initat.cluster.frontend.discovery_views import MongoDbInterface
from initat.discovery_server.config import global_config
from initat.discovery_server.event_log.ipmi_event_log_scanner import IpmiLogJob
from initat.discovery_server.event_log.wmi_event_log_scanner import WmiLogEntryJob, WmiLogFileJob
from initat.tools import logging_tools, threading_tools, config_tools, process_tools


class EventLogPollerProcess(threading_tools.process_obj):

    PROCESS_NAME = 'event_log_poller'

    MAX_CONCURRENT_JOBS = 5

    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"],
                                                       zmq=True, context=self.zmq_context)
        db_tools.close_connection()

        self.register_timer(self.periodic_update, 60 * 1 if global_config["DEBUG"] else 60 * 15, instant=True)
        self.register_timer(self.job_control, 1 if global_config["DEBUG"] else 3, instant=True)

        self._mongodb_inited = False

        # jobs are added here then processed sequentially
        self._run_queue = collections.deque()
        self.jobs_running = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _init_db(self):
        self._mongodb_database = MongoDbInterface().event_log_db

        self._mongodb_database.wmi_event_log.create_index([('$**', 'text')], name="wmi_log_full_text_index")
        self._mongodb_database.wmi_event_log.create_index('device_pk', name='device_pk_index')
        self._mongodb_database.wmi_event_log.create_index('logfile_name', name='logfile_name_index')
        self._mongodb_database.wmi_event_log.create_index('record_number', name='record_number_index')
        self._mongodb_database.wmi_event_log.create_index('time_generated', name='time_generated_index')

        self._mongodb_database.wmi_event_log.create_index(
            [('time_generated', pymongo.DESCENDING), ('record_number', pymongo.DESCENDING)],
            name='sort_index',
        )

        self._mongodb_database.ipmi_event_log.create_index([('$**', 'text')], name="ipmi_log_full_text_index")
        # for sorting:
        self._mongodb_database.ipmi_event_log.create_index([('creation_date', pymongo.DESCENDING)],
                                                           name='creation_date_index')

        self.log("Set up mongodb successfully")

    def periodic_update(self):
        if not self._mongodb_inited:
            # do this here in case mongodb is installed after discovery-server has been started
            try:
                self._init_db()
            except PyMongoError as e:
                self.log("Failed to connect to mongodb: {}".format(e), logging_tools.LOG_LEVEL_WARN)
                self.log(traceback.format_exc(), logging_tools.LOG_LEVEL_WARN)
            else:
                self._mongodb_inited = True

        if self._mongodb_inited:
            # only add jobs if we know that mongodb is accessible
            self._schedule_wmi_jobs()
            self._schedule_ipmi_jobs()

    def job_control(self):
        # called periodically
        # self.log("Calling job_control on jobs: {}".format(self.jobs_running))
        for job in self.jobs_running[:]:
            # set to False to remove jobs which throw an error
            do_continue = False
            try:
                # self.log("periodic_check on {}".format(job))
                do_continue = job.periodic_check()
            except Exception as e:
                self.log("Error for checking job {}: {}".format(job, e), logging_tools.LOG_LEVEL_ERROR)
                self.log(traceback.format_exc(), logging_tools.LOG_LEVEL_ERROR)
            if not do_continue:
                self.log("Job {} finished".format(job))
                self.jobs_running.remove(job)
                self._log_current_jobs()

        have_new_job = True
        while len(self.jobs_running) < self.__class__.MAX_CONCURRENT_JOBS and have_new_job:
            new_job = self._select_next_job()
            if new_job is None:
                have_new_job = False
            else:
                try:
                    new_job.start()
                except Exception as e:
                    self.log("Error while starting job {}: {}".format(new_job, e), logging_tools.LOG_LEVEL_ERROR)
                    self.log(traceback.format_exc(), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("Adding new job: {}".format(new_job))
                    self.jobs_running.append(new_job)
                    self._log_current_jobs()

    def _log_current_jobs(self):
        if global_config['DEBUG']:
            self.log("Current jobs ({}):".format(len(self.jobs_running)))
            for job in self.jobs_running:
                self.log("  {}".format(job))

    def _select_next_job(self):
        chosen_one = None
        for job in self._run_queue:  # prefer first (fifo)
            # not too many per device
            not_too_many_jobs_on_same_machine =\
                sum(1 for _j in self.jobs_running if job.target_device == _j.target_device) < 2

            # the last scan job for this log might not have finished yet
            not_same_job_running = not self._is_job_already_running(job)

            if not_too_many_jobs_on_same_machine and not_same_job_running:
                chosen_one = job
                break

        if chosen_one is not None:
            self._run_queue.remove(chosen_one)
        return chosen_one

    def _is_job_already_running(self, job):
        return any(job == _j for _j in self.jobs_running)

    def _schedule_wmi_jobs(self):
        self.log("scheduling new wmi jobs")
        wmi_capability = ComCapability.objects.get(matchcode=ComCapability.MatchCode.wmi.name)
        wmi_devices = device.objects.filter(com_capability_list=wmi_capability, enable_perfdata=True)

        _last_entries_qs = self._mongodb_database.wmi_logfile_maximal_record_number.find()
        last_record_numbers_lut = {  # mapping { (device_pk, logfile_name) : latest_record_number }
            (entry['device_pk'], entry['logfile_name']): entry['maximal_record_number']
            for entry in _last_entries_qs
        }
        self.log("last rec numbers lut: {}".format(last_record_numbers_lut))

        logfiles_by_device = {entry['device_pk']: entry for entry in
                              self._mongodb_database.wmi_logfile.find()}
        logfiles_list_deprecation = django.utils.timezone.now() - datetime.timedelta(seconds=60 * 60 * 12)

        # we sometimes run jobs to find new logfiles, regular scans only retrieve entries for known logfiles
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
                    if not self._is_job_already_running(job):
                        self._run_queue.append(job)

            else:
                logfiles = logfiles_by_device[wmi_dev.pk]['logfiles']
                self.log("updating wmi logs of {} using {} for logfiles: {}".format(wmi_dev, ip, logfiles))

                for logfile_name in logfiles:
                    last_known_record_number = last_record_numbers_lut.get((wmi_dev.pk, logfile_name))

                    self.log('last for {} is {} '.format((wmi_dev.pk, logfile_name), last_known_record_number))
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
                        if not self._is_job_already_running(job):
                            self._run_queue.append(job)

        self.log("finished scheduling new wmi jobs")

    def _schedule_ipmi_jobs(self):
        self.log("scheduling new ipmi jobs")
        ipmi_capability = ComCapability.objects.get(matchcode=ComCapability.MatchCode.ipmi.name)
        ipmi_devices = device.objects.filter(com_capability_list=ipmi_capability, enable_perfdata=True)

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
                job = IpmiLogJob(log=self.log,
                                 db=self._mongodb_database,
                                 target_device=ipmi_dev,
                                 target_ip=ip,
                                 last_known_record_id=last_record_ids_lut.get(ipmi_dev.pk))

            except RuntimeError as e:
                self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
            else:
                if not self._is_job_already_running(job):
                    self._run_queue.append(job)

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
        from_server_check = config_tools.server_check(device=SrvTypeRouting().local_device, config=None,
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
