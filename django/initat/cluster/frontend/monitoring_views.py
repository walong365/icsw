#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from initat.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     mon_check_command, mon_check_command_type, mon_service_templ, mon_period, mon_contact, user, \
     mon_contactgroup, get_related_models, network_type, network_device_type, mon_device_templ, \
     mon_ext_host
from django.db.models import Q
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
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
        xml_resp.append(E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))]))
        xml_resp.append(E.users(*[cur_u.get_xml() for cur_u in user.objects.all()]))
        xml_resp.append(E.mon_periods(*[cur_p.get_xml() for cur_p in mon_period.objects.all()]))
        xml_resp.append(E.mon_contacts(*[cur_c.get_xml() for cur_c in mon_contact.objects.all()]))
        xml_resp.append(E.mon_service_templs(*[cur_st.get_xml() for cur_st in mon_service_templ.objects.all()]))
        xml_resp.append(E.mon_contactgroups(*[cur_cg.get_xml() for cur_cg in mon_contactgroup.objects.all()]))
        xml_resp.append(E.mon_device_templs(*[cur_dt.get_xml() for cur_dt in mon_device_templ.objects.all()]))
        return request.xml_response.create_response()

@init_logging
@login_required
def device_config(request):
    return render_me(
        request, "monitoring_device.html",
    )()

@init_logging
@login_required
def get_monitor_hosts(request):
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
    request.xml_response["response"] = E.response(srv_list)
    return request.xml_response.create_response()

@init_logging
@login_required
def create_config(request):
    srv_com = server_command.srv_command(command="rebuild_host_config")
    #srv_com["devices"] = srv_com.builder(
    #    "devices",
    #    *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_list])
    result = net_tools.zmq_connection("config_webfrontend", timeout=5).add_connection("tcp://localhost:8010", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        res_node = result.xpath(None, ".//ns:result")[0]
        request.log(res_node.attrib["reply"],
                    int(res_node.attrib["state"]),
                    xml=True)
        request.xml_response["result"] = E.devices()
    print etree.tostring(request.xml_response.build_response(), pretty_print=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def rebuild_config(request):
    srv_com = server_command.srv_command(command="rebuild_config")
    result = net_tools.zmq_connection("webfrontend", timeout=30).add_connection("tcp://localhost:8010", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        res_node = result.xpath(None, ".//ns:result")[0]
        request.log(res_node.attrib["reply"], int(res_node.attrib["state"]), xml=True)
    return request.xml_response.create_response()
