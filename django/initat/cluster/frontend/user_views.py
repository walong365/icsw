# user views

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
     partition_fs, image, architecture, device_class, device_location, group, user, \
     device_config
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
        # get homedir export
        exp_list = E.homedir_exports(
            E.homedir_export("none", pk="0")
        )
        home_exp = device_config.objects.filter(Q(config__name__icontains="homedir") & Q(config__name__icontains="export") & Q(config__config_str__name="homeexport")).select_related("device", "config").prefetch_related("config__config_str_set")
        for cur_exp in home_exp:
            exp_list.append(
                E.homedir_export("%s on %s" % (cur_exp.config.config_str_set.get(Q(name="homeexport")).value,
                                               unicode(cur_exp.device)),
                                 pk="%d" % (cur_exp.pk))
            )
        xml_resp = E.response(
            exp_list,
            E.groups(*[cur_g.get_xml() for cur_g in group.objects.all()]),
            E.users(*[cur_u.get_xml() for cur_u in user.objects.all()]),
            E.shells(*[E.shell(cur_shell, pk=cur_shell) for cur_shell in sorted(shell_names)])
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()
