# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

""" monitoring views """

import StringIO
import base64
import collections
import datetime
import json
import logging
import socket
import uuid
from collections import defaultdict

import cairosvg
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from lxml import etree
from lxml.builder import E
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models import device, domain_name_tree, netdevice, \
    net_ip, peer_information, mon_ext_host, get_related_models, monitoring_hint, mon_check_command, \
    parse_commandline, mon_check_command_special, device_group
from initat.cluster.backbone.models.functions import duration
from initat.cluster.backbone.models.license import LicenseUsage, LicenseLockListDeviceService
from initat.cluster.backbone.models.status_history import mon_icinga_log_aggregated_host_data, \
    mon_icinga_log_aggregated_timespan, mon_icinga_log_aggregated_service_data, \
    mon_icinga_log_raw_base, mon_icinga_log_raw_service_alert_data, mon_icinga_log_raw_host_alert_data, AlertList
from initat.cluster.frontend.common import duration_utils
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.frontend.rest_views import rest_logging
from initat.md_config_server.icinga_log_reader.log_reader_utils import host_service_id_util
from initat.tools import logging_tools, process_tools, server_command

logger = logging.getLogger("cluster.monitoring")


class create_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(
            command="rebuild_host_config",
            cache_mode=request.POST.get("cache_mode", "DYNAMIC")
        )
        result = contact_server(request, "md-config", srv_com, connection_id="wf_mdrc")
        if result:
            request.xml_response["result"] = E.devices()


class call_icinga(View):
    @method_decorator(login_required)
    def post(self, request):
        pw = request.session.get("password")
        pw = base64.b64decode(pw) if pw else "no_passwd"
        _url = u"http{}://{}:{}@{}/icinga/".format(
            "s" if request.is_secure() else "",
            request.user.login,
            # fixme, if no password is set (due to automatic login) use no_passwd
            pw,
            request.get_host()
        )
        return HttpResponse(
            json.dumps({"url": _url}),
            content_type="application/json"
        )


class fetch_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        part_dev = device.objects.get(Q(pk=_post["pk"]))
        logger.info("reading partition info from %s" % (unicode(part_dev)))
        srv_com = server_command.srv_command(command="fetch_partition_info")
        _dev_node = srv_com.builder("device")
        _dev_node.attrib.update(
            {
                "pk": "{:d}".format(part_dev.pk),
            }
        )
        srv_com["devices"] = _dev_node
        _result = contact_server(request, "discovery", srv_com, timeout=30)


class clear_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        part_dev = device.objects.get(Q(pk=_post["pk"]))
        logger.info("clearing partition info from {}".format(unicode(part_dev)))
        _part = part_dev.act_partition_table
        if _part is None:
            request.xml_response.error(u"no partition table defined for {}".format(unicode(part_dev)))
        else:
            part_dev.act_partition_table = None
            part_dev.save(update_fields=["act_partition_table"])
            if not _part.user_created and not get_related_models(_part):
                request.xml_response.warn(u"partition table {} removed".format(_part))
                _part.delete()


class use_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        part_dev = device.objects.get(Q(pk=_post["pk"]))
        logger.info("using partition info from {} as act_partition".format(unicode(part_dev)))
        part_dev.act_partition_table = part_dev.partition_table
        part_dev.save(update_fields=["act_partition_table"])
        request.xml_response.info("set {} as act_partition_table".format(unicode(part_dev.partition_table)))


class get_node_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "pk_list" in _post:
            pk_list = json.loads(_post["pk_list"])
        else:
            pk_list = request.POST.getlist("pks[]")
        srv_com = server_command.srv_command(command="get_host_config")
        srv_com["device_list"] = E.device_list(
            *[
                E.device(
                    pk="{:d}".format(int(cur_pk)),
                    mode=request.POST["mode"]
                ) for cur_pk in pk_list
            ]
        )
        result = contact_server(request, "md-config", srv_com, timeout=30)
        if result:
            node_results = result.xpath(".//config", smart_strings=False)
            if len(node_results):
                request.xml_response["result"] = node_results[0]
            else:
                request.xml_response.error("no config", logger=logger)
        else:
            request.xml_response.error("no config", logger=logger)


