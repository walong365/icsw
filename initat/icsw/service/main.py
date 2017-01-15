#
# Copyright (C) 2001-2009,2011-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" checks installed servers on system """

import datetime
import os
import sys
import time

from initat.debug import ICSW_DEBUG_MODE
from initat.tools import logging_tools
from . import container
from . import instance
from . import transition
from .constants import STATE_DICT, LIC_STATE_DICT, CONF_STATE_DICT
from .tools import query_local_meta_server
from .. import icsw_logging


def show_form_list(form_list, run_time):
    # color strings (green / blue / red / normal)
    d_map = {
        "ok": "\033[1;32m{}\033[m\017",
        "warning": "\033[1;34m{}\033[m\017",
        "critical": "\033[1;31m{}\033[m\017",
    }
    print(
        "{} (took {})".format(
            datetime.datetime.now().strftime("%a, %d. %b %Y %d %H:%M:%S"),
            logging_tools.get_diff_time_str(run_time),
        )
    )
    form_list.display_attribute_map = d_map
    print(str(form_list))


def _state_overview(opt_ns, result):
    _instances = result.xpath(".//ns:instances/ns:instance")
    print("instances reported: {}".format(logging_tools.get_plural("instance", len(_instances))))
    for _inst in _instances:
        _states = []
        last_states = None
        for _src_state in result.xpath(".//ns:state", start_el=_inst):
            # todo: remove duplicates
            _states.append(_src_state)
        _actions = result.xpath(".//ns:action", start_el=_inst)
        print(
            "{:<30s}, target state is {:<20s} [{}, {}], {} / {} in the last {}".format(
                _inst.get("name"),
                {
                    0: "stopped",
                    1: "started"
                }[int(_inst.attrib["target_state"])],
                "active" if int(_inst.attrib["active"]) else "inactive",
                "ignored" if int(_inst.attrib["ignore"]) else "watched",
                logging_tools.get_plural("state", len(_states)),
                logging_tools.get_plural("action", len(_actions)),
                logging_tools.get_diff_time_str(24 * 3600 * int(result.get("days_to_consider", "1"))),
            )
        )
        _out_list = []
        if opt_ns.state:
            _out_list.extend(
                [
                    {
                        "ts": int(_el.attrib["created"]),
                        "type": "state",
                        "struct": _el,
                    } for _el in _states
                ]
            )
        if opt_ns.action:
            _out_list.extend(
                [
                    {
                        "ts": int(_el.attrib["created"]),
                        "type": "action",
                        "struct": _el,
                    } for _el in _actions
                ]
            )
        if _out_list:
            if opt_ns.merge:
                _out_list.sort(cmp=lambda x, y: x["ts"] - y["ts"], reverse=True)
            for _list_el in _out_list:
                _el = _list_el["struct"]
                if _list_el["type"] == "state":
                    print(
                        "    {} pstate={}, cstate={}, license_state={} [{}]".format(
                            time.ctime(int(_el.attrib["created"])),
                            STATE_DICT[int(_el.attrib["pstate"])],
                            CONF_STATE_DICT[int(_el.attrib["cstate"])],
                            LIC_STATE_DICT[int(_el.attrib["license_state"])],
                            _el.attrib["proc_info_str"],
                        )
                    )
                else:
                    print(
                        "    {} action={}, runtime={} [{} / {}]".format(
                            time.ctime(int(_el.attrib["created"])),
                            _el.attrib["action"],
                            _el.attrib["runtime"],
                            _el.attrib["finished"],
                            _el.attrib["success"],
                        )
                    )


def version_command(opt_ns):
    from initat.cluster.backbone.models import ICSWVersion, VERSION_NAME_LIST
    from django.conf import settings
    print("ICSW Version info")
    _vers = {
        "db": ICSWVersion.get_latest_db_dict(),
        "sys": settings.ICSW_VERSION_DICT,
    }
    for _key in sorted(_vers.keys()):
        if _vers[_key]:
            for _vn in VERSION_NAME_LIST:
                print(
                    "  {:<3} {:<10}: {}".format(
                        _key,
                        _vn,
                        _vers[_key][_vn],
                    )
                )
        else:
            print(
                "* {:<3} {:<10}: missing".format(
                    _key,
                    "",
                )
            )


