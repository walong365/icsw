#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from initat.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     mon_check_command, mon_check_command_type, mon_service_templ, mon_period, mon_contact, user, \
     mon_contactgroup, get_related_models, network_type, network_device_type, mon_device_templ, \
     mon_ext_host, mon_host_cluster, mon_service_cluster, mon_device_esc_templ, mon_service_esc_templ, \
     partition_table
from django.db.models import Q
from initat.cluster.frontend.helper_functions import init_logging, contact_server
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
from django.http import HttpResponseRedirect
from lxml.builder import E
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import pprint
import server_command
import net_tools

@init_logging
@login_required
def create_command(request):
    _post = request.POST
    pprint.pprint(_post)
    keys = _post.keys()
    conf_pk = int(keys[0].split("__")[1])
    value_dict = dict([(key.split("__", 3)[3], value) for key, value in _post.iteritems() if key.count("__") > 2])
    copy_dict = dict([(key, value) for key, value in value_dict.iteritems() if key in ["name", "command_line", "description"]])
    request.log("create new monitoring_command %s for config %d" % (value_dict["name"], conf_pk))
    new_nc = mon_check_command(
        config=config.objects.get(Q(pk=conf_pk)),
        mon_check_command_type=mon_check_command_type.objects.get(Q(pk=value_dict["mon_check_command_type"])),
        mon_service_templ=mon_service_templ.objects.get(Q(pk=value_dict["mon_service_templ"])),
        **copy_dict)
    #pprint.pprint(copy_dict)
    try:
        new_nc.save()
    except ValidationError, what:
        request.log("error creating new monitoring_config: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["new_monitoring_command"] = new_nc.get_xml()
    return request.xml_response.create_response()
    
@init_logging
@login_required
def delete_command(request):
    _post = request.POST
    main_key = [key for key in _post.keys() if key.endswith("__name")][0]
    try:
        mon_check_command.objects.get(Q(pk=main_key.split("__")[3])).delete()
    except mon_check_command.DoesNotExist:
        request.log("mon_check_command does not exist", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@init_logging
@login_required
def setup(request):
    if request.method == "GET":
        return render_me(
            request, "monitoring_setup.html",
        )()
    else:
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        device_group_dict = {}
        for cur_user in user.objects.all().prefetch_related("allowed_device_groups"):
            device_group_dict[cur_user.login] = list([dg.pk for dg in cur_user.allowed_device_groups.all()])
        xml_resp.extend(
            [
                E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))]),
                E.users(*[cur_u.get_xml(allowed_device_group_dict=device_group_dict) for cur_u in user.objects.filter(Q(active=True))]),
                E.mon_periods(*[cur_p.get_xml() for cur_p in mon_period.objects.all()]),
                E.mon_contacts(*[cur_c.get_xml() for cur_c in mon_contact.objects.all()]),
                E.mon_service_templs(*[cur_st.get_xml() for cur_st in mon_service_templ.objects.all()]),
                E.mon_contactgroups(*[cur_cg.get_xml() for cur_cg in mon_contactgroup.objects.all()]),
                E.mon_device_templs(*[cur_dt.get_xml() for cur_dt in mon_device_templ.objects.all()]),
                E.devices(*[cur_dev.get_simple_xml() for cur_dev in device.objects.exclude(Q(device_type__identifier="MD")).order_by("name")]),
                E.mon_check_Command(*[cur_mc.get_xml() for cur_mc in mon_check_command.objects.all()]),
            ]
        )
        return request.xml_response.create_response()

@init_logging
@login_required
def extended_setup(request):
    if request.method == "GET":
        return render_me(
            request, "monitoring_extended_setup.html",
        )()
    else:
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
        return request.xml_response.create_response()

@init_logging
@login_required
def device_config(request):
    if request.method == "GET":
        return render_me(
            request, "monitoring_device.html",
        )()
    else:
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
        print unicode(request.xml_response)
        return request.xml_response.create_response()

@init_logging
@login_required
def create_config(request):
    srv_com = server_command.srv_command(command="rebuild_host_config", cache_mode="ALWAYS")
    #srv_com["devices"] = srv_com.builder(
    #    "devices",
    #    *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_list])
    result = contact_server(request, "tcp://localhost:8010", srv_com)
    #result = net_tools.zmq_connection("config_webfrontend", timeout=5).add_connection("tcp://localhost:8010", srv_com)
    if result:
        request.xml_response["result"] = E.devices()
    return request.xml_response.create_response()

@login_required
@init_logging
def rebuild_config(request):
    srv_com = server_command.srv_command(command="rebuild_config")
    result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)
    return request.xml_response.create_response()

@login_required
@init_logging
def call_icinga(request):
    return HttpResponseRedirect("http://%s/icinga" % (request.META["HTTP_HOST"]))

@login_required
@init_logging
def fetch_partition(request):
    _post = request.POST
    part_dev = device.objects.get(Q(pk=_post["pk"]))
    request.log("reading partition info from %s" % (unicode(part_dev)))
    srv_com = server_command.srv_command(command="fetch_partition_info")
    srv_com["server_key:device_pk"] = "%d" % (part_dev.pk)
    srv_com["server_key:device_pk"] = "%d" % (part_dev.pk)
    result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
    return request.xml_response.create_response()
