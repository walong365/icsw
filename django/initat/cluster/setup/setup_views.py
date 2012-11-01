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
     partition_fs, image, architecture
import server_command
import net_tools

@login_required
@init_logging
def partition_overview(request):
    return render_tools.render_me(request, "part_overview.html", {})()

@init_logging
def get_all_partitions(request):
    xml_resp = E.response()
    part_list = E.partitions()
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
    #print etree.tostring(xml_resp, pretty_print=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def create_new_partition_table(request):
    _post = request.POST
    new_pt = partition_table(
        name=_post["name"])
    try:
        new_pt.save()
    except ValidationError, what:
        request.log("cannot create new parition table: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("created new parition table")
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
    return render_tools.render_me(request, "image_overview.html", {})()

@init_logging
def get_all_images(request):
    xml_resp = E.response()
    img_list = E.images()
    for cur_img in image.objects.all():
        img_list.append(cur_img.get_xml())
    xml_resp.append(img_list)
    request.xml_response["response"] = xml_resp
    #print etree.tostring(xml_resp, pretty_print=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def scan_for_images(request):
    _post = request.POST
    try:
        srv_com = server_command.srv_command(command="get_image_list")
        srv_result = net_tools.zmq_connection("sfi_webfrontend", timeout=10).add_connection("tcp://localhost:8004", srv_com)
    except:
        request.log("error contacting server: %s" % (process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        if srv_result is not None:
            present_img_names = image.objects.all().values_list("name", flat=True)
            img_list = srv_result.xpath(None, ".//ns:image_list")
            if len(img_list):
                f_img_list = E.images(src=img_list[0].attrib["image_dir"])
                for f_image in srv_result.xpath(None, ".//ns:image"):
                    f_img_list.append(
                        E.found_image(
                            f_image.text,
                            present="1" if f_image.text in present_img_names else "0",
                            **f_image.attrib)
                    )
                request.xml_response["response"] = f_img_list
        else:
            request.log("got empty response",
                        logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def take_image(request):
    _post = request.POST
    take_id = _post["take_id"]
    img_name = take_id.split("__", 1)[1]
    request.log("take_image called, take_id is '%s' (image_name %s)" % (take_id, img_name))
    try:
        cur_img = image.objects.get(Q(name=img_name))
    except image.DoesNotExist:
        srv_com = server_command.srv_command(command="get_image_list")
        srv_result = net_tools.zmq_connection("sfi_webfrontend", timeout=10).add_connection("tcp://localhost:8004", srv_com)
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
    