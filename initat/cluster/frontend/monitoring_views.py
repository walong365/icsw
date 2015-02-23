# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
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

from django.contrib.auth.decorators import login_required
from django.db.models.query import Prefetch
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
import pytz
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone.models import device, device_type, domain_name_tree, netdevice, \
    net_ip, peer_information, mon_ext_host, get_related_models, monitoring_hint, mon_check_command, \
    parse_commandline, mon_check_command_special
from initat.cluster.frontend.common import duration_utils
from initat.cluster.frontend.rest_views import rest_logging
from initat.cluster.backbone.models.monitoring import mon_icinga_log_aggregated_host_data, \
    mon_icinga_log_aggregated_timespan, mon_icinga_log_aggregated_service_data, \
    mon_icinga_log_raw_base, mon_icinga_log_raw_service_alert_data, mon_icinga_log_raw_host_alert_data
from initat.cluster.backbone.models.functions import duration
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.forms import mon_period_form, mon_notification_form, mon_contact_form, \
    mon_service_templ_form, host_check_command_form, mon_contactgroup_form, mon_device_templ_form, \
    mon_host_cluster_form, mon_service_cluster_form, mon_host_dependency_templ_form, \
    mon_service_esc_templ_form, mon_device_esc_templ_form, mon_service_dependency_templ_form, \
    mon_host_dependency_form, mon_service_dependency_form, device_monitoring_form, \
    device_group
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from lxml.builder import E  # @UnresolvedImports
import base64
import itertools
import json
import logging
import process_tools
import server_command
import socket
from collections import defaultdict

logger = logging.getLogger("cluster.monitoring")


class setup(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_setup.html", {
                }
        )()


class setup_cluster(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_setup_cluster.html", {
                }
        )()


class build_info(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_build_info.html", {
                }
        )()


class setup_escalation(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_setup_escalation.html", {
                }
        )()


class device_config(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.change_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_device.html", {
                "device_object_level_permission": "backbone.device.change_monitoring",
            }
        )()


class create_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="rebuild_host_config", cache_mode=request.POST.get("cache_mode", "DYNAMIC"))
        result = contact_server(request, "md-config", srv_com, connection_id="wf_mdrc")
        if result:
            request.xml_response["result"] = E.devices()


class call_icinga(View):
    @method_decorator(login_required)
    def get(self, request):
        resp = HttpResponseRedirect(
            u"http://{}:{}@{}/icinga/".format(
                request.user.login,
                # fixme, if no password is set (due to automatic login) use no_passwd
                base64.b64decode(request.session.get("password", "no_passwd")),
                request.get_host()
            )
        )
        return resp


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
            *[E.device(pk="{:d}".format(int(cur_pk)), mode=request.POST["mode"]) for cur_pk in pk_list]
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
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="{:d}".format(int(cur_pk))) for cur_pk in pk_list if cur_pk]
        )
        result = contact_server(request, "md-config", srv_com, timeout=30)
        if result:
            host_results = result.xpath(".//ns:host_result/text()", smart_strings=False)
            service_results = result.xpath(".//ns:service_result/text()", smart_strings=False)
            if len(host_results) + len(service_results):
                # import pprint
                # pprint.pprint(json.loads(node_results[0]))
                # simply copy json dump
                request.xml_response["host_result"] = host_results[0]
                request.xml_response["service_result"] = service_results[0]
            else:
                request.xml_response.error("no service or node_results", logger=logger)


class livestatus(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_livestatus.html", {
                }
        )()


class overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_overview.html", {
                }
        )()


class delete_hint(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        monitoring_hint.objects.get(Q(pk=_post["hint_pk"])).delete()


class get_mon_vars(View):
    def post(self, request):
        _post = request.POST
        _dev_pks = [int(_post["device_pk"])]
        _dev = device.objects.select_related("device_type", "device_group").get(Q(pk=_dev_pks[0]))
        if _dev.device_type.identifier == "H":
            # add meta device
            _dev_pks.append(_dev.device_group.device_group.filter(Q(device_type__identifier="MD"))[0].pk)
        res_list = []
        mon_check_commands = mon_check_command.objects.filter(
            Q(config__device_config__device__in=_dev_pks)
        ).select_related("config")
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
        ).select_related("mon_check_command__config")
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
        return HttpResponse(json.dumps(
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
            ]), content_type="application/json")


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


