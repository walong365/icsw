# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" RMS views """

import datetime
import json
import logging
import sys
import threading
import time
from collections import namedtuple

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from lxml.builder import E

from initat.cluster.backbone.models import rms_job_run
from initat.cluster.backbone.routing import SrvTypeRouting
from initat.cluster.backbone.serializers import rms_job_run_serializer
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.tools import logging_tools, server_command

try:
    from initat.tools import sge_tools
except ImportError:
    sge_tools = None

RMS_ADDON_KEYS = [
    key for key in sys.modules.keys() if key.startswith("initat.cluster.frontend.rms_addons.") and sys.modules[key]
]

RMS_ADDONS = [
    sys.modules[key].modify_rms() for key in RMS_ADDON_KEYS if key.split(".")[-1] not in ["base"]
]

logger = logging.getLogger("cluster.rms")

if sge_tools:
    class ThreadLockedSGEInfo(sge_tools.sge_info):
        # sge_info object with thread lock layer
        def __init__(self):
            self._init = False

        def ensure_init(self):
            if not self._init:
                self._init = True
                _srv_type = "rms-server"
                _routing = SrvTypeRouting()
                self.lock = threading.Lock()
                if _srv_type not in _routing:
                    _routing = SrvTypeRouting(force=True)
                if _srv_type in _routing:
                    _srv_address = _routing.get_server_address(_srv_type)
                else:
                    _srv_address = "127.0.0.1"
                sge_tools.sge_info.__init__(
                    self,
                    server=_srv_address,
                    source="server",
                    run_initial_update=False,
                    verbose=settings.DEBUG,
                    persistent_socket=True,
                )

        def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
            logger.log(log_level, "[sge] {}".format(what))

        def update(self):
            self.ensure_init()
            self.lock.acquire()
            try:
                sge_tools.sge_info.update(self)
                sge_tools.sge_info.build_luts(self)
            finally:
                self.lock.release()
else:
    class tl_sge_info(object):
        def update(self):
            pass

my_sge_info = ThreadLockedSGEInfo()


def get_job_options(request):
    return sge_tools.get_empty_job_options(compress_nodelist=False, queue_details=True)


def get_node_options(request):
    return sge_tools.get_empty_node_options(merge_node_queue=True, show_type=True)


class get_header_dict(View):
    @method_decorator(login_required)
    def post(self, request):
        res = rms_headers(request)
        if sge_tools is not None:
            for change_obj in RMS_ADDONS:
                change_obj.modify_headers(res)
        header_dict = {}
        for _entry in res:
            _sub_list = header_dict.setdefault(_entry.tag, [])
            if len(_entry):
                for _header in _entry[0]:
                    _sub_list.append((_header.tag, {key: value for key, value in _header.attrib.iteritems()}))

        return HttpResponse(json.dumps(header_dict), content_type="application/json")


def rms_headers(request):
    if sge_tools:
        res = E.headers(
            E.running_headers(
                sge_tools.get_running_headers(get_job_options(request)),
            ),
            E.waiting_headers(
                sge_tools.get_waiting_headers(get_job_options(request)),
            ),
            E.node_headers(
                sge_tools.get_node_headers(get_node_options(request)),
            ),
            E.done_headers(
                sge_tools.get_done_headers()
            ),
        )
    else:
        res = E.headers()
    return res


