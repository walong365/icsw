# package views

import datetime
import os
import logging
import logging_tools
import process_tools
import pprint
import re
import server_command
import time
from lxml import etree
from lxml.builder import E

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.http import HttpResponse
from django.views.generic import View
from django.utils.decorators import method_decorator

from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.backbone.models import package_repo, package_search, user, \
     package_search_result, package, get_related_models, package_device_connection, \
     device, device_variable, to_system_tz

logger = logging.getLogger("cluster.package")

class repo_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "package_repo_overview.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        cur_mode = request.POST.get("mode", None)
        if cur_mode == "rescan":
            srv_com = server_command.srv_command(command="rescan_repos")
            result = contact_server(request, "tcp://localhost:8007", srv_com, timeout=10, log_result=True)
        elif cur_mode == "sync":
            srv_com = server_command.srv_command(command="sync_repos")
            result = contact_server(request, "tcp://localhost:8007", srv_com, timeout=10, log_result=True)
        xml_resp = E.response(
            E.package_repos(*[cur_r.get_xml() for cur_r in package_repo.objects.all()])
        )
        request.xml_response["response"] = xml_resp

class search_package(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "package_search.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response(
            E.package_searchs(*[cur_r.get_xml() for cur_r in package_search.objects.filter(Q(deleted=False))]),
            E.users(*[cur_u.get_xml(with_allowed_device_groups=False) for cur_u in user.objects.all()])
        )
        request.xml_response["response"] = xml_resp

class create_search(View):
    @method_decorator(transaction.commit_manually)
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        pn_prefix = "ps__new__"
        in_dict = dict([(key[len(pn_prefix):], _post[key]) for key in _post.keys() if key.startswith(pn_prefix)])
        logger.info("creating package_search with search_string '%s'" % (in_dict["search_string"]))
        new_search = package_search(
            search_string=in_dict["search_string"],
            user=request.user,
        )
        try:
            new_search.save()
        except ValidationError, what:
            request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
        else:
            transaction.commit()
            srv_com = server_command.srv_command(command="reload_searches")
            result = contact_server(request, "tcp://localhost:8007", srv_com, timeout=5, log_result=False)
            request.xml_response["new_entry"] = new_search.get_xml()

def reload_searches(request):
    srv_com = server_command.srv_command(command="reload_searches")
    return contact_server(request, "tcp://localhost:8007", srv_com, timeout=5, log_result=False)
    
class retry_search(View):
    @method_decorator(transaction.commit_manually)
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        retry_pk = _post["pk"]
        try:
            cur_search = package_search.objects.get(Q(pk=retry_pk))
        except package_search.DoesNotExist:
            request.xml_response.error("search does not exist", logger)
        else:
            if cur_search.current_state == "done":
                cur_search.current_state = "wait"
                cur_search.save(update_fields=["current_state"])
                transaction.commit()
                reload_searches(request)
            else:
                request.xml_response.warn("search is in wrong state", logger)

class delete_search(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        pk_re = re.compile("^ps__(?P<pk>\d+)$")
        ps_pk = [key for key in _post.keys() if pk_re.match(key.strip())][0].split("__")[1]
        cur_search = package_search.objects.get(Q(pk=ps_pk))
        cur_search.deleted = True
        request.xml_response.info("removed package_search %s" % (unicode(cur_search)), logger)
        cur_search.save()

class get_search_result(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        request.xml_response["response"] = E.response(
            E.package_search_results(
                *[cur_sr.get_xml() for cur_sr in package_search_result.objects.filter(Q(package_search=_post["pk"]))]
            ),
            E.package_repos(
                *[cur_r.get_xml() for cur_r in package_repo.objects.all()]
            )
        )

class use_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        try:
            cur_sr = package_search_result.objects.get(Q(pk=_post["pk"]))
        except package_search_result.DoesNotExist:
            request.xml_response.error("package_result not found", logger)
        else:
            request.xml_response.info("copied package_result", logger)
            try:
                new_p = cur_sr.create_package()
            except IntegrityError, what:
                request.xml_response.error("error modifying: %s" % (unicode(what)), logger)

class unuse_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        try:
            cur_p = package.objects.get(Q(pk=_post["pk"]))
        except package.DoesNotExist:
            request.xml_response.error("package not found", logger)
        else:
            num_ref = get_related_models(cur_p)
            if num_ref:
                request.xml_response.error("cannot remove: %s" % (logging_tools.get_plural("reference", num_ref)),
                            logger)
            else:
                cur_p.delete()
                request.xml_response.info("removed package", logger)
    
class install(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "package_install.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response(
            E.packages(
                *[cur_p.get_xml() for cur_p in package.objects.all()]
            ),
            E.target_states(
                *[E.target_state(key, pk=key) for key in ["keep", "install", "upgrade", "erase"]]
                ),
            E.package_repos(*[cur_r.get_xml() for cur_r in package_repo.objects.all()])
        )
        request.xml_response["response"] = xml_resp

class refresh(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        # print time.mktime(datetime.datetime.now().timetuple()), int(float(_post["cur_time"]))
        # pprint.pprint(_post)
        dev_list = [key.split("__")[1] for key in _post.getlist("sel_list[]")]
        xml_resp = E.response(
            E.package_device_connections(
                *[cur_pdc.get_xml() for cur_pdc in package_device_connection.objects.filter(Q(device__in=dev_list))]
            ),
            E.last_contacts(
                *[E.last_contact(device="%d" % (cur_var.device_id), when="%d" % (
                    time.mktime(to_system_tz(cur_var.val_date).timetuple())))
                    for cur_var in device_variable.objects.filter(Q(name="package_server_last_contact") & Q(device__pk__in=dev_list))]
            )
        )
        request.xml_response["response"] = xml_resp

class add_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        dev_pk, pack_pk = (
            int(_post["dev_key"].split("__")[1]),
            int(_post["pack_key"].split("__")[1]))
        try:
            cur_pdc = package_device_connection.objects.get(Q(device=dev_pk) & Q(package=pack_pk))
        except package_device_connection.DoesNotExist:
            new_pdc = package_device_connection(
                device=device.objects.get(Q(pk=dev_pk)),
                package=package.objects.get(Q(pk=pack_pk)))
            new_pdc.save()
            request.xml_response["new_entry"] = new_pdc.get_xml()
            request.xml_response.info("added connection", logger)
        else:
            request.xml_response.error("connection already exists", logger)

class remove_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        pdc_pk = int(_post["pdc_key"].split("__")[1])
        try:
            cur_pdc = package_device_connection.objects.get(Q(pk=pdc_pk))
        except package_device_connection.DoesNotExist:
            request.xml_response.error("connection doest not exists", logger)
        else:
            cur_pdc.delete()
            request.xml_response.info("connection removed", logger)

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
        #print flag_name
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
        result = contact_server(request, "tcp://localhost:8007", srv_com, timeout=10, log_result=False)
        if result:
            #print result.pretty_print()
            request.xml_response.info("sent sync to server", logger)
    
