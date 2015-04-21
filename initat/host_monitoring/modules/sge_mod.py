# Copyright (C) 2013-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

from initat.host_monitoring import limits, hm_classes
from lxml import etree  # @UnresolvedImport
import commands
import os
from initat.tools import process_tools
from initat.tools import server_command


class _general(hm_classes.hm_module):
    def init_module(self):
        sge_dict = {}
        for v_name, v_src in [
            ("SGE_ROOT", "/etc/sge_root"),
            ("SGE_CELL", "/etc/sge_cell")
        ]:
            if os.path.isfile(v_src):
                sge_dict[v_name] = file(v_src, "r").read().strip()
                os.environ[v_name] = sge_dict[v_name]
        if set(sge_dict.keys()) == set(["SGE_ROOT", "SGE_CELL"]):
            sge_dict["SGE_ARCH"] = commands.getoutput(os.path.join(sge_dict["SGE_ROOT"], "util", "arch")).strip()
        self.sge_dict = sge_dict


class sge_queue_status_command(hm_classes.hm_command):
    def __init__(self, name):
        super(sge_queue_status_command, self).__init__(name)
        self.parser.add_argument("--sge-queue", dest="sge_queue", type=str)
        self.parser.add_argument("--sge-host", dest="sge_host", type=str)

    def __call__(self, srv_com, cur_ns):
        sge_dict = self.module.sge_dict
        if not cur_ns.sge_host:
            srv_com.set_result("need queue and host value", server_command.SRV_REPLY_STATE_ERROR)
        else:
            cur_stat, cur_out = commands.getstatusoutput(
                os.path.join(
                    sge_dict["SGE_ROOT"], "bin", sge_dict["SGE_ARCH"], "qhost -q -xml"
                )
            )
            if cur_stat:
                srv_com.set_result("error getting qhost info (%d): %s" % (
                    cur_stat,
                    cur_out), server_command.SRV_REPLY_STATE_ERROR)
            else:
                try:
                    cur_xml = etree.fromstring(cur_out)  # @UndefinedVariable
                except:
                    srv_com.set_result("error building xml: %s" % (process_tools.get_except_info()), server_command.SRV_REPLY_STATE_ERROR)
                else:
                    q_el = cur_xml.xpath(".//host[@name='%s']" % (cur_ns.sge_host), smart_strings=False)
                    if not q_el and not cur_ns.sge_host.count("."):
                        # try with short name if no FQDN is given
                        q_el = cur_xml.xpath(".//host[starts-with(@name, '%s.')]" % (cur_ns.sge_host), smart_strings=False)
                        if not q_el:
                            # last try, only with short name
                            q_el = cur_xml.xpath(".//host[@name='%s')]" % (cur_ns.sge_host), smart_strings=False)
                    if q_el:
                        q_el = q_el[0]
                        q_el.attrib["sge_host"] = cur_ns.sge_host
                        if cur_ns.sge_queue:
                            q_el.attrib["sge_queue"] = cur_ns.sge_queue
                        srv_com["queue_result"] = q_el
                    else:
                        srv_com.set_result("no host/queue element found for '%s'/'%s'" % (
                            cur_ns.sge_host,
                            cur_ns.sge_queue), server_command.SRV_REPLY_STATE_ERROR)
        return

    def interpret(self, srv_com, cur_ns):
        if "queue_result" in srv_com:
            q_host = srv_com["queue_result"][0]
            q_name = q_host.get("sge_queue", "")
            q_list = [q_name] if q_name else q_host.xpath(".//queue/@name", smart_strings=False)
            host_name = q_host.attrib["name"]
            ret_state, out_f = (
                limits.nag_STATE_OK,
                []
            )
            # iterate over all queues
            for s_queue in q_host.findall("queue"):
                queue_name = s_queue.attrib["name"]
                if queue_name in q_list:
                    qv_dict = dict([(cur_el.attrib["name"], cur_el.text or "") for cur_el in s_queue])
                    for cur_c in qv_dict["state_string"]:
                        ret_state = max(ret_state, {
                            "u": limits.nag_STATE_CRITICAL,
                            "a": limits.nag_STATE_CRITICAL,
                            "A": limits.nag_STATE_CRITICAL,
                            "C": limits.nag_STATE_OK,
                            "s": limits.nag_STATE_OK,
                            "S": limits.nag_STATE_OK,
                            "d": limits.nag_STATE_WARNING,
                            "D": limits.nag_STATE_WARNING,
                            "E": limits.nag_STATE_CRITICAL,
                        }[cur_c])
                    out_f.append(
                        "queue %s@%s, %d of %d used, state is %s" % (
                            queue_name,
                            host_name,
                            int(qv_dict["slots_used"]),
                            int(qv_dict["slots"]),
                            qv_dict["state_string"] or "ok"
                        )
                    )
            if not out_f:
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
            return ret_state, "; ".join(out_f) or "no Queues found"
        else:
            return limits.nag_STATE_CRITICAL, "no stats found"
