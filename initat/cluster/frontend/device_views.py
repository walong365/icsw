# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
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

""" device views """

import json
import logging
import re
import pprint

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from lxml.builder import E
from initat.cluster.backbone.models import device_group, device, \
    cd_connection, domain_tree_node, category
from initat.cluster.backbone.models.functions import can_delete_obj
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server
from initat.tools import logging_tools
from initat.tools import server_command
from initat.tools import process_tools


logger = logging.getLogger("cluster.device")


class device_tree_smart(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_tree"]

    def get(self, request):
        return render_me(
            request,
            "device_tree_smart.html",
            {
            }
        )()


class change_devices(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_dict = json.loads(_post.get("change_dict", ""))
        pk_list = json.loads(_post.get("device_list"))
        if c_dict.get("delete", False):
            num_deleted = 0
            error_msgs = []
            for pk in pk_list:
                obj = device.objects.get(Q(pk=pk))
                can_delete_answer = can_delete_obj(obj, logger)
                if can_delete_answer:
                    obj.delete()
                    num_deleted += 1
                else:
                    error_msgs.append((obj.name, can_delete_answer.msg))
            if num_deleted > 0:
                request.xml_response.info("delete {}".format(logging_tools.get_plural("device", num_deleted)))
            for pk, msg in error_msgs:
                request.xml_response.error("Failed to delete {}: {}".format(pk, msg))
        else:
            def_dict = {
                "bootserver": None,
                "monitor_server": None,
                "enabled": False,
                "store_rrd_data": False,
            }
            # build change_dict
            c_dict = {key[7:]: c_dict.get(key[7:], def_dict.get(key[7:], None)) for key in c_dict.iterkeys() if key.startswith("change_") and c_dict[key]}
            # resolve foreign keys
            c_dict = {key: {
                "device_group": device_group,
                "domain_tree_node": domain_tree_node,
                "bootserver": device,
                "monitor_server": device,
            }[key].objects.get(Q(pk=value)) if type(value) == int else value for key, value in c_dict.iteritems()}
            logger.info("change_dict has {}".format(logging_tools.get_plural("key", len(c_dict))))
            for key in sorted(c_dict):
                if key == "root_passwd":
                    logger.info(" %s: %s" % (key, "****"))
                else:
                    logger.info(" %s: %s" % (key, unicode(c_dict.get(key))))
            dev_changes = 0
            for cur_dev in device.objects.filter(Q(pk__in=pk_list)):
                changed = False
                for c_key, c_value in c_dict.iteritems():
                    if getattr(cur_dev, c_key) != c_value:
                        if c_key == "root_passwd":
                            c_value = cur_dev.crypt(c_value)
                            if c_value:
                                setattr(cur_dev, c_key, c_value)
                                changed = True
                        else:
                            setattr(cur_dev, c_key, c_value)
                            changed = True
                if changed:
                    cur_dev.save()
                    dev_changes += 1
            request.xml_response["changed"] = dev_changes
            request.xml_response.info("changed settings of {}".format(logging_tools.get_plural("device", dev_changes)))


class set_selection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        dev_list = json.loads(_post["angular_sel"])
        devg_list = device_group.objects.filter(Q(device__in=dev_list)).values_list("pk", flat=True)
        cur_list = ["dev__%d" % (cur_pk) for cur_pk in dev_list] + ["devg__%d" % (cur_pk) for cur_pk in devg_list]
        request.session["sel_list"] = cur_list
        request.session.save()


class show_configs(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "device_configs.html", {
                "device_object_level_permission": "backbone.device.change_config",
            }
        )()


class connections(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "device_connections.html")()

    @method_decorator(xml_wrapper)
    def post(self, request):
        pass


class manual_connection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        re_dict = {
            "source": _post["source"],
            "target": _post["target"],
        }
        t_type = _post["mode"]
        logger.info("mode is '%s', source_str is '%s', target_str is '%s'" % (
            t_type,
            re_dict["source"],
            re_dict["target"]))
        # # (hash) is our magic sign for \d
        for key in re_dict.keys():
            val = re_dict[key]
            if val.count("#"):
                parts = val.split("#")
                val = ("(%s)(%s)(%s)" % (parts[0], "#" * (len(parts) - 1), parts[-1])).replace("()", "").replace("#", "\d")
            re_dict[key] = re.compile("^%s$" % (val))
        # all cd / non-cd devices
        # FIXME
        cd_devices = device.all_real_enabled.filter(
            Q(com_capability_list__matchcode="ipmi") |
            Q(snmp_schemes__power_control=True)
        )
        # print cd_devices
        non_cd_devices = device.all_real_enabled()
        logger.info("cd / non-cd devices: {:d} / {:d}".format(cd_devices.count(), non_cd_devices.count()))
        # iterate over non-cd-device
        # pprint.pprint(re_dict)
        match_dict = {}
        for key, dev_list in [
            ("source", cd_devices),
            ("target", non_cd_devices)
        ]:
            match_dict[key] = {}
            for cur_dev in dev_list:
                cur_m = re_dict[key].match(cur_dev.name)
                if cur_m and cur_m.groups():
                    d_key = cur_m.groups()[1]
                    if d_key.isdigit():
                        d_key = int(d_key)
                    match_dict[key][d_key] = (cur_m.groups(), cur_dev)
        # matching keys
        m_keys = set(match_dict["source"].keys()) & set(match_dict["target"].keys())
        logger.info(
            "{}: {}".format(
                logging_tools.get_plural("matching key", len(m_keys)),
                ", ".join(sorted([str(key) for key in m_keys]))
            )
        )
        created_cons = []
        for m_key in m_keys:
            new_cd = cd_connection(
                parent=match_dict["target" if t_type == "slave" else "source"][m_key][1],
                child=match_dict["source" if t_type == "slave" else "target"][m_key][1],
                created_by=request.user,
                connection_info="manual"
            )
            try:
                new_cd.save()
            except ValidationError:
                request.xml_response.error("error creating: {}".format(process_tools.get_except_info()), logger)
                for del_cd in created_cons:
                    del_cd.delete()
            else:
                created_cons.append(new_cd)
        if m_keys:
            if created_cons:
                request.xml_response.info("created {}".format(logging_tools.get_plural("connection", len(m_keys))), logger)
        else:
            request.xml_response.warn("found no matching devices", logger)


class variables(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "device_variables.html", {
            "device_object_level_permission": "backbone.device.change_variables",
        })()


class scan_device_network(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _json_dev = json.loads(request.POST["dev"])
        _dev = device.objects.get(Q(pk=_json_dev["idx"]))
        _sm = _json_dev["scan_mode"]
        logger.info("scanning network settings of device {} via {}".format(unicode(_dev.full_name), _sm))
        if _sm == "hm":
            srv_com = server_command.srv_command(command="scan_network_info")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                    "scan_address": _json_dev["scan_address"],
                    "strict_mode": "1" if _json_dev["strict_mode"] else "0",
                }
            )
            srv_com["devices"] = _dev_node
        elif _sm == "snmp":
            srv_com = server_command.srv_command(command="snmp_basic_scan")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                    "scan_address": _json_dev["scan_address"],
                    "snmp_version": "{}".format(_json_dev["snmp_version"]),
                    "snmp_community": _json_dev["snmp_community"],
                    "strict": "1" if _json_dev["remove_not_found"] else "0"
                }
            )
            srv_com["devices"] = _dev_node
        elif _sm == "base":
            srv_com = server_command.srv_command(command="base_scan")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                }
            )
            if _json_dev["scan_address"] != "":
                _dev_node.attrib.update(
                    {
                        "scan_address": _json_dev["scan_address"],
                    }
                )
            srv_com["devices"] = _dev_node
        elif _sm == "wmi":
            srv_com = server_command.srv_command(command="wmi_scan")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                    "scan_address": _json_dev["scan_address"],
                    "username": _json_dev["wmi_username"],
                    "password": _json_dev["wmi_password"],
                    "discard_disabled_interfaces": "1" if _json_dev["wmi_discard_disabled_interfaces"] else "0",
                }
            )
            srv_com["devices"] = _dev_node
        else:
            srv_com = None
            request.xml_response.error("invalid scan type {}".format(_sm))
        if srv_com is not None:
            _result = contact_server(request, "discovery", srv_com, timeout=30)


class device_info(View):
    @method_decorator(login_required)
    def get(self, request, **kwargs):
        # set selection list
        request.session["sel_list"] = ["dev__{}".format(kwargs["device_pk"])]
        request.session.save()
        return render_me(request, "index.html", {"index_view": True, "doc_page": "index", "DEVICE_MODE": kwargs.get("mode", "")})()


class get_device_location(View):
    @method_decorator(login_required)
    def get(self, request):
        if "devices" in request.GET:
            _dev_pks = json.loads(request.GET["devices"])
            _mapping_list = list(category.objects.filter(Q(device__in=_dev_pks) & Q(full_name__startswith="/location/")).values_list("device__pk", "pk"))
        else:
            _mapping_list = list(category.objects.filter(Q(full_name__startswith="/location/")).values_list("device__pk", "pk"))
        return HttpResponse(json.dumps(_mapping_list), content_type="application/json")
