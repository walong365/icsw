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

""" setup views """

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import partition_table, image
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.backbone.render import render_me
from lxml.builder import E  # @UnresolvedImport
from initat.tools import server_command

logger = logging.getLogger("cluster.setup")


class validate_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_part = partition_table.objects.prefetch_related(
            "partition_disc_set",
            "partition_disc_set__partition_set",
            "partition_disc_set__partition_set__partition_fs",
            "lvm_vg_set",
            "lvm_lv_set__lvm_vg",
        ).order_by("name").get(Q(pk=_post["pt_pk"]))
        prob_list = cur_part.validate()
        request.xml_response["response"] = E.problems(
            valid="1" if cur_part.valid else "0",
            *[
                E.problem(
                    p_str,
                    g_problem="1" if g_problem else "0",
                    level="%d" % (cur_lev)
                ) for cur_lev, p_str, g_problem in prob_list
            ]
        )


class scan_for_images(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="get_image_list")
        srv_result = contact_server(request, "server", srv_com, timeout=10, log_result=True)
        if srv_result:
            present_img_names = image.objects.all().values_list("name", flat=True)
            # print srv_result.pretty_print()
            if int(srv_result["result"].attrib["state"]) == server_command.SRV_REPLY_STATE_OK:
                img_list = srv_result.xpath(".//ns:image_list", smart_strings=False)
                if len(img_list):
                    f_img_list = E.found_images(src=img_list[0].attrib["image_dir"])
                    for f_num, f_image in enumerate(srv_result.xpath(".//ns:image", smart_strings=False)):
                        f_img_list.append(
                            E.found_image(
                                f_image.text,
                                present="1" if f_image.text in present_img_names else "0",
                                name=f_image.text,
                                pk="{:d}".format(f_num + 1),
                                **f_image.attrib)
                        )
                    request.xml_response["response"] = f_img_list
                else:
                    request.xml_response.error("no images found", logger)


class use_image(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        img_name = _post["img_name"]
        logger.info("use_image called, image_name {}".format(img_name))
        srv_com = server_command.srv_command(command="get_image_list")
        srv_result = contact_server(request, "server", srv_com, timeout=10, log_result=False)
        image.take_image(request.xml_response, srv_result, img_name, logger=logger)


class rescan_kernels(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="rescan_kernels")
        _srv_result = contact_server(
            request,
            "mother",
            srv_com,
            timeout=180,
            log_result=True,
            split_send=False
        )


class BuildImage(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        image_pk = int(request.POST["image_pk"])
        image_obj = image.objects.get(pk=image_pk)
        image_obj.build_lock = not image_obj.build_lock
        image_obj.save()
        request.xml_response.warn("not implemented yet")
        # request.xml_response.info("building image {}".format(image_obj.name), logger)
