# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
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

""" package views """

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import package_search, package_search_result, \
    package, get_related_models, package_device_connection, device, kernel, image, \
    package_repo
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.backbone.serializers import package_device_connection_serializer
from initat.cluster.frontend.forms import package_search_form, package_action_form
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from rest_framework.renderers import JSONRenderer
from lxml.builder import E  # @UnresolvedImports @UnusedImport
import logging
import logging_tools
import process_tools
import json
import pprint
import server_command

logger = logging.getLogger("cluster.package")


class repo_overview(permission_required_mixin, View):
    all_required_permissions = ["backbone.package.package_install"]

    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "package_install.html", {
            })()

    @method_decorator(xml_wrapper)
    def post(self, request):
        cur_mode = request.POST.get("mode", None)
        _node_pks = request.POST.getlist("pks[]", [])
        if cur_mode in ["rescan_repos", "reload_searches", "sync_repos", "new_config", "clear_caches"]:
            srv_com = server_command.srv_command(command=cur_mode)
            if _node_pks:
                _bldr = srv_com.builder()
                srv_com["device_commands"] = [
                    _bldr.device_command(
                        name=cur_dev.full_name,
                        uuid=cur_dev.uuid
                    ) for cur_dev in device.objects.filter(Q(pk__in=_node_pks))
                ]
            _result = contact_server(request, "package", srv_com, timeout=10, log_result=True)
        else:
            request.xml_response.error("unknown mode '{}'".format(cur_mode))


def reload_searches(request):
    srv_com = server_command.srv_command(command="reload_searches")
    return contact_server(request, "package", srv_com, timeout=5, log_result=False)


