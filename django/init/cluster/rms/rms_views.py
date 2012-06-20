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

try:
    import sge_tools
except:
    sge_tools = None
    
def overview(request):
    # destroy old sessions stuff
    if sge_tools:
        act_si = sge_tools.sge_info(server="127.0.0.1",
                                    default_pref=["server"],
                                    never_direct=True)
        act_si.build_luts()
        options = sge_tools.get_empty_options()
        run_job_list  = sge_tools.build_running_list(act_si, options)
        wait_job_list = sge_tools.build_waiting_list(act_si, options)
    else:
        run_job_list, wait_job_list = (None, None)
    return render_tools.render_me(request, "rms_overview.html", {
        "run_job_list"  : run_job_list,
        "wait_job_list" : wait_job_list,
    })()
