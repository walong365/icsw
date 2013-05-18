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
     partition_fs, image, architecture, device_class, device_location, get_related_models, \
     kernel
import server_command
import net_tools

@login_required
@init_logging
def partition_overview(request):
    if request.method == "GET":
        return render_me(request, "part_overview.html", {})()
    else:
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
        return request.xml_response.create_response()

@login_required
@init_logging
def validate_partition(request):
    _post = request.POST
    cur_part = partition_table.objects.prefetch_related(
        "partition_disc_set",
        "partition_disc_set__partition_set",
        "partition_disc_set__partition_set__partition_fs",
        ).order_by("name").get(Q(pk=_post["pt_pk"]))
    request.xml_response["response"] = cur_part.get_xml(validate=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def create_part_disc(request):
    _post = request.POST
    cur_part = partition_table.objects.get(Q(pk=_post["pt_pk"]))
    new_disc = partition_disc(
        partition_table=cur_part,
        disc=_post["disc"])
    try:
        new_disc.save()
    except ValidationError, what:
        request.log("cannot add disc: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("added disc %s" % (unicode(new_disc)), xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_part_disc(request):
    _post = request.POST
    cur_disc = partition_disc.objects.get(Q(pk=_post["pd_pk"]) & Q(partition_table=_post["pt_pk"]))
    cur_disc.delete()
    return request.xml_response.create_response()

@login_required
@init_logging
def create_partition(request):
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
        request.log("cannot add partition: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("added partition %s" % (unicode(new_part)), xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_partition(request):
    _post = request.POST
    cur_part = partition.objects.get(Q(pk=_post["part_pk"]))
    cur_part.delete()
    return request.xml_response.create_response()
    
@login_required
@init_logging
def image_overview(request):
    if request.method == "GET":
        return render_me(request, "image_overview.html", {})()
    else:
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
        #print etree.tostring(xml_resp, pretty_print=True)
        return request.xml_response.create_response()

@login_required
@init_logging
def kernel_overview(request):
    if request.method == "GET":
        return render_me(request, "kernel_overview.html", {})()
    else:
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
        #print etree.tostring(xml_resp, pretty_print=True)
        return request.xml_response.create_response()

@login_required
@init_logging
def scan_for_images(request):
    _post = request.POST
    srv_com = server_command.srv_command(command="get_image_list")
    srv_result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=10, log_result=False)
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
                request.log("no images found", logging_tools.LOG_LEVEL_WARN, xml=True)
        else:
            request.log("server problem: %s" % (srv_result["result"].attrib["reply"]), server_command.srv_reply_to_log_level(int(srv_result["result"].attrib["state"])), xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_image(request):
    _post = request.POST
    img_name = _post["img_name"]
    try:
        del_image = image.objects.get(Q(name=img_name))
    except image.DoesNotExist:
        request.log("image '%s' does not exist" % (img_name), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        num_ref = get_related_models(del_image)
        if num_ref:
            request.log("cannot delete image '%s' because of reference" % (img_name),
                        logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            del_image.delete()
            request.log("deleted image '%s" % (img_name), xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def use_image(request):
    _post = request.POST
    img_name = _post["img_name"]
    request.log("use_image called, image_name %s" % (img_name))
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
                request.log("cannot create image: %s" % (process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_ERROR,
                            xml=True)
            else:
                request.log("image taken", xml=True)
        else:
            request.log("image has vanished ?", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("image already exists", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()
    
@login_required
@init_logging
def show_device_class_location(request):
    if request.method == "GET":
        return render_me(request, "cluster_device_class_location.html")()
    else:
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        xml_resp.append(E.device_classes(
            *[cur_dcl.get_xml() for cur_dcl in device_class.objects.all()]))
        xml_resp.append(E.device_locations(
            *[cur_dcl.get_xml() for cur_dcl in device_location.objects.all()]))
        return request.xml_response.create_response()
    