#!usr/bin/python -Ot
#
# Copyright (C) 2007,2012,2013 Andreas Lang-Nevyjel
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
""" rebuilds the hopcount-table, needs some rewrite ... """

import sys
import cs_base_class
import logging_tools
import time
import datetime
import pytz
import pprint
import codecs
import server_command
from django.db.models import Q
from django.conf import settings
from initat.cluster.backbone.models import net_ip, netdevice, device, device_variable, device_group, \
     peer_information, cs_timer, route_generation
from initat.cluster_server.config import global_config
from config_tools import router_object

HOPCOUNT_REBUILT_VAR_NAME = "hopcount_table_build_time"
HOPCOUNT_STATE_VAR_NAME = "hopcount_state_var"

class path_object(object):
    def __init__(self, s_nd, d_nd):
        self.s_nd, self.d_nd = (s_nd, d_nd)
        self.pathes = []
    def feed_path(self, p_list):
        self.pathes.append(p_list)
    def __nonzero__(self):
        return True if self.pathes else False
    def __repr__(self):
        return unicode(self)
    def __unicode__(self):
        return "%d - %d (%d)" % (self.s_nd, self.d_nd, len(self.pathes))
    def generate_hopcounts(self, rho):
        new_hcs = sum([self._generate_hc(cur_p, rho) for cur_p in self.pathes], [])
        return new_hcs
    def _generate_hc(self, cur_p, rho):
        cur_trace = ["%d" % (rho.nd_dict[cur_hop].device_id) for cur_hop in cur_p]
        new_hc = hopcount(
            route_generation=rho.cur_gen,
            s_netdevice=rho.nd_dict[self.s_nd],
            d_netdevice=rho.nd_dict[self.d_nd],
            value=sum([rho.nd_dict[cur_hop].penalty for cur_hop in cur_p]) + sum([rho.peer_dict[(cur_p[idx], cur_p[idx + 1])] for idx in xrange(0, len(cur_p) - 1)]),
            trace=":".join(cur_trace),
            trace_length=len(cur_trace),
        )
        hc_list = [new_hc]
        # also add reverted version
        hc_list.append(
            hopcount(
                route_generation=rho.cur_gen,
                s_netdevice=rho.nd_dict[self.d_nd],
                d_netdevice=rho.nd_dict[self.s_nd],
                value=new_hc.value,
                trace=":".join([val for val in cur_trace[::-1]]),
                trace_length=len(cur_trace),
            )
        )
        rho.dups += 1
        visited = set([(self.s_nd, self.d_nd)])
        hc_list.extend(self._expand_pruned(new_hc, cur_trace, rho, visited))
        #print "-" * 20
        #pprint.pprint(pruned_dict)
        #pprint.pprint(hc_list)
        #print visited
##        if len(hc_list) > 10:
##            sys.exit(0)
        return hc_list
    def _expand_pruned(self, src_hc, src_trace, rho, visited):
        r_list = []
        for new_left in rho.pruned_dict.get(src_hc.s_netdevice_id, []):
            # expand left
            if (new_left, src_hc.d_netdevice_id) not in visited and src_trace[0] != src_trace[-1]:
                visited.add((new_left, src_hc.d_netdevice_id))
                add_penalty = rho.peer_dict[(new_left, src_hc.s_netdevice_id)] + rho.nd_dict[new_left].penalty
                cur_trace = ["%d" % (rho.nd_dict[new_left].device_id)] + src_trace
                new_hc = hopcount(
                    route_generation=rho.cur_gen,
                    s_netdevice=rho.nd_dict[new_left],
                    d_netdevice=rho.nd_dict[src_hc.d_netdevice_id],
                    value=src_hc.value + add_penalty,
                    trace=":".join(cur_trace),
                    trace_length=len(cur_trace),
                )
                r_list.append(new_hc)
                if new_hc.s_netdevice_id != new_hc.d_netdevice_id:
                    rho.dups += 1
                    r_list.append(
                        hopcount(
                            route_generation=rho.cur_gen,
                            s_netdevice=rho.nd_dict[src_hc.d_netdevice_id],
                            d_netdevice=rho.nd_dict[new_left],
                            value=new_hc.value,
                            trace=":".join([val for val in cur_trace[::-1]]),
                            trace_length=len(cur_trace),
                        )
                    )
                    cur_trace.reverse()
                r_list.extend(self._expand_pruned(
                    new_hc, src_trace, rho, visited)
                              )
        for new_right in rho.pruned_dict.get(src_hc.d_netdevice_id, []):
            # expand right
            if (src_hc.s_netdevice_id, new_right) not in visited and src_trace[0] != src_trace[-1]:
                visited.add((src_hc.s_netdevice_id, new_right))
                add_penalty = rho.peer_dict[(new_right, src_hc.d_netdevice_id)] + rho.nd_dict[new_right].penalty
                cur_trace = src_trace + ["%d" % (rho.nd_dict[new_right].device_id)]
                new_hc = hopcount(
                    route_generation=rho.cur_gen,
                    s_netdevice=rho.nd_dict[src_hc.s_netdevice_id],
                    d_netdevice=rho.nd_dict[new_right],
                    value=src_hc.value + add_penalty,
                    trace=":".join(cur_trace),
                    trace_length=len(cur_trace),
                )
                r_list.append(new_hc)
                if new_hc.s_netdevice_id != new_hc.d_netdevice_id:
                    rho.dups += 1
                    r_list.append(
                        hopcount(
                            route_generation=rho.cur_gen,
                            s_netdevice=rho.nd_dict[new_right],
                            d_netdevice=rho.nd_dict[src_hc.s_netdevice_id],
                            value=new_hc.value,
                            trace=":".join([val for val in cur_trace[::-1]]),
                            trace_length=len(cur_trace),
                        )
                    )
                    cur_trace.reverse()
                r_list.extend(self._expand_pruned(
                    new_hc, src_trace, rho, visited)
                              )
        return r_list

