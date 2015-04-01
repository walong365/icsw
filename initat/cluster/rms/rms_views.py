# rms views

from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from initat.cluster.backbone.models import user_variable
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.render import render_me
from initat.cluster.backbone.models import device
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper, \
    update_session_object
from initat.cluster.rms.rms_addons import *
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
    return sge_tools.get_empty_job_options(compress_nodelist=False)

def get_node_options(request):
    return sge_tools.get_empty_node_options(merge_node_queue=True)

class overview(View):
    @method_decorator(login_required)
    def get(self, request):
        res = _rms_headers(request)
        if sge_tools is not None:
            for change_obj in RMS_ADDONS:
                change_obj.modify_headers(res)
        header_dict = {}
        for _entry in res:
            _sub_list = header_dict.setdefault(_entry.tag, [])
            for _header in _entry[0]:
                _sub_list.append(_header.tag)
        return render_me(request, "rms_overview.html", {
            "RMS_HEADERS" : json.dumps(header_dict)
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
    # interpret nodes according to optional type attribute, TODO: use format from attrib to reformat later
    in_list = [[_node_to_value(sub_node) for sub_node in row] for row in in_list]
    # reformat
    show_list = [[_value_to_str(value) for value in line] for line in in_list]
    # print show_list
    return show_list

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
        for file_el in my_sge_info.get_tree().xpath(".//job_list[master/text() = \"MASTER\"]", smart_strings=False):
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

class get_node_info(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        _dev_names = json.loads(_post["devnames"])
        dev_list = device.objects.filter(Q(name__in=_dev_names))
        json_resp = {_entry.name : (_entry.idx, _entry.has_active_rrds) for _entry in dev_list}
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

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
            srv_com.builder("job", job_id=job_id))
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
                file_parts = file_id.split(".")
                std_type = file_parts[2]
                job_id = "%s.%s" % (file_parts[0], file_parts[1]) if file_parts[1] else file_parts[0]
                file_id_list.append((file_id, job_id, std_type))
        elif _post["file_id"].count(":"):
            file_parts = _post["file_id"].split(":")
            std_type = file_parts[1]
            job_id = file_parts[2]
            file_id_list = [(_post["file_id"], job_id, std_type)]
        else:
            file_parts = _post["file_id"].split(".")
            std_type = file_parts[2]
            job_id = "%s.%s" % (file_parts[0], file_parts[1])
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
                io_element = job_info.find(".//%s" % (std_type))
                if io_element is None or io_element.get("error", "0") == "1":
                    request.xml_response.error("%s not defined for job %s" % (std_type, job_id), logger)
                else:
                    fetch_lut[io_element.text] = src_id
        # print "*", job_id, job_info
        if fetch_lut:
            _resp_list = []
            # print etree.tostring(job_info)
            srv_com = server_command.srv_command(command="get_file_content")
            srv_com["file_list"] = srv_com.builder(
                "file_list",
                *[srv_com.builder("file", name=_file_name) for _file_name in fetch_lut.iterkeys()]
                )
            result = contact_server(request, "server", srv_com, timeout=60, connection_id="file_fetch_%s" % (str(job_id)))
            if result is not None:
                for cur_file in result.xpath(".//ns:file", smart_strings=False):
                    # print etree.tostring(cur_file)
                    if cur_file.attrib.get("error", "1") == "1":
                        request.xml_response.error("error reading %s (job %s): %s" % (
                            cur_file.attrib["name"],
                            job_id,
                            cur_file.attrib["error_str"]), logger)
                    else:
                        _resp_list.append(
                            E.file_info(
                                cur_file.text or "",
                                id=fetch_lut[cur_file.attrib["name"]],
                                name=cur_file.attrib["name"],
                                lines=cur_file.attrib["lines"],
                                size_str=logging_tools.get_size_str(int(cur_file.attrib["size"]), True),
                            )
                        )
            if len(_resp_list):
                request.xml_response["response"] = _resp_list
        else:
            request.xml_response.error("nothing found for %s" % (logging_tools.get_plural("job", len(file_id_list))), logger) # %s not found for job %s" % (std_type, job_id), logger)

class set_user_setting(View):
    @method_decorator(login_required)
    def post(self, request):
        if "user_vars" not in request.session:
            request.session["user_vars"] = {}
        user_vars = request.session["user_vars"]
        _post = request.POST
        data = json.loads(_post["data"])
        var_name = "_rms_wf_%s" % (data["table"])
        if var_name in user_vars:
            cur_dis = user_vars[var_name].value.split(",")
        else:
            cur_dis = []
        row = data["row"]
        _save = False
        if data["enabled"] and row in cur_dis:
            cur_dis.remove(row)
            _save = True
        elif not data["enabled"] and row not in cur_dis:
            cur_dis.append(row)
            _save = True
        if _save:
            try:
                user_vars[var_name] = user_variable.objects.get(Q(name=var_name) & Q(user=request.user))
            except user_variable.DoesNotExist:
                user_vars[var_name] = user_variable.objects.create(
                    user=request.user,
                    name=var_name,
                    value=",".join(cur_dis)
                )
            else:
                user_vars[var_name].value = ",".join(cur_dis)
                user_vars[var_name].save()
            update_session_object(request)
            request.session.save()
        json_resp = {}
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

class get_user_setting(View):
    @method_decorator(login_required)
    def post(self, request):
        user_vars = request.session.get("user_vars", {})
        json_resp = {}
        for t_name in ["running", "waiting", "node"]:
            var_name = "_rms_wf_%s" % (t_name)
            if var_name in user_vars:
                json_resp[t_name] = user_vars[var_name].value.split(",")
            else:
                json_resp[t_name] = []
        return HttpResponse(json.dumps(json_resp), mimetype="application/json")