class create_device(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_tree"]

    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "create_new_device.html", {
            }
        )()

    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        # domain name tree
        dnt = domain_name_tree()
        device_data = json.loads(_post["device_data"])
        try:
            cur_dg = device_group.objects.get(Q(name=device_data["device_group"]))
        except device_group.DoesNotExist:
            try:
                cur_dg = device_group.objects.create(
                    name=device_data["device_group"],
                    domain_tree_node=dnt.get_domain_tree_node(""),
                    description="auto created device group {}".format(device_data["device_group"]),
                    )
            except:
                request.xml_response.error(
                    u"cannot create new device group: {}".format(
                        process_tools.get_except_info()
                    ),
                    logger=logger
                )
                cur_dg = None
            else:
                request.xml_response.info(u"created new device group '{}'".format(unicode(cur_dg)), logger=logger)
        else:
            if cur_dg.cluster_device_group:
                request.xml_response.error(
                    u"no devices allowed in system (cluster) group",
                    logger=logger
                )
                cur_dg = None
        if cur_dg is not None:
            if device_data["full_name"].count("."):
                short_name, domain_name = device_data["full_name"].split(".", 1)
                dnt_node = dnt.add_domain(domain_name)
            else:
                short_name = device_data["full_name"]
                # top level node
                dnt_node = dnt.get_domain_tree_node("")
            try:
                cur_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node=dnt_node))
            except device.DoesNotExist:
                # check image
                if device_data["icon_name"].strip():
                    try:
                        cur_img = mon_ext_host.objects.get(Q(name=device_data["icon_name"]))
                    except mon_ext_host.DoesNotExist:
                        cur_img = None
                    else:
                        pass
                try:
                    cur_dev = device.objects.create(
                        device_group=cur_dg,
                        device_type=device_type.objects.get(Q(identifier="H")),
                        domain_tree_node=dnt_node,
                        name=short_name,
                        mon_resolve_name=device_data["resolve_via_ip"],
                        comment=device_data["comment"],
                        mon_ext_host=cur_img,
                    )
                except:
                    request.xml_response.error(
                        u"cannot create new device: {}".format(
                            process_tools.get_except_info()
                        ),
                        logger=logger
                    )
                    cur_dev = None
                else:
                    request.xml_response.info(u"created new device '{}'".format(unicode(cur_dev)), logger=logger)
            else:
                request.xml_response.warn(u"device {} already exists".format(unicode(cur_dev)), logger=logger)
            if cur_dev is not None:
                try:
                    cur_nd = netdevice.objects.get(Q(device=cur_dev) & Q(devname='eth0'))
                except netdevice.DoesNotExist:
                    cur_nd = netdevice.objects.create(
                        devname="eth0",
                        device=cur_dev,
                        routing=device_data["routing_capable"],
                        )
                    if device_data["peer"]:
                        peer_information.objects.create(
                            s_netdevice=cur_nd,
                            d_netdevice=netdevice.objects.get(Q(pk=device_data["peer"])),
                            penalty=1,
                        )
                try:
                    cur_ip = net_ip.objects.get(Q(netdevice=cur_nd) & Q(ip=device_data["ip"]))
                except net_ip.DoesNotExist:
                    cur_ip = net_ip(
                        netdevice=cur_nd,
                        ip=device_data["ip"],
                        domain_tree_node=dnt_node,
                    )
                    cur_ip.create_default_network = True
                    try:
                        cur_ip.save()
                    except:
                        request.xml_response.error(u"cannot create IP: {}".format(process_tools.get_except_info()), logger=logger)
                        cur_ip = None


