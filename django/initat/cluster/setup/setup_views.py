# setup views

import os
import pprint
import logging_tools
import logging
import process_tools
import server_command
from lxml import etree
from lxml.builder import E

from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View

from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.backbone.models import partition_table, partition_disc, partition, \
     partition_fs, image, architecture, device_class, device_location, get_related_models, \
     kernel

logger = logging.getLogger("cluster.setup")

class partition_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "part_overview.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response()
        part_list = E.partition_tables()
        for cur_part in partition_table.objects.all().prefetch_related(
            "partition_disc_set",
            "partition_disc_set__partition_set",
            "partition_disc_set__partition_set__partition_fs",
            ).order_by("name"):
            part_list.append(cur_part.get_xml(validate=True))
        xml_resp.append(part_list)
        xml_resp.append(
            E.partition_fs_list(
                *[cur_pfs.get_xml() for cur_pfs in partition_fs.objects.all()]
            )
        )
        request.xml_response["response"] = xml_resp

class validate_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_part = partition_table.objects.prefetch_related(
            "partition_disc_set",
            "partition_disc_set__partition_set",
            "partition_disc_set__partition_set__partition_fs",
            ).order_by("name").get(Q(pk=_post["pt_pk"]))
        request.xml_response["response"] = cur_part.get_xml(validate=True)

class create_part_disc(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_part = partition_table.objects.get(Q(pk=_post["pt_pk"]))
        new_disc = partition_disc(
            partition_table=cur_part,
            disc=_post["disc"])
        try:
            new_disc.save()
        except ValidationError, what:
            request.xml_response.error("cannot add disc: %s" % (unicode(what.messages[0])), logger)
        else:
            request.xml_response.info("added disc %s" % (unicode(new_disc)), logger)

class delete_part_disc(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_disc = partition_disc.objects.get(Q(pk=_post["pd_pk"]) & Q(partition_table=_post["pt_pk"]))
        cur_disc.delete()
        return request.xml_response.create_response()

class create_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_part = partition_table.objects.get(Q(pk=_post["pt_pk"]))
        cur_disc = partition_disc.objects.get(Q(pk=_post["pd_pk"]))
        cur_fstype = partition_fs.objects.get(Q(pk=_post["fstype"]))
        new_part = partition(
            partition_disc=cur_disc,
            partition_fs=cur_fstype,
            pnum=_post["pnum"])
        try:
            new_part.save()
        except ValidationError, what:
            request.xml_response.error("cannot add partition: %s" % (unicode(what.messages[0])), logger)
        else:
            request.xml_response.info("added partition %s" % (unicode(new_part)), logger)

class delete_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_part = partition.objects.get(Q(pk=_post["part_pk"]))
        cur_part.delete()
    
class image_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "image_overview.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        img_list = E.images()
        for cur_img in image.objects.all().prefetch_related("new_image"):
            img_xml = cur_img.get_xml()
            img_xml.attrib["usecount"] = "%d" % (len(cur_img.new_image.all()))
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
        return render_me(request, "kernel_overview.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        kernel_list = E.kernels()
        for cur_kernel in kernel.objects.all():
            kernel_xml = cur_kernel.get_xml()
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
            #print srv_result.pretty_print()
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

class delete_image(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        img_name = _post["img_name"]
        try:
            del_image = image.objects.get(Q(name=img_name))
        except image.DoesNotExist:
            request.xml_response.error(
                "image '%s' does not exist" % (img_name), logger)
        else:
            num_ref = get_related_models(del_image)
            if num_ref:
                request.xml_response.error(
                    "cannot delete image '%s' because of reference" % (img_name),
                    logger)
            else:
                del_image.delete()
                request.xml_response.info("deleted image '%s" % (img_name), logger)

class use_image(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        img_name = _post["img_name"]
        logger.info("use_image called, image_name %s" % (img_name))
        try:
            cur_img = image.objects.get(Q(name=img_name))
        except image.DoesNotExist:
            srv_com = server_command.srv_command(command="get_image_list")
            srv_result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=10, log_result=False)
            img_xml = srv_result.xpath(None, ".//ns:image[text() = '%s']" % (img_name))
            if len(img_xml):
                img_xml = img_xml[0]
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
    
class show_device_class_location(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "cluster_device_class_location.html")()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        xml_resp.append(E.device_classes(
            *[cur_dcl.get_xml() for cur_dcl in device_class.objects.all()]))
        xml_resp.append(E.device_locations(
            *[cur_dcl.get_xml() for cur_dcl in device_location.objects.all()]))
    