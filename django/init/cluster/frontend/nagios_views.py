#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from init.cluster.frontend.forms import config_type_form
from init.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     ng_check_command, ng_check_command_type, ng_service_templ
from django.db.models import Q
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.forms.models import modelformset_factory
from lxml import etree
from lxml.builder import E
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import pprint

@init_logging
@login_required
def create_command(request):
    _post = request.POST
    pprint.pprint(_post)
    keys = _post.keys()
    conf_pk = int(keys[0].split("__")[1])
    value_dict = dict([(key.split("__", 3)[3], value) for key, value in _post.iteritems() if key.count("__") > 2])
    copy_dict = dict([(key, value) for key, value in value_dict.iteritems() if key in ["name", "command_line", "description"]])
    request.log("create new nagios_command %s for config %d" % (value_dict["name"], conf_pk))
    new_nc = ng_check_command(
        config=config.objects.get(Q(pk=conf_pk)),
        ng_check_command_type=ng_check_command_type.objects.get(Q(pk=value_dict["ng_check_command_type"])),
        ng_service_templ=ng_service_templ.objects.get(Q(pk=value_dict["ng_service_templ"])),
        **copy_dict)
    pprint.pprint(copy_dict)
    try:
        new_nc.save()
    except ValidationError, what:
        request.log("error creating new nagios_config: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["new_nagios_command"] = new_nc.get_xml()
    return request.xml_response.create_response()
    
@init_logging
@login_required
def delete_command(request):
    _post = request.POST
    main_key = [key for key in _post.keys() if key.endswith("__name")][0]
    try:
        ng_check_command.objects.get(Q(pk=main_key.split("__")[3])).delete()
    except ng_check_command.DoesNotExist:
        request.log("ng_check_command does not exist", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()