class retry_search(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        retry_pk = _post["pk"]
        try:
            cur_search = package_search.objects.get(Q(pk=retry_pk))
        except package_search.DoesNotExist:
            request.xml_response.error("search does not exist", logger)
            cur_search = None
        if cur_search is not None:
            if cur_search.current_state == "done":
                with transaction.atomic():
                    cur_search.current_state = "wait"
                    cur_search.save(update_fields=["current_state"])
                reload_searches(request)
            else:
                request.xml_response.warn("search is in wrong state '%s'" % (cur_search.current_state), logger)


class use_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        exact = True if int(_post["exact"]) else False
        target_repo = int(_post["target_repo"])
        if target_repo and not exact:
            # we can only specify a target repo if exact is not used
            t_repo = package_repo.objects.get(Q(pk=target_repo))
        else:
            t_repo = None
        try:
            cur_sr = package_search_result.objects.get(Q(pk=_post["pk"]))
        except package_search_result.DoesNotExist:
            request.xml_response.error("package_result not found", logger)
        else:
            try:
                _new_p = cur_sr.create_package(exact=exact, target_repo=t_repo)
            except IntegrityError, what:
                request.xml_response.error("error modifying: {}".format(unicode(what)), logger)
            except ValidationError, what:
                request.xml_response.error("error creating: {}".format(unicode(what)), logger)
            except:
                request.xml_response.info("unknown error: {}".format(process_tools.get_except_info()), logger)
            else:
                request.xml_response.info("copied package_result", logger)


class unuse_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        try:
            cur_p = package.objects.get(Q(pk=_post["pk"]))  # @UndefinedVariable
        except package.DoesNotExist:  # @UndefinedVariable
            request.xml_response.error("package not found", logger)
        else:
            num_ref = get_related_models(cur_p)
            if num_ref:
                request.xml_response.error(
                    "cannot remove: {}".format(logging_tools.get_plural("reference", num_ref)),
                    logger
                )
            else:
                cur_p.delete()
                request.xml_response.info("removed package", logger)


class add_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        num_ok, num_error = (0, 0)
        new_pdcs = []
        for dev_pk, pack_pk in json.loads(_post["add_list"]):
            try:
                _cur_pdc = package_device_connection.objects.get(Q(device=dev_pk) & Q(package=pack_pk))
            except package_device_connection.DoesNotExist:
                new_pdc = package_device_connection(
                    device=device.objects.get(Q(pk=dev_pk)),
                    package=package.objects.get(Q(pk=pack_pk)))  # @UndefinedVariable
                new_pdc.save()
                new_pdcs.append(new_pdc)
                num_ok += 1
            else:
                num_error += 1
        if num_ok:
            request.xml_response.info("added {}".format(logging_tools.get_plural("connection", num_ok)), logger)
        if num_error:
            request.xml_response.warn("{} already existed".format(logging_tools.get_plural("connection", num_error)), logger)
        request.xml_response["result"] = JSONRenderer().render(package_device_connection_serializer(new_pdcs, many=True).data)


class remove_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        num_ok, num_error = (0, 0)
        for pdc_pk in json.loads(_post["remove_list"]):
            try:
                cur_pdc = package_device_connection.objects.get(Q(pk=pdc_pk))
            except package_device_connection.DoesNotExist:
                num_error += 1
            else:
                cur_pdc.delete()
                num_ok += 1
        if num_ok:
            request.xml_response.info("%s removed" % (logging_tools.get_plural("connection", num_ok)), logger)
        if num_error:
            request.xml_response.error("%s not there" % (logging_tools.get_plural("connection", num_error)), logger)


class change_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_dict = json.loads(_post["change_dict"])
        # import pprint
        # pprint.pprint(c_dict)
        edit_obj = c_dict["edit_obj"]
        changed = 0
        for cur_pdc in package_device_connection.objects.filter(Q(pk__in=c_dict["pdc_list"])).prefetch_related("kernel_list", "image_list"):
            change = False
            # flags
            for f_name in ["force_flag", "nodeps_flag"]:
                if f_name in edit_obj and edit_obj[f_name]:
                    # print "**", f_name, edit_obj[f_name], int(edit_obj[f_name])
                    t_flag = True if int(edit_obj[f_name]) else False
                    if t_flag != getattr(cur_pdc, f_name):
                        setattr(cur_pdc, f_name, t_flag)
                        change = True
            # target state
            if edit_obj["target_state"] and edit_obj["target_state"] != cur_pdc.target_state:
                change = True
                cur_pdc.target_state = edit_obj["target_state"]
            # dependencies
            for dep, dep_obj in [("image", image), ("kernel", kernel)]:
                f_name = "%s_dep" % (dep)
                if edit_obj[f_name]:
                    _set = True if int(edit_obj[f_name]) else False
                    if _set != getattr(cur_pdc, f_name):
                        setattr(cur_pdc, f_name, _set)
                        change = True
                if edit_obj["%s_change" % (dep)]:
                    l_name = "%s_list" % (dep)
                    new_list = dep_obj.objects.filter(Q(pk__in=edit_obj[l_name]))
                    setattr(cur_pdc, l_name, new_list)
                    change = True
            if change:
                changed += 1
                cur_pdc.save()
        request.xml_response.info("%s updated" % (logging_tools.get_plural("PDC", changed)), logger)
        srv_com = server_command.srv_command(command="new_config")
        result = contact_server(request, "package", srv_com, timeout=10, log_result=False)
        if result:
            # print result.pretty_print()
            request.xml_response.info("sent sync to server", logger)


class change_target_state(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_pdc = package_device_connection.objects.get(Q(pk=_post["pdc_key"].split("__")[1]))
        cur_pdc.target_state = _post["value"]
        cur_pdc.save()
        # signal package-server ?


class change_package_flag(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_pdc = package_device_connection.objects.select_related("package").get(Q(pk=_post["pdc_key"].split("__")[1]))
        flag_name = _post["pdc_key"].split("__")[-1]
        # print flag_name
        value = True if int(_post["value"]) else False
        sflag_name = flag_name[:-5] if flag_name.endswith("_flag") else flag_name
        request.xml_response.info(
            "setting %s flag to %s for %s" % (
                sflag_name,
                "True" if value else "False",
                unicode(cur_pdc.package),
                ), logger)
        setattr(cur_pdc, flag_name, value)
        cur_pdc.save()
        # signal package-server ?


class get_pdc_status(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_pdc = package_device_connection.objects.get(Q(pk=_post["pdc_pk"]))
        request.xml_response["pdc_status"] = cur_pdc.response_str


class synchronize(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="new_config")
        result = contact_server(request, "package", srv_com, timeout=10, log_result=False)
        if result:
            # print result.pretty_print()
            request.xml_response.info("sent sync to server", logger)
