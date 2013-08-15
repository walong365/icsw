#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import base64
import server_command
import logging
from lxml.builder import E # @UnresolvedImports

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic import View

from initat.cluster.frontend import forms
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.core.render import render_me, render_string
from initat.cluster.backbone.models import config, device_group, device, \
     mon_check_command, mon_service_templ, mon_period, mon_contact, user, \
     mon_contactgroup, mon_device_templ, \
     mon_host_cluster, mon_service_cluster, mon_device_esc_templ, mon_service_esc_templ, \
     partition_table, mon_notification, host_check_command

logger = logging.getLogger("cluster.monitoring")

class create_command(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        keys = _post.keys()
        conf_pk = int(keys[0].split("__")[1])
        value_dict = dict([(key.split("__", 4)[4], value) for key, value in _post.iteritems() if key.count("__") > 3])
        copy_dict = dict([(key, value) for key, value in value_dict.iteritems() if key in ["name", "command_line", "description"]])
        logger.info("create new monitoring_command %s for config %d" % (value_dict["name"], conf_pk))
        new_nc = mon_check_command(
            config=config.objects.get(Q(pk=conf_pk)),
            mon_service_templ=mon_service_templ.objects.all()[0],
            **copy_dict)
        # pprint.pprint(copy_dict)
        try:
            new_nc.save()
        except ValidationError, what:
            request.xml_response.error("error creating new monitoring_config: %s" % (unicode(what.messages[0])), logger)
        else:
            request.xml_response["new_monitoring_command"] = new_nc.get_xml()

class delete_command(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        main_key = [key for key in _post.keys() if key.endswith("__name")][0]
        try:
            mon_check_command.objects.get(Q(pk=main_key.split("__")[3])).delete()
        except mon_check_command.DoesNotExist:
            request.xml_response.error("mon_check_command does not exist", logger)

class setup(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_setup.html",
        )()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        device_group_dict = {}
        for cur_user in user.objects.all().prefetch_related("allowed_device_groups"):
            device_group_dict[cur_user.login] = list([dg.pk for dg in cur_user.allowed_device_groups.all()])
        xml_resp.extend(
            [
                E.host_check_commands(*[cur_cc.get_xml() for cur_cc in host_check_command.objects.all()]),
                E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))]),
                E.users(*[cur_u.get_xml(allowed_device_group_dict=device_group_dict) for cur_u in user.objects.filter(Q(active=True))]),
                E.mon_periods(*[cur_p.get_xml() for cur_p in mon_period.objects.all()]),
                E.mon_contacts(*[cur_c.get_xml() for cur_c in mon_contact.objects.all()]),
                E.mon_service_templs(*[cur_st.get_xml() for cur_st in mon_service_templ.objects.all()]),
                E.mon_contactgroups(*[cur_cg.get_xml() for cur_cg in mon_contactgroup.objects.all()]),
                E.mon_device_templs(*[cur_dt.get_xml() for cur_dt in mon_device_templ.objects.all()]),
                E.devices(*[cur_dev.get_simple_xml() for cur_dev in device.objects.exclude(Q(device_type__identifier="MD")).order_by("name")]),
                E.mon_check_command(*[cur_mc.get_xml() for cur_mc in mon_check_command.objects.prefetch_related("categories").all()]),
                E.mon_notifications(*[cur_mn.get_xml() for cur_mn in mon_notification.objects.all()]),
            ]
        )

