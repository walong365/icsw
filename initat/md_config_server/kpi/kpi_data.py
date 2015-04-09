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

import collections
import json
import time
import memcache
from initat.cluster.backbone.middleware import show_database_calls
from initat.cluster.backbone.models import device, mon_check_command, Kpi, KpiDataSourceTuple, category
import initat.collectd
from initat.md_config_server.common import live_socket
from initat.md_config_server.config.objects import global_config
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.md_config_server.kpi.kpi_language import KpiObject, KpiResult
import logging_tools


class KpiData(object):
    """Data retrieval methods (mostly functions actually)"""

    def __init__(self, log):
        self.log = log

        try:
            self.icinga_socket = live_socket.get_icinga_live_socket()
        except IOError as e:
            self.log(u"error when opening icinga socket: {}".format(e), logging_tools.LOG_LEVEL_ERROR)
            raise

        host_rrd_data = self._get_memcached_data()

        if Kpi.objects.filter(uses_all_data=True).exists():
            # self.kpi_device_categories = set(device.categories_set.all())
            # self.kpi_devices = list(device.objects.all())
            # self.kpi_mon_categories = list(mon_check_command.categories_set.all())

            dev_mon_tuples = self._get_dev_mon_tuples_from_category_tuples(
                [
                    KpiDataSourceTuple(kpi=None, device_category=dev_cat, monitoring_category=mon_cat)
                    for dev_cat in category.objects.get_device_categories()
                    for mon_cat in category.objects.get_monitoring_categories()
                ]
            )

        else:
            # self.kpi_device_categories = set(tup.device_category_id for tup in KpiDataSourceTuple.objects.all())

            # self.kpi_devices = set(device.objects.filter(categories__in=self.kpi_device_categories))

            # self.kpi_mon_categories = set(tup.monitoring_category_id for tup in KpiDataSourceTuple.objects.all())

            # self.kpi_mon_check_commands = set(mon_check_command.objects.filter(categories__in=self.kpi_mon_categories))

            dev_mon_tuples = self._get_dev_mon_tuples_from_category_tuples(
                KpiDataSourceTuple.objects.all().prefetch_related("device_category")
            )

        # this is merely internal to this class
        HostData = collections.namedtuple('HostData', ('rrd_data', 'host_check_results', 'service_check_results',
                                                       'historic_data'))
        self.host_data = {}

        service_check_results = collections.defaultdict(lambda: {})
        for dev, mcc in dev_mon_tuples:

            # TODO: historic. handle dynamic time ranges as function
            service_check_results[dev.pk][mcc.pk] = self._get_service_check_results(dev, mcc)

        for dev in {dev for (dev, _) in dev_mon_tuples}:
            self.host_data[dev.pk] = HostData(rrd_data=host_rrd_data.get(dev.pk, None),
                                              host_check_results=self._get_host_check_results(dev),
                                              service_check_results=service_check_results[dev.pk],
                                              historic_data=None)

    def get_data_for_kpi(self, kpi_db):
        return self.get_data_for_dev_mon_tuples(kpi_db.kpidatasourcetuple_set.all())

    def get_data_for_dev_mon_tuples(self, tuples):
        """
        :rtype: list of KpiObject
        """
        # NOTE: only used through get_data_for_kpi as of now
        kpi_objects = []
        dev_mon_tuples = self._get_dev_mon_tuples_from_category_tuples(tuples)

        for dev in {dev for (dev, _) in dev_mon_tuples}:
            if self.host_data[dev.pk].rrd_data is not None:
                kpi_objects.extend(self.host_data[dev.pk].rrd_data)
            kpi_objects.extend(
                self.host_data[dev.pk].host_check_results
            )
        for dev, mcc in dev_mon_tuples:
            kpi_objects.extend(
                self.host_data[dev.pk].service_check_results[mcc.pk]
            )
        return kpi_objects

    def _get_dev_mon_tuples_from_category_tuples(self, queryset):
        queryset = queryset.prefetch_related('device_category').prefetch_related('monitoring_category')
        dev_mon_tuples = set()
        for tup in queryset:
            for dev in tup.device_category.device_set.all():
                for mcc in tup.monitoring_category.mon_check_command_set.all():
                    if (dev, mcc) not in dev_mon_tuples:
                        dev_mon_tuples.add((dev, mcc))
        show_database_calls()
        return dev_mon_tuples

    def _get_memcached_data(self):
        mc = memcache.Client([global_config["MEMCACHE_ADDRESS"]])
        host_rrd_data = {}
        try:
            host_list_mc = mc.get("cc_hc_list")
            if host_list_mc is None:
                raise Exception("host list is None")
        except Exception as e:
            self.log(u"error when loading memcache host list: {}".format(e), logging_tools.LOG_LEVEL_ERROR)
        else:
            host_list = json.loads(host_list_mc)

            for host_uuid, host_data in host_list.iteritems():

                try:
                    host_db = device.objects.get(name=host_data[1])
                except device.DoesNotExist:
                    self.log(u"device {} does not exist but is referenced in rrd data".format(host_data[1]),
                             logging_tools.LOG_LEVEL_WARN)
                else:
                    if (host_data[0] + 60 * 60) < time.time():
                        self.log(u"data for {} is very old ({})".format(host_data[1], time.ctime(host_data[0])))

                    host_mc = mc.get("cc_hc_{}".format(host_uuid))
                    if host_mc is not None:
                        values_list = json.loads(host_mc)

                        vector_entries = (initat.collectd.aggregate.ve(*val) for val in values_list)

                        host_rrd_data[host_db.pk] = list(
                            KpiObject(
                                host_name=host_data[1],
                                rrd=ve,
                                properties={
                                    'rrd_key': ve.key,
                                    'rrd_value': ve.get_value(),
                                }
                            ) for ve in vector_entries
                        )
                    else:
                        self.log("no memcache data for {} ({})".format(host_data[1], host_uuid))

        return host_rrd_data

    def _get_service_check_results(self, dev, check):
        service_query = self.icinga_socket.services.columns("host_name",
                                                            "description",
                                                            "state",
                                                            "last_check",
                                                            "check_type",
                                                            "state_type",
                                                            "last_state_change",
                                                            "plugin_output",
                                                            "display_name",
                                                            "current_attempt",
                                                            )
        description = host_service_id_util.create_host_service_description_direct(
            dev.pk,
            check.pk,
            special_check_command_pk=check.mon_check_command_special_id,
            info=".*"
        )
        description = "^{}".format(description)  # need regex to force start to distinguish s_host_check and host_check

        service_query.filter("description", "~", description)  # ~ means regular expression match
        icinga_result = service_query.call()

        # this is usually only one except in case of special check commands
        ret = list(self.__create_kpi_obj(r, is_service=True) for r in icinga_result)
        self.log("got service check results: {}".format(ret))
        return ret

    def _get_host_check_results(self, dev):
        host_query = self.icinga_socket.hosts.columns("host_name",
                                                      "address",
                                                      "state",
                                                      "last_check",
                                                      "check_type",
                                                      "state_type",
                                                      "last_state_change",
                                                      "plugin_output",
                                                      "display_name",
                                                      "current_attempt",
                                                      )
        host_query.filter("host_name", "~", dev.name)
        icinga_result = host_query.call()

        ret = list(self.__create_kpi_obj(r, is_service=False) for r in icinga_result)
        self.log("got host check results: {}".format(ret))
        return ret

    def __create_kpi_obj(self, check_result, is_service):
            property_names = {  # icinga names with renamings (currently none used)
                                'display_name': None,
                                'current_attempt': None,
                                'last_state_change': None,
                                'plugin_output': None,
                                'last_check': None,
                                'description': None,
                                'state_type': None,
                                'address': None,
            }
            # TODO: if state type is supposed to be used, probably parse to something more readable
            properties = {(our_name if our_name is not None else icinga_name): check_result[icinga_name]
                          for icinga_name, our_name in property_names.iteritems() if icinga_name in check_result}

            if is_service:
                host_pk, service_pk, info = \
                    host_service_id_util.parse_host_service_description(check_result['description'])

                try:
                    properties['check_command'] = mon_check_command.objects.get(pk=service_pk).name
                except mon_check_command.DoesNotExist:
                    properties['check_command'] = None

            return KpiObject(
                result=KpiResult.from_numeric_icinga_service_status(int(check_result['state'])),
                host_name=check_result['host_name'],
                properties=properties,
            )

    def _get_historic_data(self):
        pass
