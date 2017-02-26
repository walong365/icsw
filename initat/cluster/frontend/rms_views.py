# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
import re
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
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from lxml.builder import E
from rest_framework import viewsets

from initat.cluster.backbone.server_enums import icswServiceEnum

from initat.cluster.backbone.models import rms_job_run, device
from initat.cluster.backbone.models.functions import cluster_timezone
from initat.cluster.backbone.serializers import rms_job_run_serializer
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, server_command, process_tools

RMS_ADDON_KEYS = [
    key for key in list(sys.modules.keys()) if key.startswith("initat.cluster.frontend.rms_addons.") and sys.modules[key]
]

RMS_ADDONS = [
    sys.modules[key].modify_rms() for key in RMS_ADDON_KEYS if key.split(".")[-1] not in ["base"]
]

# memcached port and address
MC_PORT = InstanceXML(quiet=True).get_port_dict(icswServiceEnum.memcached, command=True)
MC_ADDRESS = "127.0.0.1"

logger = logging.getLogger("cluster.rms")

my_sge_info = None


# to be beautified ...


def get_sge_info():
    global my_sge_info
    if my_sge_info is None:
        from initat.tools import sge_tools
        # display loaded packages
        # for key in sorted(list(set([".".join(_key.split(".", 2)[:-1]) for _key in sys.modules.keys()]))):
        #    print("*", key)

        class ThreadLockedSGEInfo(sge_tools.SGEInfo):
            # sge_info object with thread lock layer
            def __init__(self):
                from initat.cluster.backbone.routing import SrvTypeRouting
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
                sge_tools.SGEInfo.__init__(
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
                self.lock.acquire()
                try:
                    sge_tools.SGEInfo.update(self, timeout=15)
                    sge_tools.SGEInfo.build_luts(self)
                finally:
                    self.lock.release()
        my_sge_info = ThreadLockedSGEInfo()
    return my_sge_info


def get_job_options(request):
    from initat.tools import sge_tools
    return sge_tools.get_empty_job_options(compress_nodelist=False, queue_details=True, show_variables=True)


def get_node_options(request):
    from initat.tools import sge_tools
    return sge_tools.get_empty_node_options(merge_node_queue=True, show_type=True, show_seq=True, show_memory=True)


class get_header_dict(View):
    @method_decorator(login_required)
    def post(self, request):
        res = rms_headers(request)
        for change_obj in RMS_ADDONS:
            change_obj.modify_headers(res)
        header_dict = {}
        for _entry in res:
            _sub_list = header_dict.setdefault(_entry.tag, [])
            if len(_entry):
                for _header in _entry[0]:
                    _sub_list.append((_header.tag, {key: value for key, value in _header.attrib.items()}))

        return HttpResponse(json.dumps(header_dict), content_type="application/json")


def rms_headers(request):
    from initat.tools import sge_tools
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
        for change_obj in RMS_ADDONS:
            change_obj.modify_headers(res)
        request.xml_response["headers"] = res


class RMSJsonMixin(object):
    def optimize_list(self, in_list: list) -> list:
        def shorten_node_list(n_list: list) -> str:
            if len(n_list) == 1:
                return n_list[0]
            else:
                # check for unique domainname
                dn_dict = {}
                for name in n_list:
                    if name.count("."):
                        _s, _d = name.split(".", 1)
                        dn_dict.setdefault(_d, []).append(_s)
                    else:
                        dn_dict.setdefault(None, []).append(_s)
                dn_dict = {
                    _domain: "{{{}}}".format(
                        logging_tools.reduce_list(_names)
                    ) if len(_names) > 1 else _names[0] for _domain, _names in dn_dict.items()
                }
            _opt_list = [
                "{}{}".format(
                    _opt_names,
                    ".{}".format(_domain) if _domain else ""
                ) for _domain, _opt_names in dn_dict.items()
            ]
            if len(_opt_list) == 1:
                return _opt_list[0]
            else:
                return "[{}]".format(
                    ", ".join(_opt_list)
                )

        # print("I", in_list)
        out_list = []
        queue_dict = {}
        simple_dict = {}
        for entry in in_list:

            _parts = entry.strip().split()
            _simple_part = [_part for _part in _parts if _part[0] == _part[-1] and _part[0] in {"\"", "'"}]
            if len(_simple_part) > 0:
                # take first match, todo: handle multiple occurances
                _simple_part = _simple_part[0]
                _index = _parts.index(_simple_part)
                _pre, _post = (
                    " ".join(_parts[0:_index]),
                    " ".join(_parts[_index + 1:])
                )
                _simple_part = _simple_part[1:-1]
                if _simple_part.count("@"):
                    # is a queue specifier
                    queue_dict.setdefault((_pre, _post), []).append(_simple_part)
                else:
                    simple_dict.setdefault((_pre, _post), []).append(_simple_part)
            else:
                out_list.append(" ".join(_parts))
        # import pprint
        # pprint.pprint(_list)
        # pprint.pprint(out_list)
        # pprint.pprint(queue_dict)
        for key, s_list in simple_dict.items():
            out_list.append(
                "{} \"{}\" {}".format(
                    key[0],
                    ", ".join(s_list),
                    key[1],
                )
            )
        # add optimized queue entries
        for key, n_list in queue_dict.items():
            local_q_dict = {}
            for q_spec in n_list:
                q_name, n_name = q_spec.split("@", 1)
                local_q_dict.setdefault(q_name, []).append(n_name)
            res_list = []
            for q_name, node_names in local_q_dict.items():
                res_list.append(
                    "{}@{}".format(
                        q_name,
                        shorten_node_list(node_names),
                    )
                )
            out_list.append(
                "{} {} {}".format(
                    key[0],
                    ", ".join(res_list),
                    key[1],
                )
            )

        return out_list

    def node_to_value(self, in_node):
        _attrs = {
            key: value for key, value in in_node.attrib.items()
        }
        if "raw" in _attrs:
            _raw = json.loads(_attrs["raw"])
            if in_node.tag == "messages":
                _raw = self.optimize_list(_raw)
            _attrs["raw"] = _raw
        if in_node.get("type", "string") == "float":
            _attrs["value"] = _attrs["format"].format(float(in_node.text))
        elif in_node.get("type", "string") == "int":
            _attrs["value"] = int(in_node.text)
        else:
            _attrs["value"] = in_node.text
        return _attrs

    def xml_to_json(self, in_list):
        def _get_id(in_dict):
            if in_dict["task_id"]["value"]:
                return "{}.{}".format(
                    in_dict["job_id"]["value"],
                    in_dict["task_id"]["value"],
                )
            else:
                return "{}".format(
                    in_dict["job_id"]["value"],
                )
        _res_dict = {}
        for row in in_list:
            _dict = {sub_node.tag: self.node_to_value(sub_node) for sub_node in row}
            _res_dict[_get_id(_dict)] = _dict
        return _res_dict

    def sort_list(self, in_list: list) -> list:
        # interpret nodes according to optional type attribute, reformat if needed, preserve attributes
        return [
            [
                self.node_to_value(sub_node) for sub_node in row
            ] for row in in_list
        ]


def _salt_addons(request):
    if RMS_ADDONS:
        for change_obj in RMS_ADDONS:
            change_obj.set_headers(rms_headers(request))


def _fetch_rms_info(request):
    # get rms info needed by several views
    # call my_sge_info.update() before calling this!
    my_sge_info = get_sge_info()
    if my_sge_info is not None:
        from initat.tools import sge_tools
        if request.user.is_authenticated():
            _user = request.user
        else:
            _user = None
        run_job_list = sge_tools.build_running_list(my_sge_info, get_job_options(request), user=_user, django_init=True)
        wait_job_list = sge_tools.build_waiting_list(my_sge_info, get_job_options(request), user=_user)
        if RMS_ADDONS:
            for change_obj in RMS_ADDONS:
                change_obj.modify_running_jobs(my_sge_info, run_job_list)
                change_obj.modify_waiting_jobs(my_sge_info, wait_job_list)
        return namedtuple(
            "RmsInfo",
            ["run_job_list", "wait_job_list"]
        )(
            run_job_list, wait_job_list,
        )
    else:
        return namedtuple(
            "RmsInfo",
            ["run_job_list", "wait_job_list"]
        )(
            [], [],
        )


class get_rms_done_json(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
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
        json_resp = {
            "done_table": _done_ser,
        }
        return HttpResponse(json.dumps(json_resp), content_type="application/json")


class get_rms_current_json(View, RMSJsonMixin):
    @method_decorator(login_required)
    def post(self, request):
        import memcache
        from initat.tools import sge_tools
        _post = request.POST
        my_sge_info = get_sge_info()
        my_sge_info.update()
        _salt_addons(request)
        rms_info = _fetch_rms_info(request)

        # print etree.tostring(run_job_list, pretty_print=True)
        node_list = sge_tools.build_node_list(my_sge_info, get_node_options(request))
        if RMS_ADDONS:
            for change_obj in RMS_ADDONS:
                change_obj.modify_nodes(my_sge_info, node_list)

        # load values
        # get name of all hosts
        _host_names = node_list.xpath(".//node/host/text()")
        # memcache client
        _mcc = memcache.Client(["{}:{:d}".format(MC_ADDRESS, MC_PORT)])
        h_dict_raw = _mcc.get("cc_hc_list")
        if h_dict_raw:
            h_dict = json.loads(h_dict_raw)
        else:
            h_dict = {}
        # required keys
        req_keys = re.compile("^(load\.(1|5|15)$)|(mem\.(avail|free|used)\..*)$")
        # resolve to full host names / dev_pks / uuids
        _dev_dict = {
            _name: {
                "uuid": _uuid,
                "values": {},
                # core id -> job list
                "pinning": {},
                "idx": _idx,
            } for _name, _uuid, _idx in device.objects.filter(
                Q(name__in=_host_names)
            ).values_list("name", "uuid", "idx")
        }
        # reverse lut (idx -> name)
        _rev_lut = {
            _value["idx"]: _key for _key, _value in _dev_dict.items()
        }
        for _name, _struct in _dev_dict.items():
            if _struct["uuid"] in h_dict:
                try:
                    _value_list = json.loads(_mcc.get("cc_hc_{}".format(_struct["uuid"])))
                except:
                    logger.error(
                        "error decoding json.loads: {}".format(
                            process_tools.get_except_info()

                        )
                    )
                else:
                    for _list in _value_list:
                        if req_keys.match(_list[1]):
                            _struct["values"][_list[1]] = _list[5] * _list[7]

        fc_dict = {}
        cur_time = time.time()
        # job_ids = my_sge_info.get_tree().xpath(".//job_list[master/text() = \"MASTER\"]/@full_id", smart_strings=False)
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
                            {
                                "name": file_name,
                                "content": content,
                                "size": len(content),
                                "last_update": int(cur_fc.attrib.get("last_update", cur_time)),
                                "disp_len": min(10, len(lines) + 1),
                            }
                        )
                fc_dict[file_el.attrib["full_id"]] = list(reversed(sorted(cur_fcd, key=lambda x: x["last_update"])))
        for job_el in my_sge_info.get_tree().xpath(".//job_list[master/text() = \"MASTER\"]", smart_strings=False):
            job_id = job_el.attrib["full_id"]
            pinning_el = job_el.find(".//pinning_info")
            if pinning_el is not None and pinning_el.text:
                # device_id -> process_id -> core_id
                _pd = json.loads(pinning_el.text)
                for _node_idx, _pin_dict in _pd.items():
                    if int(_node_idx) in _rev_lut:
                        _dn = _rev_lut[int(_node_idx)]
                        for _proc_id, _core_id in _pin_dict.items():
                            _dev_dict[_dn]["pinning"].setdefault(_core_id, []).append(job_id)
        _gsi = my_sge_info.tree.find(".//global_waiting_info")
        if _gsi is not None:
            _g_msgs = [
                {
                    "value": _line
                } for _line in self.optimize_list(
                    [
                        self.node_to_value(el)["value"] for el in _gsi.findall(".//message")
                    ]
                )
            ]

        else:
            _g_msgs = []
        # import pprint
        # pprint.pprint(self.sort_list(rms_info.wait_job_list))
        json_resp = {
            "run_table": self.sort_list(rms_info.run_job_list),
            "wait_table": self.sort_list(rms_info.wait_job_list),
            "node_table": self.sort_list(node_list),
            "sched_conf": sge_tools.build_scheduler_info(my_sge_info),
            "files": fc_dict,
            "fstree": sge_tools.build_fstree_info(my_sge_info),
            "node_values": _dev_dict,
            "global_waiting_info": _g_msgs,
        }
        return HttpResponse(json.dumps(json_resp), content_type="application/json")


class get_rms_jobinfo(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info = get_sge_info()
        my_sge_info.update()
        _salt_addons(request)
        rms_info = _fetch_rms_info(request)

        latest_possible_end_time = cluster_timezone.localize(datetime.datetime.fromtimestamp(int(_post["jobinfo_jobsfrom"])))
        done_jobs = rms_job_run.objects.all().filter(
            Q(end_time__gt=latest_possible_end_time)
        ).select_related("rms_job")

        def xml_to_jobid(jobxml):
            return [
                int(jobxml.findall("job_id")[0].text),
                jobxml.findall("task_id")[0].text
            ]

        json_resp = {
            "jobs_running": sorted(
                map(
                    xml_to_jobid,
                    rms_info.run_job_list
                )
            ),
            "jobs_waiting": sorted(
                map(
                    xml_to_jobid,
                    rms_info.wait_job_list
                )
            ),
            "jobs_finished": sorted(
                [
                    job.rms_job.jobid, job.rms_job.taskid if job.rms_job.taskid else ""
                ] for job in done_jobs
            ),
        }
        return HttpResponse(json.dumps(json_resp), content_type="application/json")


# liebherr
class RmsJobViewSet(viewsets.ViewSet, RMSJsonMixin):
    @csrf_exempt
    def simple_get(self, request):
        my_sge_info = get_sge_info()
        my_sge_info.update()

        _salt_addons(request)

        rms_info = _fetch_rms_info(request)

        json_resp = {
            "jobs_running": self.xml_to_json(rms_info.run_job_list),
            "jobs_waiting": self.xml_to_json(rms_info.wait_job_list),
        }
        return HttpResponse(json.dumps(json_resp), content_type="application/json")


class control_job(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_action = _post["command"]
        job_id = ".".join(
            [
                entry for entry in [
                    _post["job_id"],
                    _post["task_id"]
                ] if entry.strip()
            ]
        )
        srv_com = server_command.srv_command(command="job_control", action=c_action)
        srv_com["job_list"] = srv_com.builder(
            "job_list",
            srv_com.builder("job", job_id=job_id)
        )
        contact_server(request, icswServiceEnum.rms_server, srv_com, timeout=10)


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
        contact_server(request, icswServiceEnum.rms_server, srv_com, timeout=10)


class get_file_content(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        my_sge_info = get_sge_info()
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
                    srv_com.builder("file", name=_file_name, encoding="utf-8") for _file_name in fetch_lut.keys()
                ]
            )
            result = contact_server(request, icswServiceEnum.cluster_server, srv_com, timeout=60, connection_id="file_fetch_{}".format(str(job_id)))
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
                                new_text = ""
                                while len(new_text) < magic_limit and last_lines:
                                    new_text = last_lines.pop() + "\n" + new_text

                                cut_marker = "\n\n[cut off output since file is too large ({} > {})]\n\n".format(
                                    logging_tools.get_size_str(len(text)),
                                    logging_tools.get_size_str(magic_limit),
                                )
                                text = "\n".join(first_lines) + cut_marker + new_text

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
        contact_server(request, icswServiceEnum.rms_server, srv_com, timeout=10)
