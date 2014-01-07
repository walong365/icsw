#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013,2014 Andreas Lang-Nevyjel
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

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device_type, device_group, device, \
     cd_connection, domain_name_tree, category_tree, package_device_connection, \
     mon_ext_host, mon_device_templ, mon_service_cluster, mon_host_cluster, network, \
     domain_tree_node
from initat.cluster.frontend import forms
from initat.cluster.frontend.forms import device_tree_form, device_group_tree_form, \
    device_tree_many_form, device_variable_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.core.render import render_me, render_string
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImports
import config_tools
import json
import logging
import logging_tools
import re

logger = logging.getLogger("cluster.device")

class device_tree(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "device_tree.html",
            {
                "device_tree_form"       : device_tree_form(),
                "device_group_tree_form" : device_group_tree_form(),
                "device_tree_many_form"  : device_tree_many_form(),
                "hide_sidebar"           : True,
            }
            )()

class get_xml_tree(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        full_tree = device_group.objects.all().prefetch_related(
            "device",
            "device_group__categories",
            "device_group",
            "device_group__device_type").distinct().order_by("-cluster_device_group", "name")
        xml_resp = E.response()
        for cur_dg in full_tree:
            xml_resp.append(cur_dg.get_xml(with_devices=True, full=False, ignore_enabled=True))
        # add device type
        xml_resp.append(
            E.device_types(
                *[cur_dt.get_xml() for cur_dt in device_type.objects.all()]
            )
        )
        # add mother server(s)
        all_mothers = config_tools.device_with_config("mother_server").get("mother_server", [])
        xml_resp.extend([
            E.mother_servers(
                *[E.mother_server(unicode(mother_server.effective_device), pk="%d" % (mother_server.effective_device.pk)) for mother_server in all_mothers]),
            domain_name_tree().get_xml(),
        ])
        request.xml_response["response"] = xml_resp

class change_devices(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_dict = json.loads(_post.get("change_dict", ""))
        pk_list = json.loads(_post.get("device_list"))
        if c_dict.get("delete", False):
            device.objects.filter(Q(pk__in=pk_list)).delete()
            request.xml_response.info("delete {}".format(logging_tools.get_plural("device", len(pk_list))))
        else:
            def_dict = {
                "curl" : "",
                "bootserver" : None,
                "monitor_server" : None,
                }
            # build change_dict
            c_dict = {key[7:] : c_dict.get(key[7:], def_dict.get(key[7:], None)) for key in c_dict.iterkeys() if key.startswith("change_") and c_dict[key]}
            # resolve foreign keys
            c_dict = {key : {
                "device_type" : device_type,
                "device_group" : device_group,
                "domain_tree_node" : domain_tree_node,
                "bootserver" : device,
                "monitor_server" : device,
                }[key].objects.get(Q(pk=value)) if type(value) == int else value for key, value in c_dict.iteritems()}
            logger.info("change_dict has {}".format(logging_tools.get_plural("key", len(c_dict))))
            for key in sorted(c_dict):
                logger.info(" %s: %s" % (key, unicode(c_dict[key])))
            dev_changes = 0
            for cur_dev in device.objects.filter(Q(pk__in=pk_list)):
                changed = False
                for c_key, c_value in c_dict.iteritems():
                    if getattr(cur_dev, c_key) != c_value:
                        setattr(cur_dev, c_key, c_value)
                        changed = True
                if changed:
                    cur_dev.save()
                    dev_changes += 1
            request.xml_response["changed"] = dev_changes
            request.xml_response.info("changed settings of {}".format(logging_tools.get_plural("device", dev_changes)))

class clear_selection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        request.session["sel_list"] = []
        request.session.save()

class set_selection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "angular_sel" in _post:
            dev_list = json.loads(_post["angular_sel"])
            devg_list = device_group.objects.filter(Q(device__in=dev_list)).values_list("pk", flat=True)
            cur_list = ["dev__%d" % (cur_pk) for cur_pk in dev_list] + ["devg__%d" % (cur_pk) for cur_pk in devg_list]
        else:
            cur_list = [key for key in _post.getlist("key_list[]", []) if key.startswith("dev")]
        request.session["sel_list"] = cur_list
        request.session.save()

class get_selection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        request.xml_response["sel_list"] = E.selection(
            *[E.sel(cur_key) for cur_key in request.session.get("sel_list", [])]
        )

class add_selection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        dbl = True if int(_post["double"]) else False
        if "key" in _post:
            # single set / delete
            add_flag, add_sel_list, cur_list = (
                int(_post["add"]),
                [_post["key"]],
                request.session.get("sel_list", []))
        else:
            # total set / delete
            add_flag, add_sel_list, cur_list = (
                1,
                _post.getlist("key[]"),
                []
            )
        for add_sel in add_sel_list:
            if add_flag and add_sel not in cur_list:
                cur_list.append(add_sel)
            elif not add_flag and add_sel in cur_list:
                cur_list.remove(add_sel)
            if add_sel.startswith("devg__"):
                if dbl:
                    # toggle meta device
                    logger.info("toggle selection of META-device of device_group %d" % (int(add_sel.split("__")[1])))
                    toggle_devs = ["dev__%d" % (cur_pk) for cur_pk in device.objects.filter(
                        Q(enabled=True) &
                        Q(device_group__enabled=True) &
                        Q(device_group=add_sel.split("__")[1]) &
                        Q(device_type__identifier="MD")).values_list("pk", flat=True)]
                else:
                    # emulate toggle of device_group
                    logger.info("toggle selection of device_group %d" % (int(add_sel.split("__")[1])))
                    toggle_devs = ["dev__%d" % (cur_pk) for cur_pk in device.objects.filter(
                        Q(enabled=True) &
                        Q(device_group__enabled=True) &
                        Q(device_group=add_sel.split("__")[1])).values_list("pk", flat=True)]
                for toggle_dev in toggle_devs:
                    if toggle_dev in cur_list:
                        cur_list.remove(toggle_dev)
                    else:
                        cur_list.append(toggle_dev)
        # import pprint
        # pprint.pprint(cur_list)
        request.session["sel_list"] = cur_list
        request.session.save()
        logger.info("%s in list" % (logging_tools.get_plural("selection", len(cur_list))))
        return request.xml_response.create_response()

class show_configs(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "device_configs.html",
        )()

def _get_group_tree(request, sel_list, **kwargs):
    ignore_md = kwargs.get("ignore_meta_devices", False)
    ignore_cdg = kwargs.get("ignore_cdg", True)
    with_variables = kwargs.get("with_variables", False)
    with_monitoring = kwargs.get("with_monitoring", False)
    # show only nodes where the user has permissions for
    permission_tree = kwargs.get("permission_tree", False)
    # use FQDNs
    full_name = kwargs.get("full_name", False)
    devg_resp = E.device_groups()
    # sel_pks = [int(value.split("__")[1]) for value in sel_list]
    all_dgs = device_group.objects
    if permission_tree:
        # rights
        all_devs = request.user.has_perm("backbone.all_devices")
        if not all_devs:
            # ignore meta-device
            ignore_cdg = True
            all_dgs = all_dgs.filter(Q(pk__in=request.user.allowed_device_groups.all()))
    if ignore_cdg:
        all_dgs = all_dgs.exclude(Q(cluster_device_group=True))
    all_dgs = all_dgs.filter(Q(enabled=True)).prefetch_related(
        "device_group",
        "device_group__device_type",
        "device_group__netdevice_set",
        "device_group__bootnetdevice",
        "device_group__categories",
        # "device_group__mon_host_cluster_set"
    )
    if with_monitoring:
        all_dgs = all_dgs.prefetch_related(
            "device_group__devs_mon_host_cluster",
            "device_group__devs_mon_service_cluster")
    if with_variables:
        all_dgs = all_dgs.prefetch_related(
            "device_group__device_variable_set")
    if full_name:
        all_dgs = all_dgs.prefetch_related(
            "device_group__domain_tree_node"
        )
    device_type_dict = dict([(cur_dt.pk, cur_dt) for cur_dt in device_type.objects.all()])
    meta_dev_type_id = [key for key, value in device_type_dict.iteritems() if value.identifier == "MD"][0]
    # selected ........ device or device_group selected
    # tree_selected ... device is selected
    for cur_dg in all_dgs:
        cur_xml = cur_dg.get_xml(full=False, with_variables=with_variables, with_monitoring=with_monitoring, full_name=full_name)
        if cur_xml.attrib["key"] in sel_list:
            cur_xml.attrib["selected"] = "selected"
            cur_xml.attrib["tree_selected"] = "selected"
        any_sel = False
        for cur_dev in cur_xml.find("devices"):
            if ignore_md and int(cur_dev.attrib["device_type"]) == meta_dev_type_id:
                cur_dev.getparent().remove(cur_dev)
            else:
                cur_dev.attrib["title"] = "%s (%s%s)" % (
                    cur_dev.attrib["full_name" if full_name else "name"],
                    device_type_dict[int(cur_dev.attrib["device_type"])].identifier,
                    ", %s" % (cur_dev.attrib["comment"]) if cur_dev.attrib["comment"] else ""
                )
                if int(cur_dev.attrib["device_type"]) == meta_dev_type_id:
                    if cur_xml.attrib["key"] in sel_list:
                        cur_dev.attrib["tree_selected"] = "selected"
                    cur_dev.attrib["meta_device"] = "1"
                else:
                    cur_dev.attrib["meta_device"] = "0"
                if cur_dev.attrib["key"] in sel_list or cur_xml.attrib["key"] in sel_list:
                    # if permission_tree or (cur_dev.attrib["key"] in sel_list or cur_xml.attrib["key"] in sel_list):
                    cur_dev.attrib["selected"] = "selected"
                    any_sel = True
                if cur_dev.attrib["key"] in sel_list:
                    cur_dev.attrib["tree_selected"] = "selected"
                if permission_tree:
                    any_sel = True
        if any_sel:
            # add when any device is selected
            devg_resp.append(cur_xml)
        elif not ignore_cdg and int(cur_xml.attrib.get("is_cdg")):
            # or add the CDG when the CDG should not be ignored
            devg_resp.append(cur_xml)
    return E.repsonse(devg_resp)

def get_post_boolean(_post, name, default):
    if name in _post:
        p_val = _post[name]
        if p_val.lower() in ["1", "true"]:
            return True
        else:
            return False
    else:
        return default

class get_group_tree(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        ignore_md = get_post_boolean(_post, "ignore_meta_devices", False)
        ignore_cdg = get_post_boolean(_post, "ignore_cdg"         , True)
        with_variables = get_post_boolean(_post, "with_variables"     , False)
        permission_tree = get_post_boolean(_post, "permission_tree"    , False)
        with_monitoring = get_post_boolean(_post, "with_monitoring"    , False)
        full_name = get_post_boolean(_post, "full_name"          , False)
        if "sel_list[]" in _post:
            sel_list = _post.getlist("sel_list[]", [])
        else:
            sel_list = request.session.get("sel_list", [])
        xml_resp = _get_group_tree(request, sel_list, ignore_meta_devices=ignore_md,
                                   ignore_cdg=ignore_cdg, with_variables=with_variables,
                                   permission_tree=permission_tree, with_monitoring=with_monitoring,
                                   full_name=full_name)
        extra_re = re.compile("^extra_t(\d+)$")
        for extra_key in [key for key in _post.keys() if extra_re.match(key)]:
            extra_name = _post[extra_key]
            device_filter = True if "%s_device" % (extra_key) in _post else False
            kwargs = {"mon_ext_host" : {"with_images" : True}}.get(extra_name, {})
            select_rel_dict = {"cd_connection" : ["parent", "child"]}
            # request.log("adding extra data %s (device filter : %s)" % (extra_name,
            #                                                           str(device_filter)))
            extra_obj = globals()[extra_name]
            if device_filter:
                obj_list = extra_obj.objects.filter(Q(device__in=xml_resp.xpath(".//device/@pk")))
            else:
                obj_list = extra_obj.objects.all()
            extra_list = getattr(E, "%ss" % (extra_name))(
                *[cur_obj.get_xml(**kwargs) for cur_obj in obj_list.select_related(*select_rel_dict.get(extra_name, []))]
            )
            xml_resp.append(extra_list)
        request.xml_response["response"] = xml_resp

class connections(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "device_connections.html")()
    @method_decorator(xml_wrapper)
    def post(self, request):
        pass

class create_connection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        drag_dev, target_dev = (
            device.objects.get(Q(pk=_post["drag_id"].split("__")[1])),
            device.objects.get(Q(pk=_post["target"].split("__")[1])))
        t_type = _post["target_type"]
        request.xml_response.info("dragged '%s' over '%s' (field %s)" % (
            unicode(drag_dev),
            unicode(target_dev),
            t_type))
        new_cd = cd_connection(
            parent=target_dev if t_type == "master" else drag_dev,
            child=drag_dev if t_type == "master" else target_dev,
            created_by=request.user,
            connection_info="webfrontend")
        try:
            new_cd.save()
        except ValidationError, what:
            request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
        else:
            request.xml_response.info("added connection", logger=logger)
            request.xml_response["new_connection"] = new_cd.get_xml()

class delete_connection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        del_pk = _post["pk"]
        del_con = cd_connection.objects.get(Q(pk=del_pk))
        request.xml_response.info("removing %s" % (unicode(del_con)))
        del_con.delete()

class manual_connection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        re_dict = {
            "drag"   : _post["source"],
            "target" : _post["target"],
        }
        t_type = _post["mode"]
        logger.info("mode is '%s', drag_str is '%s', target_str is '%s'" % (
            t_type,
            re_dict["drag"],
            re_dict["target"]))
        # # (hash) is our magic sign for \d
        for key in re_dict.keys():
            val = re_dict[key]
            if val.count("#"):
                parts = val.split("#")
                val = "(%s)(%s)(%s)" % (parts[0], "#" * (len(parts) - 1), parts[-1])
                val = val.replace("#", "\d")
            re_dict[key] = re.compile("^%s$" % (val))
        # all cd / non-cd devices
        cd_devices = device.objects.filter(Q(device_type__identifier='CD'))
        non_cd_devices = device.objects.exclude(Q(device_type__identifier='CD'))
        # iterate over non-cd-device
        # pprint.pprint(re_dict)
        match_dict = {}
        for key, dev_list in [("drag", non_cd_devices),
                              ("target", cd_devices)]:
            match_dict[key] = {}
            for cur_dev in dev_list:
                cur_m = re_dict[key].match(cur_dev.name)
                if cur_m and cur_m.groups():
                    d_key = cur_m.groups()[1]
                    if d_key.isdigit():
                        d_key = int(d_key)
                    match_dict[key][d_key] = (cur_m.groups(), cur_dev)
        # matching keys
        m_keys = set(match_dict["drag"].keys()) & set(match_dict["target"].keys())
        logger.info(
            "%s: %s" % (logging_tools.get_plural("matching key", len(m_keys)),
                        ", ".join(sorted([str(key) for key in m_keys]))))
        created_cons = []
        for m_key in m_keys:
            new_cd = cd_connection(
                parent=match_dict["target" if t_type == "slave" else "drag"][m_key][1],
                child=match_dict["drag" if t_type == "slave" else "target"][m_key][1],
                created_by=request.user,
                connection_info="manual")
            try:
                new_cd.save()
            except ValidationError, what:
                request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
                for del_cd in created_cons:
                    del_cd.delete()
            else:
                created_cons.append(new_cd)
        if m_keys:
            if created_cons:
                request.xml_response.info("created %s" % (logging_tools.get_plural("connection", len(m_keys))), logger)
        else:
            request.xml_response.warn("found no matching devices", logger)

class variables(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "device_variables.html", {
            "device_variable_form" : device_variable_form(),
            })()
    @method_decorator(xml_wrapper)
    def post(self, request):
        pass

class device_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # request.xml_response.log(logging_tools.LOG_LEVEL_ERROR, "ok", logger)
        dev_key = request.POST["key"].split("__")[1]
        cur_dev = device.objects.prefetch_related("netdevice_set", "netdevice_set__net_ip_set").get(Q(pk=dev_key))
        request.xml_response["permissions"] = request.user.get_all_object_perms_xml(cur_dev)
        request.xml_response["response"] = cur_dev.get_xml(
            with_partition=True,
            with_variables=True,
            with_md_cache=True,
            full_name=True,
        )
        request.xml_response["response"] = domain_name_tree().get_xml()
        request.xml_response["response"] = E.network_list(
            *[cur_nw.get_xml() for cur_nw in network.objects.all().select_related("network_type").prefetch_related("network_device_type").order_by("name")]
        )
        request.xml_response["response"] = category_tree().get_xml()
        # print etree.tostring(request.xml_response["response"][1], pretty_print=True)
        request.xml_response["response"] = E.forms(
            E.general_form(
                render_string(
                    request,
                    "crispy_form.html",
                    {
                        "form" : forms.device_general_form(
                            auto_id="dev__%d__%%s" % (cur_dev.pk),
                            instance=cur_dev,
                        )
                    }
                )
            )
        )
