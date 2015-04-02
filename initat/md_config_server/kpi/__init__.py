# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>
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
import json
# noinspection PyUnresolvedReferences
import pprint
from django.db import connection
import itertools
import memcache
import time
import initat.collectd.aggregate
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.cluster.backbone.models.kpi import KpiSelectedDeviceMonitoringCategoryTuple, Kpi
from initat.md_config_server.config.objects import global_config
from initat.md_config_server.common import live_socket
from initat.md_config_server.kpi.kpi_language import KpiObject
import logging_tools
import threading_tools


class kpi_process(threading_tools.process_obj):

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()

        # TODO: possibly like this:
        # self.register_func("update_kpi", self.update)

        self.register_timer(self.update, 30 if global_config["DEBUG"] else 300, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def update(self):
        #self.get_memcached_data()

        self["run_flag"] = False
        self["exit_requested"] = True

        # recalculate kpis

        # check db for kpi definitions
        # gather data
        try:
            icinga_socket = live_socket.get_icinga_live_socket()
        except IOError as e:
            self.log(unicode(e), logging_tools.LOG_LEVEL_ERROR)
        else:

            # get hosts and services of categories
            # get checks for kpis

            if Kpi.objects.filter(uses_all_data=True).exists():
                # TODO
                pass

            else:
                queryset = KpiSelectedDeviceMonitoringCategoryTuple.objects.all()\
                    .select_related("monitoring_category", "device_category")

            # TODO: uses_all_data
            # simulate distinct
            dev_mon_tuple_already_checked = dict()
            for item in queryset:
                if not (item.device_category_id, item.monitoring_category_id) in dev_mon_tuple_already_checked:
                    print 'gather for', item.monitoring_category, 'x', item.device_category

                    devices = item.device_category.device_set.values_list('name', flat=True)
                    checks = item.monitoring_category.mon_check_command_set.values_list('pk', flat=True)

                    kpi_objects = []

                    for dev_pk in devices:
                        for check_pk in checks:
                            description = host_service_id_util.create_host_service_description(dev_pk, check_pk, info="")
                            # TODO: check if we can reference special check commands this way
                            service_query = icinga_socket.services.columns("host_name",
                                                                           "description",
                                                                           "check_type",
                                                                           "plugin_output",
                                                                           "state_type")
                            service_query.filter("description", "~", description)  # ~ means regular expression match
                            result = json.loads(service_query.call())
                            self.log('res {}'.format(result))
                            print('res {}'.format(result))

                            # TODO: fill result in dict
                            properties = {}

                            kpi_objects.append(
                                KpiObject(properties=properties, result=None)
                            )

                    dev_mon_tuple_already_checked[(item.device_category_id, item.monitoring_category_id)] = kpi_objects

        # calculate kpis, such that drill down data is present
        pass

    def get_memcached_data(self):
        mc = memcache.Client([global_config["MEMCACHE_ADDRESS"]])
        try:
            host_list = json.loads(mc.get("cc_hc_list"))
        except Exception as e:
            self.log(unicode(e), logging_tools.LOG_LEVEL_ERROR)
        else:
            print 'hl', host_list

            for host_uuid, host_data in host_list.iteritems():
                if host_data[0] + 10*60 < time.time():
                    self.log("data for {} is very old ({})".format(host_data[1], time.ctime(host_data[0])))

                values_list = json.loads(mc.get("cc_hc_{}".format(host_uuid)))
                print 'host', host_data[1]
                for val in values_list:
                    vector_entry = initat.collectd.aggregate.ve(*val)
                    print vector_entry, vector_entry.get_value()
