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

""" setup views """

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import partition_table, \
    image, architecture, kernel
from initat.cluster.frontend.forms import kernel_form, image_form, partition_table_form, \
    partition_form, partition_disc_form, partition_sys_form
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.core.render import render_me
from lxml.builder import E # @UnresolvedImport
import logging
import os
import process_tools
import server_command

logger = logging.getLogger("cluster.setup")

class partition_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "part_overview.html", {
            "partition_table_form" : partition_table_form(),
            "partition_disc_form"  : partition_disc_form(),
            "partition_sys_form"   : partition_sys_form(),
            "partition_form"       : partition_form(),
            })()

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
            *[E.problem(p_str, g_problem="1" if g_problem else "0", level="%d" % (cur_lev)) for cur_lev, p_str, g_problem in prob_list]
        )

class image_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "image_overview.html", {
            "image_form" : image_form(),
            })()
    @method_decorator(xml_wrapper)
    def post(self, request):
        img_list = E.images()
        for cur_img in image.objects.all().prefetch_related("new_image"):
            img_xml = cur_img.get_xml()
            img_xml.attrib["usecount"] = "%d" % (cur_img.new_image.count())
            img_list.append(img_xml)
        xml_resp = E.response(
            img_list,
            E.architectures(
                *[cur_arch.get_xml() for cur_arch in architecture.objects.all()]
            ),
        )
        request.xml_response["response"] = xml_resp

class kernel_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "kernel_overview.html", {
            "kernel_form" : kernel_form(),
            })()
    @method_decorator(xml_wrapper)
    def post(self, request):
        kernel_list = E.kernels()
        for cur_kernel in kernel.objects.prefetch_related("new_kernel", "act_kernel").all():
            kernel_xml = cur_kernel.get_xml()
            kernel_xml.attrib["usecount"] = "%d" % (cur_kernel.new_kernel.count() + cur_kernel.act_kernel.count())
            kernel_list.append(kernel_xml)
        xml_resp = E.response(
            kernel_list,
            E.architectures(
                *[cur_arch.get_xml() for cur_arch in architecture.objects.all()]
            ),
        )
        request.xml_response["response"] = xml_resp

class scan_for_images(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="get_image_list")
        srv_result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=10, log_result=True)
        if srv_result:
            present_img_names = image.objects.all().values_list("name", flat=True)
            # print srv_result.pretty_print()
            if int(srv_result["result"].attrib["state"]) == server_command.SRV_REPLY_STATE_OK:
                img_list = srv_result.xpath(None, ".//ns:image_list")
                if len(img_list):
                    f_img_list = E.found_images(src=img_list[0].attrib["image_dir"])
                    for f_num, f_image in enumerate(srv_result.xpath(None, ".//ns:image")):
                        f_img_list.append(
                            E.found_image(
                                f_image.text,
                                present="1" if f_image.text in present_img_names else "0",
                                name=f_image.text,
                                pk="%d" % (f_num + 1),
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
        logger.info("use_image called, image_name %s" % (img_name))
        try:
            _cur_img = image.objects.get(Q(name=img_name))
        except image.DoesNotExist:
            srv_com = server_command.srv_command(command="get_image_list")
            srv_result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=10, log_result=False)
            img_xml = srv_result.xpath(None, ".//ns:image[text() = '%s']" % (img_name))
            if len(img_xml):
                img_xml = img_xml[0]
                print img_xml.attrib
                if "arch" not in img_xml.attrib:
                    request.xml_response.error(
                        "no architecture-attribute found in image",
                        logger
                        )
                else:
                    try:
                        img_arch = architecture.objects.get(Q(architecture=img_xml.attrib["arch"]))
                    except architecture.DoesNotExist:
                        img_arch = architecture(
                            architecture=img_xml.attrib["arch"])
                        img_arch.save()
                    img_source = srv_result.xpath(None, ".//ns:image_list/@image_dir")[0]
                    new_img = image(
                        name=img_xml.text,
                        source=os.path.join(img_source, img_xml.text),
                        sys_vendor=img_xml.attrib["vendor"],
                        sys_version=img_xml.attrib["version"].split(".", 1)[0],
                        sys_release=img_xml.attrib["version"].split(".", 1)[1],
                        bitcount=img_xml.attrib["bitcount"],
                        architecture=img_arch,
                    )
                    try:
                        new_img.save()
                    except:
                        request.xml_response.error(
                            "cannot create image: %s" % (process_tools.get_except_info()),
                            logger)
                    else:
                        request.xml_response.info("image taken", logger)
            else:
                request.xml_response.error("image has vanished ?", logger)
        else:
            request.xml_response.error("image already exists", logger)

class rescan_kernels(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="rescan_kernels")
        _srv_result = contact_server(request, "tcp://localhost:8000", srv_com, timeout=180, log_result=True)