########################################
# device status history views
class _device_status_history_util(object):
    @staticmethod
    def get_timespan_tuple_from_request(request):
        date = duration_utils.parse_date(request.GET["date"])
        duration_type = {'day': duration.Day,
                         'week': duration.Week,
                         'month': duration.Month,
                         'year': duration.Year}[request.GET['duration_type']]
        start = duration_type.get_time_frame_start(date)
        end = duration_type.get_end_time_for_start(start)
        return start, end, duration_type

    @staticmethod
    def get_timespan_db_from_request(request):
        start, end, duration_type = _device_status_history_util.get_timespan_tuple_from_request(request)

        try:
            return mon_icinga_log_aggregated_timespan.objects.get(duration_type=duration_type.ID,
                                                                  start_date__range=(start, end))
        except mon_icinga_log_aggregated_timespan.DoesNotExist:
            return None

    @staticmethod
    def merge_state_types(data, undetermined_state):
        # data is list of dicts {'state': state, 'value': value, 'state_type': state_type}
        data_merged_state_types = []
        # merge state_types (soft/hard)
        for state in set(d['state'] for d in data):
            data_merged_state_types.append({'state': state, 'value': sum(d['value'] for d in data if d['state'] == state)})

        if not data_merged_state_types:
            data_merged_state_types.append({'state': undetermined_state, 'value': 1})
        return data_merged_state_types

    @staticmethod
    def get_line_graph_data(request, for_host):
        """
        Get line graph data for hosts and services
        :param request: Request with usual parameters
        :param for_host: boolean, whether to get data for services or hosts
        :return: dict of either {(dev_id, service_id): values} or {dev_id: values}
        """
        if for_host:
            obj_man = mon_icinga_log_raw_host_alert_data.objects
            trans = dict((k, v.capitalize()) for (k, v) in mon_icinga_log_aggregated_host_data.STATE_CHOICES)
        else:
            obj_man = mon_icinga_log_raw_service_alert_data.objects
            trans = dict((k, v.capitalize()) for (k, v) in mon_icinga_log_aggregated_service_data.STATE_CHOICES)

        device_ids = [int(i) for i in request.GET["device_ids"].split(",")]

        use_client_service_name = not for_host

        # calculate detailed view based on all events
        start, end, _ = _device_status_history_util.get_timespan_tuple_from_request(request)
        entries = obj_man.calc_alerts(start, end, device_ids=device_ids,
                                      use_client_service_name=use_client_service_name)

        last_before_entries = obj_man.calc_limit_alerts(start,
                                                        mode='last before',
                                                        device_ids=device_ids,
                                                        use_client_service_name=use_client_service_name)

        first_after_entries = obj_man.calc_limit_alerts(end,
                                                        mode='first after',
                                                        device_ids=device_ids,
                                                        use_client_service_name=use_client_service_name)

        return_data = {}

        for key, amended_list in entries.iteritems():
            # only use dev/serv keys which have entries in the time frame (i.e. those from entries)
            # they might be active before and after, but not during the time frame, in which case
            # they are not relevant to us

            entry_before = last_before_entries.get(key, None)
            if entry_before is not None:
                amended_list = [entry_before] + amended_list
            entry_after = first_after_entries.get(key, None)
            if entry_after is not None:
                amended_list = amended_list + [entry_after]

            l = []
            for entry in amended_list:
                if isinstance(entry, dict):
                    l.append({'date': entry['date'], 'state': trans[entry['state']], 'msg': entry['msg']})
                else:
                    l.append({'date': entry.date, 'state': trans[entry.state], 'msg': entry.msg})
            return_data[key] = l
        return return_data


class get_hist_timespan(RetrieveAPIView):
    @method_decorator(login_required)
    @rest_logging
    def retrieve(self, request, *args, **kwargs):
        timespan = _device_status_history_util.get_timespan_db_from_request(request)
        if timespan:
            data = {'status': 'found', 'start': timespan.start_date, 'end': timespan.end_date}
        else:
            data = {'status': 'not found'}
            start, end, duration_type = _device_status_history_util.get_timespan_tuple_from_request(request)
            # return most recent data type if this type is not yet finished
            try:
                latest_timespan_db = \
                    mon_icinga_log_aggregated_timespan.objects.filter(duration_type=duration_type.ID).latest('start_date')
            except mon_icinga_log_aggregated_timespan.DoesNotExist:
                pass  # no data at all, can't do anything useful
            else:
                date = duration_utils.parse_date(request.GET["date"])
                date = date.replace(tzinfo=pytz.UTC)
                if latest_timespan_db.end_date < date:
                    data = {'status': 'found earlier', 'start': latest_timespan_db.start_date, 'end': latest_timespan_db.end_date}

        return Response(data)


