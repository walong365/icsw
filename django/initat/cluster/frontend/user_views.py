# setup views

import os
from django.http import HttpResponse
from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import init_logging, logging_pool
from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
import logging_tools
from lxml import etree
import pprint
from lxml.builder import E
import process_tools
from initat.cluster.backbone.models import partition_table, partition_disc, partition, \
     partition_fs, image, architecture, device_class, device_location, group, user
import server_command
import net_tools

@login_required
@init_logging
def overview(request, *args, **kwargs):
    if request.method == "GET":
        if kwargs["mode"] == "table":
            return render_me(request, "user_overview.html", {})()
    else:
        shell_names = [line.strip() for line in file("/etc/shells", "r").read().split("\n") if line.strip()]
        shell_names = [line for line in shell_names if os.path.exists(line)] + ["/bin/false"]
        xml_resp = E.response(
            E.groups(*[cur_g.get_xml() for cur_g in group.objects.all()]),
            E.users(*[cur_u.get_xml() for cur_u in user.objects.all()]),
            E.shells(*[E.shell(cur_shell, pk=cur_shell) for cur_shell in sorted(shell_names)])
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()
