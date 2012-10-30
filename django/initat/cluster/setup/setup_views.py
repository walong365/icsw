# setup views

from django.http import HttpResponse
from initat.cluster.frontend import render_tools
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
from initat.cluster.backbone.models import partition_table, partition_disc, partition, partition_fs

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
        "partition_disc_set__partition_set").order_by("name"):
        part_list.append(cur_part.get_xml())
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
    