class route_helper_obj(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init router helper object")
        self.__start_time = time.time()
        self.all_nds = netdevice.objects.exclude(Q(device__device_type__identifier="MD")).select_related("device__device_type")
        self.all_peers = peer_information.objects.all()
        self.nd_dict = dict([(cur_nd.pk, cur_nd) for cur_nd in self.all_nds])
        # peer dict
        self.peer_dict = {}
        for cur_p in self.all_peers:
            self.peer_dict[(cur_p.s_netdevice_id, cur_p.d_netdevice_id)] = cur_p.penalty
            self.peer_dict[(cur_p.d_netdevice_id, cur_p.s_netdevice_id)] = cur_p.penalty
        self.pruned_dict = {}
        self.dups = 0
        try:
            self.last_gen = route_generation.objects.get(Q(valid=True))
        except route_generation.DoesNotExist:
            self.last_gen = None
        self.cur_gen = route_generation(
            generation=self.last_gen.generation + 1 if self.last_gen else 1,
            valid=False,
            build=True,
        )
        self.cur_gen.save()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[rho] %s" % (what), log_level)
    def switch(self, num_hops, num_dups):
        self.__end_time = time.time()
        # switches from last_gen to cur_gen
        self.cur_gen.time_used = self.__end_time - self.__start_time
        self.cur_gen.build = False
        self.cur_gen.valid = True
        # statistic values
        self.cur_gen.num_hops = num_hops
        self.cur_gen.num_dups = num_dups
        self.log("enabled new route_generation (%s)" % (unicode(self.cur_gen)))
        self.cur_gen.save()
        for prev_gen in route_generation.objects.exclude(pk=self.cur_gen.pk).filter(Q(valid=True)):
            prev_gen.valid = False
            prev_gen.save()
        # delete all hopcounts with no route generation
        hopcount.objects.filter(Q(route_generation=None)).delete()
        # delete routing sets which are at least 10 geneartions behind
        old_gens = route_generation.objects.filter(Q(generation__lt=self.cur_gen.generation - 10))
        if old_gens:
            self.log("deleting %s" % (logging_tools.get_plural("old generation", len(old_gens))))
            old_gens.delete()
    def create_hopcount(self, nd_list):
        penalty = sum([self.nd_dict[nd_list[idx]].penalty + self.peer_dict[(nd_list[idx], nd_list[idx + 1])] for idx in xrange(len(nd_list) - 1)], 0) + self.nd_dict[nd_list[-1]].penalty
        ret_list = [
            hopcount(
                route_generation=self.cur_gen,
                s_netdevice=self.nd_dict[nd_list[0]],
                d_netdevice=self.nd_dict[nd_list[-1]],
                value=penalty,
                trace=":".join(["%d" % (self.nd_dict[cur_nd].device_id) for cur_nd in nd_list]),
                trace_length=len(nd_list),
            )
        ]
        if len(nd_list) > 1:
            self.dups += 1
            ret_list.append(
                hopcount(
                    route_generation=self.cur_gen,
                    s_netdevice=self.nd_dict[nd_list[-1]],
                    d_netdevice=self.nd_dict[nd_list[0]],
                    value=penalty,
                    trace=":".join(["%d" % (self.nd_dict[cur_nd].device_id) for cur_nd in nd_list[::-1]]),
                    trace_length=len(nd_list),
                )
            )
        return ret_list
        
class rebuild_hopcount(cs_base_class.server_com):
    class Meta:
        blocking = True
        needed_configs = ["rebuild_hopcount"]
        background = True
        disabled = True
    def _new_code(self, cur_inst):
        rho = route_helper_obj(cur_inst.log)
        my_timer = cs_timer()
        cur_inst.log("building routing info for %s and %s" % (
            logging_tools.get_plural("netdevice", len(rho.all_nds)),
            logging_tools.get_plural("peer information", len(rho.all_peers))))
        pure_peers = [(cur_p.s_netdevice_id, cur_p.d_netdevice_id) for cur_p in rho.all_peers]
        # dot part
        if True:
            dot_file = codecs.open("/tmp/r.dot", "w", "utf-8")
            dot_file.write("graph routing {\n")
            # build neighbour dict
            nb_dict = {}
            for nd_pk, cur_nd in rho.nd_dict.iteritems():
                label = "%s (%d, [%s:%d], p: %d)" % (
                    cur_nd.devname,
                    nd_pk,
                    unicode(cur_nd.device),
                    cur_nd.device_id,
                    cur_nd.penalty)
                dot_file.write(u"n_%d %s;\n" % (
                    nd_pk,
                    u"[shape=%s, label=\"%s\"]" % (
                        "circle " if cur_nd.routing else "box",
                        label),
                )
                               )
            for cur_p in pure_peers:
                nb_dict.setdefault(cur_p[0], set()).add(cur_p[1])
                nb_dict.setdefault(cur_p[1], set()).add(cur_p[0])
                dot_file.write("n_%d -- n_%d;\n" % (cur_p[0], cur_p[1]))
            dot_file.write("}\n")
            dot_file.close()
        nd_pks = set(rho.nd_dict.keys())
        #print nd_pks
        #print pure_peers
        pruned_pks = set()
        # first step: prune the tree
        for prune_step in xrange(256):
            #break
            cur_inst.log("prune step %d" % (prune_step))
            rem_nds = set()
            if len(nd_pks) > 2:
                for cur_nd in nd_pks:
                    # check for non-routing netdevices
                    if len(nb_dict.get(cur_nd, set())) < 2 and not rho.nd_dict[cur_nd].routing:
                        # remove netdevice (no or only one connection)
                        if cur_nd in nb_dict:
                            for nb_pk in nb_dict[cur_nd]:
                                nb_dict[nb_pk].remove(cur_nd)
                                rho.pruned_dict.setdefault(nb_pk, []).append(cur_nd)
                            del nb_dict[cur_nd]
                        rem_nds.add(cur_nd)
                if rem_nds:
                    pruned_pks |= rem_nds
                    nd_pks -= rem_nds
                    cur_inst.log("removing %s (%s) while pruning" % (
                        logging_tools.get_plural("netdevice", len(rem_nds)),
                        ", ".join(["%d" % (rem_nd) for rem_nd in rem_nds]),
                    ))
                    pure_peers = [cur_p for cur_p in pure_peers if cur_p[0] not in rem_nds and cur_p[1] not in rem_nds]
                else:
                    cur_inst.log("nothing to prune, exiting")
                    break
            else:
                cur_inst.log("no netdevices left to prune, exiting")
                break
        cur_inst.log(my_timer("pruning finished (%s)" % (logging_tools.get_plural("netdevice", len(pruned_pks)))))
        nds_visited = set()
        all_paths = []
        # some rules:
        # only routes via external (net)devices, so
        # no route from netdevice to netdevice (inner-device routing)
        old_perc, old_time = (1000, time.time())
        num_to_check = len(nd_pks) * len(nd_pks)
        checks_left = num_to_check
        for s_nd in nd_pks:
            perc_done = max(0, min(100, 100. - (100. * checks_left) / num_to_check))
            if abs(old_perc - perc_done) >= 10 or abs(time.time() - old_time) >= 5.:
                old_perc, old_time = (perc_done, time.time())
                cur_inst.log("%6.2f %% done (%7d of %7d)" % (perc_done, checks_left, num_to_check))
            checks_left -= len(nd_pks)
            for d_nd in nd_pks:
                if d_nd not in nds_visited:
                    #print "+++", d_nd
                    new_po = path_object(s_nd, d_nd)
                    # get all paths between s_nd and d_nd
                    new_paths = [[s_nd]]
                    # uncomment the following two lines when netdevice self-routing is desired
                    #if s_nd == d_nd:
                    #    new_po.feed_path([s_nd])
                    while new_paths:
                        cur_paths = new_paths
                        new_paths = []
                        for cur_path in cur_paths:
                            #print len(cur_path)
                            for next_nd in nb_dict.get(cur_path[-1], []):
                                if next_nd == d_nd:
                                    #new_po.feed_path(copy.deepcopy(cur_path) + [next_nd])
                                    new_po.feed_path(cur_path + [next_nd])
                                elif next_nd not in cur_path and rho.nd_dict[next_nd].routing:
                                    #print cur_path
                                    #new_paths.append(copy.deepcopy(cur_path) + [next_nd])
                                    new_paths.append(cur_path + [next_nd])
                        cur_paths = new_paths
                    if new_po:
                        all_paths.append(new_po)
                    nds_visited.add(s_nd)
        cur_inst.log("%6.2f %% done" % (100.))
        cur_inst.log(my_timer("pathfinding (%s) finished" % (logging_tools.get_plural("node", len(nd_pks)))))
        hopcount.objects.all().delete()
        cur_inst.log(my_timer("hopcount delete"))
        # add simple hopcounts from prune dict
        save_hcs = []
        for src_nd, dst_nds in rho.pruned_dict.iteritems():
            used_dst_nds = set()
            for dst_nd in dst_nds:
                save_hcs.extend(rho.create_hopcount([src_nd, dst_nd]))
                used_dst_nds.add(dst_nd)
                # add triplets (dst_nd -> src_nd -> dst_nd' )
                for dst_nd_2 in dst_nds:
                    if dst_nd_2 not in used_dst_nds:
                        save_hcs.extend(rho.create_hopcount([dst_nd, src_nd, dst_nd_2]))
        num_hcs = len(save_hcs)
        cur_inst.log("simple hops: %d" % (num_hcs))
        for cur_p in all_paths:
            cur_hcs = cur_p.generate_hopcounts(rho)
            num_hcs += len(cur_hcs)
            save_hcs.extend(cur_hcs)
            if len(save_hcs) > 200:
                hopcount.objects.bulk_create(save_hcs)
                save_hcs = []
        if save_hcs:
            hopcount.objects.bulk_create(save_hcs)
        cur_inst.log(my_timer("%d hopcounts inserted" % (num_hcs)))
        num_dups = rho.dups
        # enable new routing set
        rho.switch(num_hcs, num_dups)
        del rho
        del new_paths
        return num_hcs, num_dups
    def _call(self, cur_inst):
        # check for cluster-device-group
        try:
            cdg_dev = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            return "error no cluster_device_group defined"
        # show flag
        show = settings.DEBUG
        # get device-structs
        try:
            device_variable.objects.get(Q(device=cdg_dev) & Q(name=HOPCOUNT_REBUILT_VAR_NAME)).delete()
        except device_variable.DoesNotExist:
            pass
        try:
            # remove old state_var
            device_variable.objects.get(Q(device=cdg_dev) & Q(name=HOPCOUNT_STATE_VAR_NAME)).delete()
        except device_variable.DoesNotExist:
            pass
        state_var = device_variable(
            device=cdg_dev,
            name=HOPCOUNT_STATE_VAR_NAME,
            description="rebuild info",
            var_type="i",
            val_int=0)
        state_var.save()
        num_routes, num_dups = self._new_code(cur_inst)
        ret_str = "ok wrote %d routing entries (%d dups)" % (num_routes, num_dups)
        try:
            reb_var = device_variable.objects.get(Q(device=cdg_dev) & Q(name=HOPCOUNT_REBUILT_VAR_NAME))
        except device_variable.DoesNotExist:
            reb_var = device_variable(device=cdg_dev,
                                      name=HOPCOUNT_REBUILT_VAR_NAME)
        reb_var.var_type = "d"
        reb_var.description = "rebuilt at %s" % (
            global_config["SERVER_SHORT_NAME"],
        )
        reb_var.val_date = pytz.utc.localize(datetime.datetime(*time.localtime()[0:6]))
        reb_var.save()
        state_var.delete()
        cur_inst.srv_com["result"].attrib.update({
            "reply" : ret_str,
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        return
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