class get_hist_device_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        device_ids = [int(i) for i in request.GET["device_ids"].split(",")]

        timespan_db = _device_status_history_util.get_timespan_db_from_request(request)

        data = []
        if timespan_db:
            data = mon_icinga_log_aggregated_host_data.objects.filter(device_id__in=device_ids, timespan=timespan_db).values('device_id', 'state', 'state_type', 'value')

        trans = dict((k, v.capitalize()) for (k, v) in mon_icinga_log_aggregated_host_data.STATE_CHOICES)
        data_per_device = {device_id: [] for device_id in device_ids}
        for d in data:
            d['state'] = trans[d['state']].capitalize()
            data_per_device[d['device_id']].append(d)

        data_merged_state_types = {}
        for device_id, device_data in data_per_device.iteritems():
            data_merged_state_types[device_id] = _device_status_history_util.merge_state_types(device_data, trans[mon_icinga_log_raw_base.STATE_UNDETERMINED])

        return Response([data_merged_state_types])  # fake a list, see coffeescript


class get_hist_service_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        device_ids = [int(i) for i in request.GET["device_ids"].split(",")]

        timespan_db = _device_status_history_util.get_timespan_db_from_request(request)

        trans = dict((k, v.capitalize()) for (k, v) in mon_icinga_log_aggregated_service_data.STATE_CHOICES)

        def get_data_per_device(device_ids, timespans_db):

            queryset = mon_icinga_log_aggregated_service_data.objects.filter(device_id__in=device_ids, timespan__in=timespans_db)
            # can't do regular prefetch_related for queryset, this seems to work

            data_per_device = {device_id: defaultdict(lambda: []) for device_id in device_ids}
            for entry in queryset.prefetch_related(Prefetch("service")):

                relevant_data_from_entry = {
                    'state': trans[entry.state],
                    'state_type': entry.state_type,
                    'value': entry.value
                }

                client_service_name = mon_icinga_log_raw_service_alert_data.objects.calculate_service_name_for_client(entry)

                data_per_device[entry.device_id][client_service_name].append(relevant_data_from_entry)

            return data_per_device

        def merge_services(data_per_device):
            return_data = {}
            for device_id, device_data in data_per_device.iteritems():
                # it's not obvious how to aggregate service states
                # we now just add the values, but we could e.g. also use the most common state of a service as it's state
                # then we could say "4 services were ok, 3 were critical".
                data_concat = list(itertools.chain.from_iterable(service_data for service_data in device_data.itervalues()))
                device_data = _device_status_history_util.merge_state_types(data_concat, trans[mon_icinga_log_raw_base.STATE_UNDETERMINED])

                # normalize to 1.0, else the values are meaningless
                total = sum(entry['value'] for entry in device_data)
                for entry in device_data:
                    entry['value'] /= total
                return_data[device_id] = device_data
            return return_data

        def merge_state_types_per_device(data_per_device):
            return_data = {}
            # merge state types for each service in each device
            for device_id, device_service_data in data_per_device.iteritems():
                return_data[device_id] = {service_key: _device_status_history_util.merge_state_types(service_data, trans[mon_icinga_log_raw_base.STATE_UNDETERMINED]) for
                                          service_key, service_data in device_service_data.iteritems()}
            return return_data

        data_per_device = get_data_per_device(device_ids, [timespan_db])

        # this mode is for an overview of the services of a device without saying anything about a particular service
        if int(request.GET.get("merge_services", 0)):
            return_data = merge_services(data_per_device)

        else:
            return_data = merge_state_types_per_device(data_per_device)

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

        return Response([return_data])  # fake a list, see coffeescript
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