class get_node_status(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        pk_list = json.loads(_post["pk_list"])
        srv_com = server_command.srv_command(command="get_node_status")
        # noinspection PyUnresolvedReferences
        srv_com["device_list"] = E.device_list(
            *[
                E.device(
                    pk="{:d}".format(int(cur_pk))
                ) for cur_pk in pk_list if cur_pk
            ]
        )
        result = contact_server(request, "md-config", srv_com, timeout=30)
        if result:
            host_results = result.xpath(".//ns:host_result/text()", smart_strings=False)
            service_results = result.xpath(".//ns:service_result/text()", smart_strings=False)
            if len(host_results) + len(service_results):

                # log and lock access
                any_locked = False
                host_results_filtered = []
                devices_used = set()
                for dev_res in json.loads(host_results[0]):
                    locked = False
                    for entry in dev_res['custom_variables'].split(","):
                        split = entry.split("|")
                        if len(split) == 2 and split[0].lower() == "device_pk":
                            try:
                                dev_pk = int(split[1])
                                locked = LicenseLockListDeviceService.objects.is_device_locked(
                                    LicenseEnum.monitoring_dashboard,
                                    dev_pk
                                )
                                if not locked:
                                    devices_used.add(dev_pk)
                            except ValueError:
                                logger.warn(
                                    "Invalid device pk in get_node_result access logging: {}".format(
                                        entry
                                    )
                                )

                    if not locked:
                        host_results_filtered.append(dev_res)

                    any_locked |= locked

                LicenseUsage.log_usage(LicenseEnum.monitoring_dashboard, LicenseParameterTypeEnum.device, devices_used)

                service_results_filtered = []
                services_used = collections.defaultdict(lambda: [])
                for serv_res in json.loads(service_results[0]):
                    host_pk, service_pk, _ = host_service_id_util.parse_host_service_description(
                        serv_res['description'],
                        log=logger.error
                    )
                    locked = False
                    if host_pk is not None and service_pk is not None:

                        locked = LicenseLockListDeviceService.objects.is_device_service_locked(
                            LicenseEnum.monitoring_dashboard, host_pk, service_pk
                        )

                        if not locked:
                            services_used[host_pk].append(service_pk)

                    if not locked:
                        service_results_filtered.append(serv_res)

                    any_locked |= locked

                LicenseUsage.log_usage(
                    LicenseEnum.monitoring_dashboard,
                    LicenseParameterTypeEnum.service,
                    services_used
                )

                if any_locked:
                    request.xml_response.info(
                        "Some entries are on the license lock list and therefore not displayed."
                    )

                # simply copy json dump
                request.xml_response["host_result"] = json.dumps(host_results_filtered)
                request.xml_response["service_result"] = json.dumps(service_results_filtered)

            else:
                request.xml_response.error("no service or node_results", logger=logger)


class get_mon_vars(View):
    def post(self, request):
        _post = request.POST
        _dev_pks = [int(_post["device_pk"])]
        _dev = device.objects.select_related("device_group").get(Q(pk=_dev_pks[0]))
        if not _dev.is_meta_device:
            # add meta device
            _dev_pks.append(_dev.device_group.device_group.filter(Q(is_meta_device=True))[0].pk)
        res_list = []
        mon_check_commands = mon_check_command.objects.filter(
            Q(config__device_config__device__in=_dev_pks)
        ).select_related(
            "config"
        )
        for _mc in mon_check_commands:
            _mon_info, _log_lines = parse_commandline(_mc.command_line)
            for _key, _value in _mon_info["default_values"].iteritems():
                if type(_value) == tuple:
                    res_list.append(
                        (
                            _mc.name,
                            _value[0],
                            _value[1],
                            "i" if _value[1].isdigit() else "s",
                            _mc.config.name,
                        )
                    )
        mon_special_check_commands = mon_check_command_special.objects.filter(
            Q(mon_check_command__config__device_config__device__in=_dev_pks)
        )
        for _mc in mon_special_check_commands:
            _mon_info, _log_lines = parse_commandline(_mc.command_line)
            for _key, _value in _mon_info["default_values"].iteritems():
                if type(_value) == tuple:
                    _checks = _mc.mon_check_command_set.all()
                    if len(_checks) == 1:
                        res_list.append(
                            (
                                _mc.name,
                                _value[0],
                                _value[1],
                                "i" if _value[1].isdigit() else "s",
                                _checks[0].config.name,
                            )
                        )
        return HttpResponse(
            json.dumps(
                # [
                #    {"idx": 0, "name": "please choose..."}
                # ] +
                [
                    {
                        "idx": _idx,
                        "info": "{} (default {}) from check_command {} (config {})".format(
                            _value[1],
                            _value[2],
                            _value[0],
                            _value[4],
                        ),
                        "type": _value[3],
                        "name": _value[1],
                        "value": _value[2],
                    } for _idx, _value in enumerate(res_list, 1)
                ]
            ),
            content_type="application/json"
        )


class resolve_name(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        fqdn = request.POST["fqdn"]
        if fqdn.strip():
            try:
                _ip = socket.gethostbyname(fqdn)
            except:
                pass
            else:
                logger.info(u"resolved {} to {}".format(fqdn, _ip))
                request.xml_response["ip"] = _ip


########################################
# device status history views
class _device_status_history_util(object):
    @staticmethod
    def get_timespan_tuple_from_request(request):
        date = duration_utils.parse_date(request.GET["date"])
        duration_type = {
            'day': duration.Day,
            'week': duration.Week,
            'month': duration.Month,
            'year': duration.Year,
            "decade": duration.Decade,
        }[request.GET['duration_type']]
        start = duration_type.get_time_frame_start(date)
        end = duration_type.get_end_time_for_start(start)
        return start, end, duration_type

    @staticmethod
    def get_timespan_db_from_request(request):
        start, end, duration_type = _device_status_history_util.get_timespan_tuple_from_request(request)

        try:
            return mon_icinga_log_aggregated_timespan.objects.get(
                duration_type=duration_type.ID,
                start_date__range=(start, end - datetime.timedelta(seconds=1))
            )
        except mon_icinga_log_aggregated_timespan.DoesNotExist:
            return None

    @staticmethod
    def get_line_graph_data(request, for_host):
        """
        Get line graph data for hosts and services
        :param request: Request with usual parameters
        :param for_host: boolean, whether to get data for services or hosts
        :return: dict of either {(dev_id, service_id): values} or {dev_id: values}
        """
        if for_host:
            trans = {
                k: v.capitalize() for (k, v) in mon_icinga_log_aggregated_host_data.STATE_CHOICES
            }
        else:
            trans = {
                k: v.capitalize() for (k, v) in mon_icinga_log_aggregated_service_data.STATE_CHOICES
            }

        device_ids = json.loads(request.GET["device_ids"])

        # calculate detailed view based on all events
        start, end, _ = _device_status_history_util.get_timespan_tuple_from_request(request)
        alert_filter = Q(device__in=device_ids)

        alert_list = AlertList(
            is_host=for_host,
            alert_filter=alert_filter,
            start_time=start,
            end_time=end,
            calc_first_after=True
        )

        return_data = {}

        for key, amended_list in alert_list.alerts.iteritems():
            # only use dev/serv keys which have entries in the time frame (i.e. those from entries)
            # they might be active before and after, but not during the time frame, in which case
            # they are not relevant to us

            # add first and last in case they are not contained in range already
            entry_before = alert_list.last_before.get(key, None)
            if entry_before is not None and amended_list[0].date != entry_before['date']:
                amended_list = [entry_before] + amended_list
            entry_after = alert_list.first_after.get(key, None)
            if entry_after is not None and amended_list[-1].date != entry_after['date']:
                amended_list = amended_list + [entry_after]

            l = []
            for entry in amended_list:
                if isinstance(entry, dict):
                    l.append(
                        {
                            'date': entry['date'],
                            'state': trans[entry['state']],
                            'msg': entry['msg']
                        }
                    )
                else:
                    l.append(
                        {
                            'date': entry.date,
                            'state': trans[entry.state],
                            'msg': entry.msg
                        }
                    )

            if not for_host:
                # use nice service id for services
                key = key[0], mon_icinga_log_raw_service_alert_data.objects.calculate_service_name_for_client_tuple(key[1], key[2])

            return_data[key] = l
        return return_data


class get_hist_timespan(RetrieveAPIView):
    @method_decorator(login_required)
    @rest_logging
    def retrieve(self, request, *args, **kwargs):
        timespan = _device_status_history_util.get_timespan_db_from_request(request)
        if timespan:
            data = {
                'status': 'found',
                'start': timespan.start_date, 'end': timespan.end_date
            }
        else:
            data = {
                'status': 'not found'
            }
            start, end, duration_type = _device_status_history_util.get_timespan_tuple_from_request(request)
            # return most recent data type if this type is not yet finished
            try:
                latest_timespan_db = \
                    mon_icinga_log_aggregated_timespan.objects.filter(duration_type=duration_type.ID).latest('start_date')
            except mon_icinga_log_aggregated_timespan.DoesNotExist:
                pass  # no data at all, can't do anything useful
            else:
                date = duration_utils.parse_date(request.GET["date"])
                if latest_timespan_db.end_date < date:
                    data = {'status': 'found earlier', 'start': latest_timespan_db.start_date, 'end': latest_timespan_db.end_date}

        return Response(data)


class get_hist_device_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        device_ids = json.loads(request.GET.get("device_ids"))

        timespan_db = _device_status_history_util.get_timespan_db_from_request(request)

        data = []
        if timespan_db:
            data = mon_icinga_log_aggregated_host_data.objects.filter(
                device_id__in=device_ids,
                timespan=timespan_db
            ).values('device_id', 'state', 'state_type', 'value')

        data_per_device = {device_id: [] for device_id in device_ids}
        for d in data:
            d['state'] = mon_icinga_log_aggregated_host_data.STATE_CHOICES_READABLE[d['state']].capitalize()
            data_per_device[d['device_id']].append(d)

        data_merged_state_types = {}
        for device_id, device_data in data_per_device.iteritems():
            if not LicenseLockListDeviceService.objects.is_device_locked(LicenseEnum.reporting, device_id):
                data_merged_state_types[device_id] = mon_icinga_log_aggregated_service_data.objects.merge_state_types(
                    device_data,
                    mon_icinga_log_aggregated_host_data.STATE_CHOICES_READABLE[mon_icinga_log_raw_base.STATE_UNDETERMINED]
                )

        LicenseUsage.log_usage(
            LicenseEnum.reporting,
            LicenseParameterTypeEnum.device,
            data_merged_state_types.iterkeys()
        )

        return Response([data_merged_state_types])  # fake a list, see coffeescript


class get_hist_service_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        device_ids = json.loads(request.GET.get("device_ids"))

        timespan_db = _device_status_history_util.get_timespan_db_from_request(request)

        merge_services = bool(int(request.GET.get("merge_services", 0)))
        return_data = mon_icinga_log_aggregated_service_data.objects.get_data(
            devices=device_ids,
            timespans=[timespan_db],
            license=LicenseEnum.reporting,
            merge_services=merge_services
        )

        return Response([return_data])  # fake a list, see coffeescript


class get_hist_device_line_graph_data(ListAPIView):
    """
    Returns device data for line graph
    """
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):

        return_data = _device_status_history_util.get_line_graph_data(request, for_host=True)
        return Response([return_data])  # fake a list, see coffeescript


class get_hist_service_line_graph_data(ListAPIView):
    """
    Returns service data for line graph
    """
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        prelim_return_data = _device_status_history_util.get_line_graph_data(request, for_host=False)

        return_data = defaultdict(lambda: {})

        for ((dev_id, service_identifier), values) in prelim_return_data.iteritems():
            return_data[dev_id][service_identifier] = values

        """
        def f():
            prelim_return_data = _device_status_history_util.get_line_graph_data(request, for_host=False)

            return_data = defaultdict(lambda: {})

            for ((dev_id, service_identifier), values) in prelim_return_data.iteritems():
                return_data[dev_id][service_identifier] = values

        import cProfile
        import time
        a = "/tmp/profl-{}".format(time.time())
        print 'prof to ', a
        cProfile.runctx("f()", globals(), locals(), a)

        from django.db import connection
        from pprint import pprint
        pprint(sorted(connection.queries, key=lambda a: a['time']), open("/tmp/prof1", "w"))

        return Response([return_data])  # fake a list, see coffeescript
        """
        return Response([return_data])  # fake a list, see coffeescript


class svg_to_png(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        parser = etree.XMLParser(remove_comments=True)
        _post = request.POST
        _bytes = _post["svg"]
        _out = StringIO.StringIO()
        # _xml = etree.fromstring(_post["svg"], parser)
        # for _el in _xml.iter():
        #    for _key, _value in _el.attrib.iteritems():
        #        if _key.startswith("ng-"):
        #            del _el.attrib[_key]
        try:
            cairosvg.svg2png(bytestring=_bytes.strip(), write_to=_out)
        except:
            request.xml_response.error("error converting svg to png")
        else:
            _png_content = _out.getvalue()
            _cache_key = "SVG2PNG_{}".format(uuid.uuid4().get_urn().split("-")[-1])
            cache.set(_cache_key, _png_content, 60)
            logger.info(
                "converting svg with {} to png with {} (cache_key is {})".format(
                    logging_tools.get_size_str(len(_post["svg"])),
                    logging_tools.get_size_str(len(_png_content)),
                    _cache_key,
                )
            )
            request.xml_response["cache_key"] = _cache_key


class fetch_png_from_cache(View):
    def get(self, request, cache_key=None):
        _val = cache.get(cache_key)
        if _val:
            return HttpResponse(_val, content_type="image/png")
        else:
            return HttpResponse("", content_type="image/png")