class get_header_xml(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        res = rms_headers(request)
        if sge_tools is not None:
            for change_obj in RMS_ADDONS:
                change_obj.modify_headers(res)
        request.xml_response["headers"] = res


def _node_to_value(in_node):
    _attrs = {key: value for key, value in in_node.attrib.iteritems()}
    if "raw" in _attrs:
        _attrs["raw"] = json.loads(_attrs["raw"])
    if in_node.get("type", "string") == "float":
        _attrs["value"] = _attrs["format"].format(float(in_node.text))
    else:
        _attrs["value"] = in_node.text
    return _attrs


def _sort_list(in_list, _post):
    # interpret nodes according to optional type attribute, reformat if needed, preserve attributes
    return [[_node_to_value(sub_node) for sub_node in row] for row in in_list]


def _salt_addons(request):
    if RMS_ADDONS:
        for change_obj in RMS_ADDONS:
            change_obj.set_headers(rms_headers(request))


def _fetch_rms_info(request):
    # get rms info needed by several views
    # call my_sge_info.update() before calling this!
    if sge_tools:
        run_job_list = sge_tools.build_running_list(my_sge_info, get_job_options(request), user=request.user)
        wait_job_list = sge_tools.build_waiting_list(my_sge_info, get_job_options(request), user=request.user)

        if RMS_ADDONS:
            for change_obj in RMS_ADDONS:
                change_obj.modify_running_jobs(my_sge_info, run_job_list)
                change_obj.modify_waiting_jobs(my_sge_info, wait_job_list)
        return namedtuple("RmsInfo", ["run_job_list", "wait_job_list"])(run_job_list, wait_job_list)
    else:
        return namedtuple("RmsInfo", ["run_job_list", "wait_job_list"])([], [])


class get_rms_json(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info.update()
        _salt_addons(request)
        rms_info = _fetch_rms_info(request)

        # print etree.tostring(run_job_list, pretty_print=True)
        node_list = sge_tools.build_node_list(my_sge_info, get_node_options(request))
        if RMS_ADDONS:
            for change_obj in RMS_ADDONS:
                change_obj.modify_nodes(my_sge_info, node_list)
        fc_dict = {}
        cur_time = time.time()
        for file_el in my_sge_info.get_tree().xpath(".//job_list[master/text() = \"MASTER\"]", smart_strings=False):
            file_contents = file_el.findall(".//file_content")
            if len(file_contents):
                cur_fcd = []
                for cur_fc in file_contents:
                    file_name = cur_fc.attrib["name"]
                    content = cache.get(cur_fc.attrib["cache_uuid"])
                    if content is not None:
                        lines = content.replace(r"\r\n", r"\n").split("\n")
                        content = "\n".join(reversed(lines))
                        cur_fcd.append(
                            (
                                file_name,
                                content,
                                len(content),
                                int(cur_fc.attrib.get("last_update", cur_time)),
                                min(10, len(lines) + 1)
                            )
                        )
                fc_dict[file_el.attrib["full_id"]] = list(reversed(sorted(cur_fcd, cmp=lambda x, y: cmp(x[3], y[3]))))
        # todo: add jobvars to running (waiting for rescheduled ?) list
        # print dir(rms_info.run_job_list)
        done_jobs = rms_job_run.objects.all().exclude(
            Q(end_time=None)
        ).prefetch_related(
            "rms_pe_info_set"
        ).select_related(
            "rms_queue",
            "rms_department",
            "rms_job",
            "rms_project",
            "rms_pe",
        ).prefetch_related(
            "rmsjobvariable_set",
        ).order_by(
            "-rms_job__jobid",
            "rms_job__taskid",
            "-pk"
        )[0:100]
        _done_ser = rms_job_run_serializer(done_jobs, many=True).data
        # pprint.pprint(_done_ser)
        json_resp = {
            "run_table": _sort_list(rms_info.run_job_list, _post),
            "wait_table": _sort_list(rms_info.wait_job_list, _post),
            "node_table": _sort_list(node_list, _post),
            "done_table": _done_ser,
            "sched_conf": sge_tools.build_scheduler_info(my_sge_info),
            "files": fc_dict,
        }
        return HttpResponse(json.dumps(json_resp), content_type="application/json")


class get_rms_jobinfo(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info.update()
        _salt_addons(request)
        rms_info = _fetch_rms_info(request)

        latest_possible_end_time = datetime.datetime.fromtimestamp(int(_post["jobinfo_jobsfrom"]))
        done_jobs = rms_job_run.objects.all().filter(
            Q(end_time__gt=latest_possible_end_time)
        ).select_related("rms_job")

        def xml_to_jobid(jobxml):
            return [int(jobxml.findall("job_id")[0].text), jobxml.findall("task_id")[0].text]

        json_resp = {
            "jobs_running": sorted(map(xml_to_jobid, rms_info.run_job_list)),
            "jobs_waiting": sorted(map(xml_to_jobid, rms_info.wait_job_list)),
            "jobs_finished": sorted([job.rms_job.jobid, job.rms_job.taskid if job.rms_job.taskid else ""] for job in done_jobs),
        }
        return HttpResponse(json.dumps(json_resp), content_type="application/json")


class control_job(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_action = _post["command"]
        job_id = ".".join([entry for entry in [_post["job_id"], _post["task_id"]] if entry.strip()])
        srv_com = server_command.srv_command(command="job_control", action=c_action)
        srv_com["job_list"] = srv_com.builder(
            "job_list",
            srv_com.builder("job", job_id=job_id)
        )
        contact_server(request, "rms", srv_com, timeout=10)


class control_queue(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        queue_spec = "{}@{}".format(_post["queue"], _post["host"])
        logger.info("{} on {}".format(_post["command"], queue_spec))
        srv_com = server_command.srv_command(command="queue_control", action=_post["command"])
        srv_com["queue_list"] = srv_com.builder(
            "queue_list",
            srv_com.builder("queue", queue_spec=queue_spec)
        )
        contact_server(request, "rms", srv_com, timeout=10)


class get_file_content(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "file_ids" in _post:
            file_id_list = []
            for file_id in json.loads(_post["file_ids"]):
                _parts = file_id.split(".")
                if len(_parts) == 3:
                    job_id = _parts[:2].join(".")
                    std_type = _parts[2]
                else:
                    job_id, std_type = _parts
                file_id_list.append((file_id, job_id, std_type))
        elif _post["file_id"].count(":"):
            file_parts = _post["file_id"].split(":")
            std_type = file_parts[1]
            job_id = file_parts[2]
            file_id_list = [(_post["file_id"], job_id, std_type)]
        else:
            file_parts = _post["file_id"].split(".")
            std_type = file_parts[2]
            job_id = "{}.{}".format(file_parts[0], file_parts[1])
            file_id_list = [(_post["file_id"], job_id, std_type)]
        # already refreshed ?
        _refreshed = False
        fetch_lut = {}
        for src_id, job_id, std_type in file_id_list:
            # my_sge_info.update()
            job_info = my_sge_info.get_job(job_id)
            if job_info is None and not _refreshed:
                # refresh only once
                _refreshed = True
                my_sge_info.update()
                job_info = my_sge_info.get_job(job_id)
            if job_info is not None:
                io_element = job_info.find(".//{}".format(std_type))
                if io_element is None or io_element.get("error", "0") == "1":
                    request.xml_response.error("{} not defined for job {}".format(std_type, job_id), logger)
                else:
                    fetch_lut[io_element.text] = src_id
        # print "*", job_id, job_info
        if fetch_lut:
            _resp_list = []
            # print etree.tostring(job_info)
            srv_com = server_command.srv_command(command="get_file_content")
            srv_com["file_list"] = srv_com.builder(
                "file_list",
                *[
                    srv_com.builder("file", name=_file_name, encoding="utf-8") for _file_name in fetch_lut.iterkeys()
                ]
            )
            result = contact_server(request, "server", srv_com, timeout=60, connection_id="file_fetch_{}".format(str(job_id)))
            if result is not None:
                if result.get_result()[1] > server_command.SRV_REPLY_STATE_WARN:
                    request.xml_response.error(result.get_log_tuple()[0], logger)
                else:
                    for cur_file in result.xpath(".//ns:file", smart_strings=False):
                        # print etree.tostring(cur_file)
                        if cur_file.attrib.get("error", "0") == "1":
                            request.xml_response.error(
                                "error reading {} (job {}): {}".format(
                                    cur_file.attrib["name"],
                                    job_id,
                                    cur_file.attrib["error_str"]
                                ),
                                logger
                            )
                        else:
                            # ie freezes if it displays too much text
                            text = cur_file.text
                            magic_limit = 350 * 1024
                            if int(_post.get("is_ie", "0")) and text and len(text) > magic_limit:
                                request.xml_response.info("file is too large, truncating beginning")
                                # return some first lines and mostly last lines such that in total,
                                # we transfer about $magic_limit

                                # also include first 200 lines
                                # this is needed for some people to identify the job
                                # (200 is an arbitrary number. there is relevant information from ansys around line 135)

                                lines = text.split("\n")
                                first_lines, last_lines = (lines[:200], lines[201:])
                                new_text = u""
                                while len(new_text) < magic_limit and last_lines:
                                    new_text = last_lines.pop() + u"\n" + new_text

                                cut_marker = u"\n\n[cut off output since file is too large ({} > {})]\n\n".format(
                                    logging_tools.get_size_str(len(text)),
                                    logging_tools.get_size_str(magic_limit),
                                )
                                text = u"\n".join(first_lines) + cut_marker + new_text

                            _resp_list.append(
                                E.file_info(
                                    text or "",
                                    id=fetch_lut[cur_file.attrib["name"]],
                                    name=cur_file.attrib["name"],
                                    lines=cur_file.attrib["lines"],
                                    size_str=logging_tools.get_size_str(int(cur_file.attrib["size"]), True),
                                )
                            )
            if len(_resp_list):
                request.xml_response["response"] = _resp_list
        else:
            request.xml_response.warn(
                "nothing found for {}".format(
                    logging_tools.get_plural("job", len(file_id_list))
                ),
                logger
            )


class change_job_priority(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="job_control", action="modify_priority")
        srv_com["job_list"] = srv_com.builder(
            "job_list",
            srv_com.builder("job", job_id=_post["job_id"], priority=_post["new_pri"])
        )
        contact_server(request, "rms", srv_com, timeout=10)
