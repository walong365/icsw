# package views

import os
from django.http import HttpResponse
from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import init_logging, logging_pool
from django.conf import settings
from django.db.models import Q
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import logging_tools
from lxml import etree
import pprint
import re
from lxml.builder import E
import process_tools
from initat.cluster.backbone.models import package_repo, package_search, user, \
     package_search_result, package, get_related_models, package_device_connection, \
     device
import server_command
import net_tools

@login_required
@init_logging
def repo_overview(request):
    if request.method == "GET":
        return render_me(request, "package_repo_overview.html", {})()
    else:
        xml_resp = E.response(
            E.package_repos(*[cur_r.get_xml() for cur_r in package_repo.objects.all()])
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()

@login_required
@init_logging
def search_package(request):
    if request.method == "GET":
        return render_me(request, "package_search.html", {})()
    else:
        xml_resp = E.response(
            E.package_searchs(*[cur_r.get_xml() for cur_r in package_search.objects.filter(Q(deleted=False))]),
            E.users(*[cur_u.get_xml() for cur_u in user.objects.all()])
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()

@transaction.commit_manually
@login_required
@init_logging
def create_search(request):
    _post = request.POST
    pn_prefix = "ps__new__"
    in_dict = dict([(key[len(pn_prefix):], _post[key]) for key in _post.keys() if key.startswith(pn_prefix)])
    request.log("creating package_search with search_string '%s'" % (in_dict["search_string"]))
    new_search = package_search(
        search_string=in_dict["search_string"],
        user=request.session["db_user"],
    )
    try:
        new_search.save()
    except ValidationError, what:
        request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        transaction.commit()
        srv_com = server_command.srv_command(command="reload_searches")
        result = net_tools.zmq_connection("config_webfrontend", timeout=5).add_connection("tcp://localhost:8007", srv_com)
        if not result:
            request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
        request.xml_response["new_entry"] = new_search.get_xml()
    return request.xml_response.create_response()

def reload_searches(request):
    srv_com = server_command.srv_command(command="reload_searches")
    result = net_tools.zmq_connection("config_webfrontend", timeout=5).add_connection("tcp://localhost:8007", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return result
    
@transaction.commit_manually
@login_required
@init_logging
def retry_search(request):
    _post = request.POST
    retry_pk = _post["pk"]
    try:
        cur_search = package_search.objects.get(Q(pk=retry_pk))
    except package_search.DoesNotExist:
        request.log("search does not exist", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        if cur_search.current_state == "done":
            cur_search.current_state = "wait"
            cur_search.save(update_fields=["current_state"])
            transaction.commit()
            reload_searches(request)
        else:
            request.log("search is in wrong state", logging_tools.LOG_LEVEL_WARN, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_search(request):
    _post = request.POST
    pk_re = re.compile("^ps__(?P<pk>\d+)$")
    ps_pk = [key for key in _post.keys() if pk_re.match(key.strip())][0].split("__")[1]
    cur_search = package_search.objects.get(Q(pk=ps_pk))
    cur_search.deleted = True
    request.log("removed package_search %s" % (unicode(cur_search)), xml=True)
    cur_search.save()
    return request.xml_response.create_response()

@login_required
@init_logging
def get_search_result(request):
    _post = request.POST
    request.xml_response["response"] = E.response(
        E.package_search_results(
            *[cur_sr.get_xml() for cur_sr in package_search_result.objects.filter(Q(package_search=_post["pk"]))]
        ),
        E.package_repos(
            *[cur_r.get_xml() for cur_r in package_repo.objects.all()]
        )
    )
    return request.xml_response.create_response()

@login_required
@init_logging
def use_package(request):
    _post = request.POST
    try:
        cur_sr = package_search_result.objects.get(Q(pk=_post["pk"]))
    except package_search_result.DoesNotExist:
        request.log("package_result not found", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("copied package_result", xml=True)
        try:
            new_p = cur_sr.create_package()
        except IntegrityError, what:
            request.log("error modifying: %s" % (unicode(what)), logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def unuse_package(request):
    _post = request.POST
    try:
        cur_p = package.objects.get(Q(pk=_post["pk"]))
    except package.DoesNotExist:
        request.log("package not found", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        num_ref = get_related_models(cur_p)
        if num_ref:
            request.log("cannot remove: %s" % (logging_tools.get_plural("reference", num_ref)),
                        logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            cur_p.delete()
            request.log("removed package", xml=True)
    return request.xml_response.create_response()
    
@login_required
@init_logging
def install(request):
    if request.method == "GET":
        return render_me(request, "package_install.html", {})()
    else:
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
        return request.xml_response.create_response()

@login_required
@init_logging
def add_package(request):
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
        request.log("added connection", xml=True)
    else:
        request.log("connection already exists", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def remove_package(request):
    _post = request.POST
    pdc_pk = int(_post["pdc_key"].split("__")[1])
    try:
        cur_pdc = package_device_connection.objects.get(Q(pk=pdc_pk))
    except package_device_connection.DoesNotExist:
        request.log("connection doest not exists", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        cur_pdc.delete()
        request.log("connection removed", xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def change_target_state(request):
    _post = request.POST
    cur_pdc = package_device_connection.objects.get(Q(pk=_post["pdc_key"].split("__")[1]))
    cur_pdc.target_state = _post["value"]
    cur_pdc.save()
    # signal package-server
    return request.xml_response.create_response()

@login_required
@init_logging
def change_package_flag(request):
    _post = request.POST
    cur_pdc = package_device_connection.objects.get(Q(pk=_post["pdc_key"].split("__")[1]))
    flag_name = _post["pdc_key"].split("__")[-1]
    value = True if int(_post["value"]) else False
    setattr(cur_pdc, flag_name, value)
    cur_pdc.save()
    # signal package-server
    return request.xml_response.create_response()

@login_required
@init_logging
def synchronize(request):
    srv_com = server_command.srv_command(command="new_config")
    result = net_tools.zmq_connection("pack_webfrontend", timeout=10).add_connection("tcp://localhost:8007", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        #print result.pretty_print()
        request.log("sent sync to server", xml=True)
    return request.xml_response.create_response()
    