class extended_setup(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_extended_setup.html",
        )()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        xml_resp.extend(
            [
                E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))]),
                E.users(*[cur_u.get_xml() for cur_u in user.objects.filter(Q(active=True))]),
                E.mon_periods(*[cur_p.get_xml() for cur_p in mon_period.objects.all()]),
                E.mon_contacts(*[cur_c.get_xml() for cur_c in mon_contact.objects.all()]),
                E.mon_service_templs(*[cur_st.get_xml() for cur_st in mon_service_templ.objects.all()]),
                E.mon_service_esc_templs(*[cur_set.get_xml() for cur_set in mon_service_esc_templ.objects.all()]),
                E.mon_contactgroups(*[cur_cg.get_xml() for cur_cg in mon_contactgroup.objects.all()]),
                E.mon_device_templs(*[cur_dt.get_xml() for cur_dt in mon_device_templ.objects.all()]),
                E.mon_device_esc_templs(*[cur_det.get_xml() for cur_det in mon_device_esc_templ.objects.all()]),
                E.mon_host_clusters(*[cur_mhc.get_xml() for cur_mhc in mon_host_cluster.objects.all()]),
                E.mon_service_clusters(*[cur_msc.get_xml() for cur_msc in mon_service_cluster.objects.all()]),
                E.devices(*[cur_dev.get_simple_xml() for cur_dev in device.objects.exclude(Q(device_type__identifier="MD")).order_by("name")]),
                E.mon_check_Command(*[cur_mc.get_xml() for cur_mc in mon_check_command.objects.all()]),
            ]
        )

class device_config(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_device.html",
        )()
    @method_decorator(xml_wrapper)
    def post(self, request):
        mon_hosts = device.objects.filter(Q(device_config__config__name__in=["monitor_server", "monitor_slave"])).prefetch_related("device_config_set__config")
        srv_list = E.devices()
        for cur_dev in mon_hosts:
            dev_xml = cur_dev.get_xml(full=False)
            if "monitor_server" in [dc.config.name for dc in cur_dev.device_config_set.all()]:
                dev_xml.attrib["monitor_type"] = "server"
            else:
                dev_xml.attrib["monitor_type"] = "slave"
            dev_xml.text = "%s [%s]" % (dev_xml.attrib["name"], dev_xml.attrib["monitor_type"])
            srv_list.append(dev_xml)
        part_list = E.partition_tables(*[cur_pt.get_xml() for cur_pt in partition_table.objects.all()])
        request.xml_response["response"] = E.response(srv_list, part_list)

class create_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="rebuild_host_config", cache_mode="ALWAYS")
        # srv_com["devices"] = srv_com.builder(
        #    "devices",
        #    *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_list])
        result = contact_server(request, "tcp://localhost:8010", srv_com)
        # result = net_tools.zmq_connection("config_webfrontend", timeout=5).add_connection("tcp://localhost:8010", srv_com)
        if result:
            request.xml_response["result"] = E.devices()

class rebuild_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="rebuild_config")
        _result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)

class call_icinga(View):
    @method_decorator(login_required)
    def get(self, request):
        resp = HttpResponseRedirect(
            "http://%s:%s@%s/icinga/" % (
                request.user.login,
                base64.b64decode(request.session["password"]),
                request.META["HTTP_HOST"]
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
        srv_com["server_key:device_pk"] = "%d" % (part_dev.pk)
        srv_com["server_key:device_pk"] = "%d" % (part_dev.pk)
        _result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)

class moncc_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        dev_key = request.POST["key"].split("__")[1]
        cur_moncc = mon_check_command.objects.get(Q(pk=dev_key))
        request.xml_response["response"] = cur_moncc.get_xml()
        request.xml_response["response"] = E.forms(
            E.template_form(
                render_string(
                    request,
                    "crispy_form.html",
                    {
                        "form" : forms.moncc_template_flags_form(
                            auto_id="moncc__%d__%%s" % (cur_moncc.pk),
                            instance=cur_moncc,
                        )
                    }
                )
            )
        )

class get_node_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="get_host_config")
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(cur_pk))) for cur_pk in request.POST.getlist("pks[]")]
        )
        result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)
        if result:
            node_results = result.xpath(None, ".//config")
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
        srv_com = server_command.srv_command(command="get_node_status")
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(cur_pk))) for cur_pk in request.POST.getlist("pks[]")]
        )
        result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)
        if result:
            node_results = result.xpath(None, ".//node_results")
            if len(node_results):
                node_results = node_results[0]
                if len(node_results):
                    # first device
                    request.xml_response["result"] = E.node_results(
                        *[E.node_result(
                            *[E.result(cur_res.attrib.pop("plugin_output"), **cur_res.attrib) for cur_res in node_result],
                            **node_result.attrib
                        ) for node_result in node_results]
                    )
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)

