# rms views

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.rms.rms_addons import *
from initat.core.render import render_me
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import json
import logging
import logging_tools
import pprint
import server_command
import sys
import threading
import time
try:
    import sge_tools
except ImportError:
    sge_tools = None

RMS_ADDON_KEYS = [key for key in sys.modules.keys() if key.startswith("initat.cluster.rms.rms_addons.") and sys.modules[key]]
RMS_ADDONS = [sys.modules[key].modify_rms() for key in RMS_ADDON_KEYS]

logger = logging.getLogger("cluster.rms")

if sge_tools:
    class tl_sge_info(sge_tools.sge_info):
        # sge_info object with thread lock layer
        def __init__(self):
            self.lock = threading.Lock()
            sge_tools.sge_info.__init__(
                self,
                server="127.0.0.1",
                default_pref=["server"],
                never_direct=True,
                run_initial_update=False,
                verbose=settings.DEBUG
            )
        def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
            logger.log(log_level, "[sge] %s" % (what))
        def update(self):
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

my_sge_info = tl_sge_info()

def get_job_options(request):
    return sge_tools.get_empty_job_options()

def get_node_options(request):
    return sge_tools.get_empty_node_options(merge_node_queue=True)

class overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "rms_overview.html", {
        })()

def _rms_headers(request):
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
            )
        )
    else:
        res = E.headers()
    return res

class get_header_xml(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        res = _rms_headers(request)
        if sge_tools is not None:
            for change_obj in RMS_ADDONS:
                change_obj.modify_headers(res)
        request.xml_response["headers"] = res

def _node_to_value(in_node):
    if in_node.get("type", "string") == "float":
        return float(in_node.text)
    else:
        return in_node.text

def _value_to_str(in_value):
    if type(in_value) == float:
        return "%.2f" % (in_value)
    else:
        return in_value

def _sort_list(in_list, _post):
    # for key in sorted(_post):
    #    print key, _post[key]
    start_idx = int(_post.get("iDisplayStart", "0"))
    num_disp = int(_post.get("iDisplayLength", "10000"))
    total_data_len = len(in_list)
    # interpet nodes according to optional type attribute, TODO: use format from attrib to reformat later
    in_list = [[_node_to_value(sub_node) for sub_node in row] for row in in_list]
    s_str = _post.get("sSearch", "").strip()
    if s_str:
        in_list = [row for row in in_list if any([str(cur_text).count(s_str) for cur_text in row])]
    filter_data_len = len(in_list)
    for sort_key in [key for key in _post.keys() if key.startswith("sSortDir_")]:
        sort_dir = _post[sort_key]
        sort_idx = int(_post["iSortCol_%s" % (sort_key.split("_")[-1])])
        if sort_dir == "asc":
            in_list = sorted(in_list, cmp=lambda x, y: cmp(x[sort_idx], y[sort_idx]))
        else:
            in_list = sorted(in_list, cmp=lambda x, y: cmp(y[sort_idx], x[sort_idx]))
    # reformat
    show_list = [[_value_to_str(value) for value in line] for line in in_list[start_idx : start_idx + num_disp]]
    # print show_list
    return {"sEcho"                : int(_post.get("sEcho", "28")),
            "iTotalRecords"        : total_data_len,
            "iTotalDisplayRecords" : filter_data_len,
            "aaData"               : show_list}

class get_rms_json(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info.update()
        run_job_list = sge_tools.build_running_list(my_sge_info, get_job_options(request), user=request.user)

        # print etree.tostring(run_job_list, pretty_print=True)
        wait_job_list = sge_tools.build_waiting_list(my_sge_info, get_job_options(request), user=request.user)
        node_list = sge_tools.build_node_list(my_sge_info, get_node_options(request))
        if RMS_ADDONS:
            for change_obj in RMS_ADDONS:
                change_obj.set_headers(_rms_headers(request))
                change_obj.modify_running_jobs(my_sge_info, run_job_list)
                change_obj.modify_waiting_jobs(my_sge_info, wait_job_list)
                change_obj.modify_nodes(my_sge_info, node_list)
        fc_dict = {}
        cur_time = time.time()
        for file_el in my_sge_info.get_tree().xpath(".//job_list[master/text() = \"MASTER\"]"):
            file_contents = file_el.findall(".//file_content")
            if len(file_contents):
                cur_fcd = []
                for cur_fc in file_contents:
                    file_name = cur_fc.attrib["name"]
                    lines = cur_fc.text.replace(r"\r\n", r"\n").split("\n")
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
        json_resp = {
            "run_table"  : _sort_list(run_job_list, _post),
            "wait_table" : _sort_list(wait_job_list, _post),
            "node_table" : _sort_list(node_list, _post),
            "files"      : fc_dict,
        }
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

class get_run_jobs_xml(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info.update()
        run_job_list = sge_tools.build_running_list(my_sge_info, get_job_options(request), user=request.user)
        json_resp = _sort_list(run_job_list, _post)
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

class get_wait_jobs_xml(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info.update()
        wait_job_list = sge_tools.build_waiting_list(my_sge_info, get_job_options(request), user=request.user)
        json_resp = _sort_list(wait_job_list, _post)
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

class get_node_xml(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        my_sge_info.update()
        node_list = sge_tools.build_node_list(my_sge_info, get_node_options(request))
        json_resp = _sort_list(node_list, _post)
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

class control_job(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_id = _post["control_id"]
        c_action = c_id.split(":")[1]
        job_id = ".".join([entry for entry in c_id.split(":")[2:] if entry.strip()])
        srv_com = server_command.srv_command(command="job_control", action=c_action)
        srv_com["job_list"] = srv_com.builder(
            "job_list",
            srv_com.builder("job", job_id=job_id))
        contact_server(request, "tcp://localhost:8009", srv_com, timeout=10)

class get_file_content(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        file_parts = _post["file_id"].split(":")
        std_type = file_parts[1]
        job_id = file_parts[2]
        # my_sge_info.update()
        job_info = my_sge_info.get_job(job_id)
        if job_info is None:
            my_sge_info.update()
            job_info = my_sge_info.get_job(job_id)
        # print "*", job_id, job_info
        if job_info is not None:
            # print etree.tostring(job_info)
            io_element = job_info.find(".//%s" % (std_type))
            if io_element is None or io_element.get("error", "0") == "1":
                request.xml_response.error("%s not defined for job %s" % (std_type, job_id), logger)
            else:
                srv_com = server_command.srv_command(command="get_file_content")
                srv_com["file_list"] = srv_com.builder(
                    "file_list",
                    srv_com.builder("file", name=io_element.text),
                    )
                result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=60, connection_id="file_fetch_%s" % (str(job_id)))
                for cur_file in result.xpath(".//ns:file"):
                    # print etree.tostring(cur_file)
                    if cur_file.attrib["error"] == "1":
                        request.xml_response.error("error reading %s (job %s): %s" % (
                            cur_file.attrib["name"],
                            job_id,
                            cur_file.attrib["error_str"]), logger)
                    else:
                        file_resp = E.file_info(
                            cur_file.text or "",
                            name=cur_file.attrib["name"],
                            lines=cur_file.attrib["lines"],
                            size_str=logging_tools.get_size_str(int(cur_file.attrib["size"]), True),
                        )
                        request.xml_response["response"] = file_resp
        else:
            request.xml_response.error("%s not found for job %s" % (std_type, job_id), logger)