def main(opt_ns):
    log_com = icsw_logging.get_logger("service", opt_ns, all=True if opt_ns.childcom in ["state"] else False)
    if os.getuid():
        log_com("Not running as root, information may be incomplete, disabling display of memory", logging_tools.LOG_LEVEL_ERROR)
        opt_ns.memory = False
    inst_xml = instance.InstanceXML(log_com)
    cur_c = container.ServiceContainer(log_com)
    META_COMS = ["disable", "enable", "ignore", "monitor", "overview"]
    if opt_ns.childcom == "version":
        version_command(opt_ns)
    elif opt_ns.childcom == "status":
        if opt_ns.interactive:
            from . import console
            console.main(opt_ns, cur_c, inst_xml)
        else:
            cur_c.check_system(opt_ns, inst_xml)
            if ICSW_DEBUG_MODE:
                from django.db import connection
                _time = 0.0
                for line in connection.queries:
                    print("{} : {}".format(line["time"], line["sql"]))
                    _time += float(line["time"])
                print()
                print("performed {:d} queries in {:.3f}".format(len(connection.queries), _time))
                print()
            form_list = cur_c.instance_to_form_list(opt_ns, inst_xml.tree)
            start_time, end_time = (
                float(inst_xml.tree.attrib["start_time"]),
                float(inst_xml.tree.attrib["end_time"])
            )
            run_time = end_time - start_time
            show_form_list(form_list, run_time)
            _res = inst_xml.tree.findall(".//result")
            if len(_res) == 1:
                # set return state to single-state result
                _state = int(_res[0].find("process_state_info").get("state"))
                sys.exit(_state)
    elif opt_ns.childcom in ["start", "stop", "restart", "debug", "reload"]:
        if opt_ns.childcom == "debug":
            debug_args = opt_ns.debug_args
            if opt_ns.debug_flag:
                debug_args.append("--debug-flag")
        else:
            debug_args = None
        cur_t = transition.ServiceTransition(
            opt_ns.childcom,
            opt_ns.service,
            cur_c,
            inst_xml,
            log_com,
            debug_args=debug_args,
        )
        while True:
            _left = cur_t.step(cur_c)
            if _left:
                time.sleep(1)
            else:
                break
    elif opt_ns.childcom in META_COMS:
        # check wether the meta-server is running
        opt_ns.meta = True
        orig_service = opt_ns.service  # save the "service" argument
        opt_ns.service = ['meta-server']
        cur_c.check_system(opt_ns, inst_xml)
        opt_ns.service = orig_service
        meta_server_instance = inst_xml.tree.xpath(
            "/instances/instance[@name='meta-server']"
        )[0]
        meta_server_state = meta_server_instance.xpath(
            "result/process_state_info/@state"
        )
        if not meta_server_state or int(meta_server_state[0]):
            print("Warning: meta-server is not running")

        # contact meta-server at localhost
        _result = query_local_meta_server(
            inst_xml,
            opt_ns.childcom,
            services=opt_ns.service,
            days_to_consider=opt_ns.days if opt_ns.childcom in ["overview"] else 1,
            db_limit=opt_ns.db_limit if opt_ns.childcom in ["overview"] else 100,
        )
        if _result is None:
            log_com("Got no result from meta-server")
            sys.exit(1)
        elif _result.get_log_tuple()[1] > logging_tools.LOG_LEVEL_WARN:
            log_com(*_result.get_log_tuple())
        else:
            if opt_ns.childcom == "overview":
                _state_overview(opt_ns, _result)
            elif opt_ns.childcom in ["disable", "enable", "ignore", "monitor"]:
                log_com(*_result.get_log_tuple())
    else:
        log_com(
            "unknown childcom '{}'".format(
                opt_ns.childcom
            ),
            logging_tools.LOG_LEVEL_ERROR
        )
