# Copyright (C) 2013,2015 Andreas Lang-Nevyjel, init.at
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

# import pprint
from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools, process_tools, server_command

try:
    import memcache
except ImportError:
    memcache = None


class _general(hm_classes.hm_module):
    pass


class memcached_status_command(hm_classes.hm_command):
    def __init__(self, name):
        super(memcached_status_command, self).__init__(name, positional_arguments=True)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)

    def __call__(self, srv_com, cur_ns):
        if memcache:
            if cur_ns.arguments:
                target_servers = cur_ns.arguments
            else:
                target_servers = ["localhost:11211"]
            cur_c = memcache.Client(target_servers)
            try:
                mc_stats = cur_c.get_stats()
            except:
                srv_com.set_result("cannot get stats: {}".format(process_tools.get_except_info()), server_command.SRV_REPLY_STATE_ERROR)
            else:
                if mc_stats:
                    srv_com["memcache_stats"] = mc_stats
                else:
                    srv_com.set_result("no stats from {}".format(", ".join(target_servers)), server_command.SRV_REPLY_STATE_ERROR)
        else:
            srv_com.set_result("no memcached module found", server_command.SRV_REPLY_STATE_ERROR)

    def interpret(self, srv_com, cur_ns):
        if "memcache_stats" in srv_com:
            mc_stats = srv_com["*memcache_stats"]
            ret_state = limits.nag_STATE_OK
            out_f = []
            for t_srv, cur_stats in mc_stats:
                # pprint.pprint(mc_stats)
                used_bytes, max_bytes = (
                    int(cur_stats["bytes"]),
                    int(cur_stats["limit_maxbytes"]),
                )
                cur_perc = used_bytes * 100. / max_bytes
                out_f.append(
                    "{}: {} of {} used ({:.2f} %)".format(
                        t_srv.strip(),
                        logging_tools.get_size_str(used_bytes),
                        logging_tools.get_size_str(max_bytes),
                        cur_perc,
                    )
                )
                ret_state = max(ret_state, limits.check_ceiling(cur_perc, cur_ns.warn, cur_ns.crit))
            return ret_state, ", ".join(out_f)
        else:
            return limits.nag_STATE_CRITICAL, "no stats found"
