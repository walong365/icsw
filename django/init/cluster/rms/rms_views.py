# rms views

import sys
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
import os
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
import pprint
from init.cluster.backbone.models import user
from django.db.models import Q
import random
from init.cluster.frontend import render_tools
from django.conf import settings
from lxml import etree
import argparse
import json
import sge_tools

my_sge_info = None

def init_sge_info():
    global my_sge_info
    if not my_sge_info:
        my_sge_info = sge_tools.sge_info(server="127.0.0.1",
                                         default_pref=["server"],
                                         never_direct=True)

def update_sge_info():
    my_sge_info.update()
    my_sge_info.build_luts()
    
def overview(request):
    job_options, node_options = (
        sge_tools.get_empty_job_options(),
        sge_tools.get_empty_node_options())
    return render_tools.render_me(request, "rms_overview.html", {
        "run_job_headers"  : sge_tools.get_running_headers(job_options),
        "wait_job_headers" : sge_tools.get_waiting_headers(job_options),
        "node_headers"     : sge_tools.get_node_headers(node_options)
    })()

def _sort_list(in_list, _post):
##    for key in sorted(_post):
##        print key, _post[key]
    start_idx = int(_post["iDisplayStart"])
    num_disp  = int(_post["iDisplayLength"])
    total_data_len = len(in_list)
    in_list = [[sub_node.text for sub_node in row] for row in in_list]
    s_str = _post.get("sSearch", "").strip()
    if s_str:
        in_list = [row for row in in_list if any([cur_text.count(s_str) for cur_text in row])]
    filter_data_len = len(in_list)
    for sort_key in [key for key in _post.keys() if key.startswith("sSortDir_")]:
        sort_dir = _post[sort_key]
        sort_idx = int(_post["iSortCol_%s" % (sort_key.split("_")[-1])])
        if sort_dir == "asc":
            in_list = sorted(in_list, cmp=lambda x,y: cmp(x[sort_idx], y[sort_idx]))
        else:
            in_list = sorted(in_list, cmp=lambda x,y: cmp(y[sort_idx], x[sort_idx]))
    show_list = in_list[start_idx : start_idx + num_disp]
    return {"sEcho" : int(_post["sEcho"]),
            "iTotalRecords"        : total_data_len,
            "iTotalDisplayRecords" : filter_data_len,
            "aaData" : show_list}

def get_node_xml(request):
    _post = request.POST
    init_sge_info()
    update_sge_info()
    job_options, node_options = (
        sge_tools.get_empty_job_options(),
        sge_tools.get_empty_node_options())
    node_list     = sge_tools.build_node_list(my_sge_info, node_options)
    json_resp = _sort_list(node_list, _post)
    return HttpResponse(json.dumps(json_resp), mimetype="application/json")

def get_run_jobs_xml(request):
    _post = request.POST
    init_sge_info()
    update_sge_info()
    job_options, node_options = (
        sge_tools.get_empty_job_options(),
        sge_tools.get_empty_node_options())
    run_job_list  = sge_tools.build_running_list(my_sge_info, job_options)
    json_resp = _sort_list(run_job_list, _post)
    return HttpResponse(json.dumps(json_resp), mimetype="application/json")

def get_wait_jobs_xml(request):
    _post = request.POST
    init_sge_info()
    update_sge_info()
    job_options, node_options = (
        sge_tools.get_empty_job_options(),
        sge_tools.get_empty_node_options())
    wait_job_list  = sge_tools.build_waiting_list(my_sge_info, job_options)
    json_resp = _sort_list(wait_job_list, _post)
    return HttpResponse(json.dumps(json_resp), mimetype="application/json")
