# Copyright (C) 2015,2017 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from __future__ import unicode_literals, print_function

import collections
import json
import operator
import time

import memcache
from django.db.models import Q

from initat.cluster.backbone.models import device, mon_check_command, Kpi, KpiDataSourceTuple,\
    category
from initat.cluster.backbone.models.kpi import DataSourceTuple
from initat.md_config_server.icinga_log_reader.log_aggregation import icinga_log_aggregator
from initat.md_config_server.icinga_log_reader.log_reader_utils import host_service_id_util
from initat.md_config_server.kpi.kpi_language import KpiObject, KpiResult, KpiRRDObject, \
    KpiServiceObject, KpiSet
from initat.md_sync_server.common import LiveSocket
from initat.tools import logging_tools


class KpiData(object):
    """Data retrieval methods (mostly functions actually)

    Retrieves all data on construction.
    Data can be retrieved via get_kpi_set_for_kpi and get_kpi_set_for_dev_mon_cat_tuples
    """

    def __init__(self, log, dev_mon_cat_tuples=None):
        """
        :param dev_mon_cat_tuples: if specified, only load data for these dev_mon_cat tuples
        """
        self.log = log
        self._mccs = {
            mcc.pk: mcc for mcc in mon_check_command.objects.all()
        }

        self.data_source_tuples = None if dev_mon_cat_tuples is None else [
            DataSourceTuple(
                device_category=category.objects.get(Q(pk=tup[0])),
                monitoring_category=category.objects.get(Q(pk=tup[1])),
            ) for tup in dev_mon_cat_tuples
        ]

        self._load_data()

    def get_kpi_set_for_kpi(self, kpi_db):
        dev_mon_tuples = kpi_db.kpidatasourcetuple_set.all()

        if kpi_db.has_historic_data():
            start, end = kpi_db.get_time_range()
        else:
            start, end = None, None

        return self._get_kpi_set_for_source_tuples(dev_mon_tuples, start, end)

    def get_kpi_set_for_dev_mon_cat_tuples(self, start=None, end=None):
        if self.data_source_tuples is None:
            raise ValueError()
        return self._get_kpi_set_for_source_tuples(
            self.data_source_tuples,
            start=start,
            end=end,
        )

    def _get_kpi_set_for_source_tuples(self, tuples, start=None, end=None):
        """
        Retrieves current results for (dev, mon)
        :rtype: list of KpiObject
        """
        dev_mon_tuples, dev_list = self._get_dev_mon_tuples_from_category_tuples(tuples)

        if start is not None:

            timespan_hosts_qs, timespan_services_qs =\
                icinga_log_aggregator.get_active_hosts_and_services_in_timespan_queryset(start, end)

            timespan_hosts_qs = timespan_hosts_qs.filter(device__in=dev_list)

            timespan_hosts = set(timespan_hosts_qs)

            if dev_mon_tuples:
                timespan_services_qs = timespan_services_qs.filter(
                    reduce(operator.or_, (Q(device_id=dev_id, service_id=mcc.pk) for (dev_id, mcc) in dev_mon_tuples))
                )
            else:
                timespan_services_qs = []

            timespan_services = set(timespan_services_qs)
        else:
            timespan_hosts, timespan_services = set(), set()

        # add kpi objects to result list, check off historical data which is present there
        kpi_objects = []
        for dev in dev_list:
            if self.host_data[dev.pk].rrd_data is not None:
                kpi_objects.extend(self.host_data[dev.pk].rrd_data)
            kpi_objects.extend(
                self.host_data[dev.pk].host_check_results
            )
            timespan_hosts.discard(dev.pk)

        dev_services_used = {dev: [] for dev in dev_list}
        # noinspection PyTypeChecker
        for dev, mcc in dev_mon_tuples:
            dev_services_used[dev].append(mcc)
            service_kpi_objects = self.host_data[dev.pk].service_check_results[mcc.pk]
            kpi_objects.extend(service_kpi_objects)

            for service_kpi_obj in service_kpi_objects:
                timespan_services.discard(
                    (
                        service_kpi_obj.host_pk,
                        service_kpi_obj.service_id,
                        service_kpi_obj.service_info,
                    )
                )

        # LicenseUsage.log_usage(LicenseEnum.kpi, LicenseParameterTypeEnum.device, dev_services_used.iterkeys())
        # LicenseUsage.log_usage(LicenseEnum.kpi, LicenseParameterTypeEnum.service, dev_services_used)

        # now timespan_hosts and timespan_services_qs contain historical data, which is currently not present anymore
        for missing_dev_pk in timespan_hosts:
            try:
                dev_obj = device.objects.get(pk=missing_dev_pk)
            except device.DoesNotExist:
                self.log("device {} has historical data but does not exist any more".format(missing_dev_pk))
            else:
                kpi_objects.append(
                    KpiObject(
                        host_pk=missing_dev_pk,
                        host_name=dev_obj.full_name,
                    )
                )

        for missing_dev_pk, missing_serv_pk, missing_serv_info in timespan_services:
            try:
                dev_obj = device.objects.get(pk=missing_dev_pk)
            except device.DoesNotExist:
                self.log("device {} has historical data but does not exist any more".format(missing_dev_pk))
            else:
                kpi_objects.append(
                    KpiServiceObject(
                        host_pk=missing_dev_pk,
                        host_name=dev_obj.full_name,
                        service_id=missing_serv_pk,
                        service_info=missing_serv_info,
                        mcc=self._mccs.get(missing_serv_pk, None),
                    )
                )

        return KpiSet(kpi_objects, origin=None)

    ##########################
    # private methods

    def _load_data(self):

        try:
            self.icinga_socket = LiveSocket.get_mon_live_socket(self.log)
        except IOError as e:
            self.log(u"error when opening monitoring socket: {}".format(e), logging_tools.LOG_LEVEL_ERROR)
            raise

        host_rrd_data = self._get_memcached_data()

        self.log("got rrd_data for {} hosts".format(len(host_rrd_data)))

        if self.data_source_tuples:
            dev_mon_tuples, dev_list = self._get_dev_mon_tuples_from_category_tuples(self.data_source_tuples)

        elif False and Kpi.objects.filter(uses_all_data=True).exists():  # DISABLED
            # self.kpi_device_categories = set(device.categories_set.all())
            # self.kpi_devices = list(device.objects.all())
            # self.kpi_mon_categories = list(mon_check_command.categories_set.all())

            dev_mon_tuples, dev_list = self._get_dev_mon_tuples_from_category_tuples(
                [
                    DataSourceTuple(kpi=None, device_category=dev_cat, monitoring_category=mon_cat)
                    for dev_cat in category.objects.get_device_categories()
                    for mon_cat in category.objects.get_monitoring_categories()
                ]
            )

        else:
            dev_mon_tuples, dev_list = self._get_dev_mon_tuples_from_category_tuples(
                KpiDataSourceTuple.objects.all().prefetch_related("device_category")
            )

        # this is merely internal to this class
        HostData = collections.namedtuple('HostData', ('rrd_data', 'host_check_results', 'service_check_results'))
        self.host_data = {}

        service_check_results = collections.defaultdict(lambda: {})
        for dev, mcc in dev_mon_tuples:

            service_check_results[dev.pk][mcc.pk] = self._get_service_check_results(dev, mcc)

        for dev in dev_list:
            self.host_data[dev.pk] = HostData(
                rrd_data=host_rrd_data.get(dev.pk, None),
                host_check_results=self._get_host_check_results(dev),
                service_check_results=service_check_results[dev.pk]
            )

    def _get_dev_mon_tuples_from_category_tuples(self, queryset):
        ":rtype: (set[device, mon_check_command], set[device]) "
        if hasattr(queryset, "prefetch_related"):
            queryset = queryset.prefetch_related('device_category', 'device_category__device_set')
            queryset = queryset.prefetch_related('monitoring_category', 'monitoring_category__mon_check_command_set')
        dev_mon_tuples = set()
        dev_list = set()
        for tup in queryset:
            for dev in tup.device_category.device_set.all():
                dev_list.add(dev)  # also add devs without checks
                for mcc in tup.monitoring_category.mon_check_command_set.all():
                    if (dev, mcc) not in dev_mon_tuples:
                        dev_mon_tuples.add((dev, mcc))

        return dev_mon_tuples, dev_list

    def _get_memcached_data(self):

        device_full_names = {
            entry.full_name: entry for entry in device.objects.all().prefetch_related('domain_tree_node')
        }

        from initat.md_config_server.config.objects import global_config
        mc = memcache.Client(
            [
                "{}:{:d}".format(
                    global_config["MEMCACHE_ADDRESS"].split(":")[0],
                    global_config["MEMCACHE_PORT"],
                )
            ]
        )
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
                    host_db = device_full_names[host_data[1]]
                except KeyError:
                    self.log(u"device {} does not exist but is referenced in rrd data".format(host_data[1]),
                             logging_tools.LOG_LEVEL_WARN)
                else:
                    if (host_data[0] + 60 * 60) < time.time():
                        self.log(u"data for {} is very old ({})".format(host_data[1], time.ctime(host_data[0])))

                    host_mc = mc.get("cc_hc_{}".format(host_uuid))
                    if host_mc is not None:
                        values_list = json.loads(host_mc)

                        vector_entries = (VE(*val) for val in values_list)

                        host_rrd_data[host_db.pk] = list(
                            KpiRRDObject(
                                host_name=host_data[1],
                                host_pk=host_db.pk,
                                rrd_id=ve.key,
                                rrd_name=ve.get_expanded_info(),
                                rrd_value=ve.get_value(),
                            ) for ve in vector_entries
                        )
                    else:
                        self.log(u"no memcache data for {} ({})".format(host_data[1], host_uuid))

        return host_rrd_data

    def _get_service_check_results(self, dev, mcc):
        service_query = self.icinga_socket.services.columns(
            # "host_name",
            "description",
            "state",
            # "last_check",
            # "check_type",
            # "state_type",
            # "last_state_change",
            # "plugin_output",
            # "display_name",
            # "current_attempt",
        )
        description = host_service_id_util.create_host_service_description_direct(
            dev.pk,
            mcc.pk,
            special_check_command_pk=mcc.mon_check_command_special_id,
            info=".*"
        )
        description = "^{}".format(description)  # need regex to force start to distinguish s_host_check and host_check

        service_query.filter("description", "~", description)  # ~ means regular expression match
        icinga_result = service_query.call()

        ret = []
        # this is usually only one except in case of special check commands
        for ir in icinga_result:
            try:
                service_info = host_service_id_util.parse_host_service_description(ir['description'])[2]
            except IndexError:
                service_info = None
            ret.append(
                KpiServiceObject(
                    result=KpiResult.from_numeric_icinga_service_state(int(ir['state'])),
                    host_name=dev.full_name,
                    host_pk=dev.pk,
                    service_id=mcc.pk,
                    service_info=service_info,
                    mcc=mcc,
                )
            )
        # self.log("got service check results: {}".format(ret))
        return ret

    def _get_host_check_results(self, dev):
        host_query = self.icinga_socket.hosts.columns(
            "name",
            "state",
            # "address",
            # "last_check",
            # "check_type",
            # "state_type",
            # "last_state_change",
            # "plugin_output",
            # "display_name",
            # "current_attempt",
        )
        host_query.filter("name", "~", dev.name)
        icinga_result = host_query.call()

        ret = list(
            KpiObject(
                result=KpiResult.from_numeric_icinga_host_state(int(ir['state'])),
                host_name=dev.full_name,
                host_pk=dev.pk,
            )
            for ir in icinga_result
        )

        # self.log("got host check results: {}".format(ret))
        return ret


class VE(object):
    # vector entry (duplicated in collectd.aggregate)
    def __init__(self, *args):
        self.format, self.key, self.info, self.unit, self.v_type, self.value, self.base, self.factor = args

    def __repr__(self):
        return u"ve {}".format(self.key)

    def get_value(self):
        return self.value * self.factor

    def get_expanded_info(self):
        # replace "$2" by 2nd part of key and so on
        expanded_info = self.info
        for num, subst in enumerate(self.key.split("."), start=1):
            expanded_info = expanded_info.replace("${}".format(num), subst)
        return expanded_info
