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
import server_command
from django.db.models import Q
from django.conf import settings
from initat.cluster.backbone.models import net_ip, netdevice, device, device_variable, hopcount, device_group, \
     peer_information, cs_timer
import pprint
import copy

HOPCOUNT_REBUILT_VAR_NAME = "hopcount_table_build_time"
HOPCOUNT_STATE_VAR_NAME = "hopcount_state_var"

##def generate_minhop_dict(in_hops):
##    # simpler (not needed) minhop_dict generator to honor loops (for redundant monitoring)
##    mh_d = {}
##    for run_idx, (pen, pens, hop) in enumerate(in_hops):
##        mh_d[run_idx] = (pen, pens, hop)
##    return mh_d
##
##def get_hcs(hc, nd_dict):
##    ndev = nd_dict[hc]
##    #return "%s, %d (%d)" % (ndev["devname"], ndev["penalty"], hc)
##    return "%s, %d" % (ndev.devname, ndev.penalty)
##        
##def find_path(source_ndev, dest_ndev, devs, peers, nd_dict):
##    """ find path between source_ndev and dest_ndev """
##    # net_devices touched
##    #netdevs_touched = [source_ndev]
##    # final connections
##    final_cons = []
##    # peer keys
##    peer_keys = set(peers)
##    # connection format is [penaltys], [hns, nds, nd2a, hn2, nd2b, nd3a, hn3, nd3b, ndd, hnd], [netdevs_touched]
##    act_cons = [([], [source_ndev], set([source_ndev]))]
##    while True:
##        new_list = [(x, y, z) for x, y, z in act_cons if y[-1] in peer_keys]
##        act_cons = []
##        for act_peer, act_con, netdevs_touched in new_list:
##            peer_stuff = peers[act_con[-1]]
##            for nd, (new_p, d_route) in peer_stuff.iteritems():
##                act_ndev = nd_dict[nd]
##                if nd == dest_ndev:
##                    final_cons.append((act_peer + [new_p], act_con + [nd]))
##                elif d_route:
##                    for next_nd in devs[act_ndev.device.name].nd_pks - netdevs_touched:
##                        next_ndev = nd_dict[next_nd]
##                        # needed ?
##                        netdevs_touched.add(next_nd)
##                        if act_ndev.pk not in act_con and next_nd != source_ndev and next_ndev.routing:
##                            # routing device found
##                            act_cons.append((act_peer + [new_p, act_ndev.penalty, next_ndev.penalty],
##                                             act_con  + [nd, next_nd],
##                                             netdevs_touched | set([nd, next_nd])))
##        if not act_cons:
##            break
##    return final_cons
##
##class rhc_device(object):
##    def __init__(self, dev_record):
##        self.device = dev_record
##        self.__peers = []
##        self.__netdevs = {}
##        self.__routing = False
##        self.device_type = "nc"
##        self.__cts_f = []
##        # all possible routes through this device in the form (src, dst)
##        self.__int_routes = []
##        # all routes from this device to all other external nds in the form (src, dst, route)
##        self.__ext_routes = []
##    def get_dot_str(self, d_dict, nd_lut):
##        # device part
##        d_f = ["%s [" % (self.device.name)]
##        d_f.append("  label=\"%s|%s\"" % (self.device.name,
##                                          "|".join(["<f%d>%s; %s" % (d_idx, d_stuff["devname"], ", ".join(d_stuff["ips"])) for d_idx, d_stuff in self.__netdevs.iteritems()])))
##        d_f.append("  shape=record")
##        d_f.append("];")
##        # link part
##        for a, b in self.__int_routes:
##            if a in self.__netdevs.keys() and a != b:
##                d_f.append("%s:f%d -- %s:f%d" % (d_dict[nd_lut[a]].name,
##                                                 a,
##                                                 d_dict[nd_lut[b]].name,
##                                                 b))
##        for a, b, c in self.__ext_routes:
##            if a in self.__netdevs.keys():
##                d_f.append("%s:f%d -- %s:f%d" % (d_dict[nd_lut[a]].name,
##                                                 a,
##                                                 d_dict[nd_lut[b]].name,
##                                                 b))
##        return "\n".join(d_f)
##    def add_netdevice(self, nd_record):
##        self.__netdevs[nd_record.pk] = nd_record
##        nd_record.peers = []
##        if self.device_type == "nc":
##            self.device_type = "leaf"
##        if nd_record.routing:
##            self.__int_routes.append((nd_record.pk, nd_record.pk))
##            for y in [i for i in self.__netdevs.keys() if i != nd_record.pk]:
##                self.__int_routes.append((nd_record.pk, y))
##                self.__int_routes.append((y, nd_record.pk))
##            self.__routing = True
##            self.device_type = "router"
##    def get_routing_netdevice_idx_list(self):
##        return [x for x in self.__netdevs.keys() if self.__netdevs[x]["routing"]]
##    def get_netdevice_idx_list(self):
##        return self.__netdevs.keys()
##    def get_netdevice_info(self, idx):
##        return self.__netdevs[idx]
##    def add_ext_route(self, src_nd, dst_nd, r_info):
##        if (src_nd, dst_nd) in self.__int_routes or (dst_nd, src_nd) in self.__int_routes:
##            # route already covered by internal route, skip
##            pass
##        else:
##            self.__ext_routes.append((src_nd, dst_nd, r_info))
##    def get_peers(self, src_idx):
##        return [(y, 0) for x, y in self.__int_routes if x == src_idx] + [(y, z) for x, y, z in self.__ext_routes if x == src_idx]
##    def get_num_int_routes(self):
##        return len(self.__int_routes)
##    def get_num_ext_routes(self):
##        return len(self.__ext_routes)
##    def get_num_routes(self):
##        return self.get_num_int_routes() + self.get_num_ext_routes()
##    def get_nd_info(self, idx):
##        act_nd = self.__netdevs[idx]
##        return "%s (%d, %d)" % (
##            act_nd["devname"],
##            act_nd["penalty"],
##            act_nd["routing"])
##    def get_num_nds(self):
##        return len(self.__netdevs.keys())
##    def get_simple_peers(self, src_idx):
##        return [(y, z) for x, y, z in self.__peers if x == src_idx]
##    def add_peer_information(self, s_idx, d_idx, penalty):
##        self.__netdevs[s_idx].peers.append((d_idx, penalty))
##        self.__peers.append((s_idx, d_idx, penalty))
##        self.__cts_f.append("%d.%d.%d" % (s_idx, d_idx, penalty))
##        self.__cts_f.sort()
##    def is_routing_device(self):
##        return self.__routing
##    def get_connection_type_str(self):
##        return ":".join(self.__cts_f)
##    
##class r_route(object):
##    def __init__(self, s_dev, d_dev):
##        self.__s_dev = s_dev
##        self.__d_dev = d_dev
##    def find_routes(self, dev_dict, nd_lut):
##        s_dev = dev_dict[nd_lut[self.__s_dev]]
##        d_dev = dev_dict[nd_lut[self.__d_dev]]
##        # find routes excluding penalty of s/d_netdevice
##        if self.__s_dev == self.__d_dev:
##            found = [(0, [self.__s_dev])]
##            print "Loop (%s %s): %s" % (s_dev.name,
##                                        s_dev.get_nd_info(self.__s_dev),
##                                        str(found))
##        else:
##            act_nds = [(0, [self.__s_dev])]
####             act_nds = [(s_dev.get_netdevice_info(self.__s_dev)["penalty"], [self.__s_dev])]
##            found = []
##            while act_nds:
##                #print "pass"
##                new_nds = []
##                for pen, x in act_nds:
##                    for add_nd, add_pen, nd_pen in [(nd, np, dev_dict[nd_lut[nd]].get_netdevice_info(nd)["penalty"]) for nd, np in dev_dict[nd_lut[x[-1]]].get_peers(x[-1]) if not nd in x]:
##                        #print x + [y]
##                        if add_nd == self.__d_dev:
##                            found.append((pen + add_pen, x + [add_nd]))
##                        else:
##                            new_nds.append((pen + add_pen + nd_pen, x + [add_nd]))
##                act_nds = new_nds
##            if found:
##                print "From %s %s to %s %s (%d -> %d): %s" % (s_dev.name,
##                                                              s_dev.get_nd_info(self.__s_dev),
##                                                              d_dev.name,
##                                                              d_dev.get_nd_info(self.__d_dev),
##                                                              self.__s_dev,
##                                                              self.__d_dev,
##                                                              str(found))
##        return found

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
    def __init__(self):
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
    def create_hopcount(self, nd_list):
        penalty = sum([self.nd_dict[nd_list[idx]].penalty + self.peer_dict[(nd_list[idx], nd_list[idx + 1])] for idx in xrange(len(nd_list) - 1)], 0) + self.nd_dict[nd_list[-1]].penalty
        ret_list = [
            hopcount(
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
        restartable = True
    def _new_code(self):
        rho = route_helper_obj()
        my_timer = cs_timer()
        self.log("building routing info for %s and %s" % (
            logging_tools.get_plural("netdevice", len(rho.all_nds)),
            logging_tools.get_plural("peer information", len(rho.all_peers))))
        pure_peers = [(cur_p.s_netdevice_id, cur_p.d_netdevice_id) for cur_p in rho.all_peers]
        # dot part
        if True:
            dot_file = file("/tmp/r.dot", "w")
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
                dot_file.write("n_%d %s;\n" % (
                    nd_pk,
                    "[shape=%s, label=\"%s\"]" % (
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
            self.log("prune step %d" % (prune_step))
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
                    self.log("removing %s (%s) while pruning" % (
                        logging_tools.get_plural("netdevice", len(rem_nds)),
                        ", ".join(["%d" % (rem_nd) for rem_nd in rem_nds]),
                    ))
                    pure_peers = [cur_p for cur_p in pure_peers if cur_p[0] not in rem_nds and cur_p[1] not in rem_nds]
                else:
                    self.log("nothing to prune, exiting")
                    break
            else:
                self.log("no netdevices left to prune, exiting")
                break
        self.log(my_timer("pruning finished (%s)" % (logging_tools.get_plural("netdevice", len(pruned_pks)))))
        nds_visited = set()
        all_paths = []
        # some rules:
        # only routes via external (net)devices, so
        # no route from netdevice to netdevice (inner-device routing)
        for s_nd in nd_pks:
            for d_nd in nd_pks:
                if d_nd not in nds_visited:
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
                            for next_nd in nb_dict.get(cur_path[-1], []):
                                if next_nd == d_nd:
                                    new_po.feed_path(copy.deepcopy(cur_path) + [next_nd])
                                elif next_nd not in cur_path and rho.nd_dict[next_nd].routing:
                                    new_paths.append(copy.deepcopy(cur_path) + [next_nd])
                        cur_paths = new_paths
                    if new_po:
                        all_paths.append(new_po)
                        nds_visited.add(s_nd)
        self.log(my_timer("pathfinding (%s) finished" % (logging_tools.get_plural("node", len(nd_pks)))))
        hopcount.objects.all().delete()
        self.log(my_timer("hopcount delete"))
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
        self.log("simple hops: %d" % (num_hcs))
        for cur_p in all_paths:
            cur_hcs = cur_p.generate_hopcounts(rho)
            num_hcs += len(cur_hcs)
            save_hcs.extend(cur_hcs)
            if len(save_hcs) > 200:
                hopcount.objects.bulk_create(save_hcs)
                save_hcs = []
        if save_hcs:
            hopcount.objects.bulk_create(save_hcs)
        self.log(my_timer("%d hopcounts inserted" % (num_hcs)))
        num_dups = rho.dups
        del rho
        return num_hcs, num_dups
    def _call(self):
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
        num_routes, num_dups = self._new_code()
        ret_str = "ok wrote %d routing entries (%d dups)" % (num_routes, num_dups)
        try:
            reb_var = device_variable.objects.get(Q(device=cdg_dev) & Q(name=HOPCOUNT_REBUILT_VAR_NAME))
        except device_variable.DoesNotExist:
            reb_var = device_variable(device=cdg_dev,
                                      name=HOPCOUNT_REBUILT_VAR_NAME)
        reb_var.var_type = "d"
        min_peer_pk = peer_information.objects.all().order_by("pk")[0].pk
        max_peer_pk = peer_information.objects.all().order_by("-pk")[0].pk
        num_peers = peer_information.objects.all().count()
        reb_var.description = "rebuilt at %s {%d:%d:%d}" % (
            self.global_config["SERVER_SHORT_NAME"],
            min_peer_pk,
            num_peers,
            max_peer_pk,
        )
        print reb_var.description
        reb_var.val_date = pytz.utc.localize(datetime.datetime(*time.localtime()[0:6]))
        reb_var.save()
        state_var.delete()
        self.srv_com["result"].attrib.update({
            "reply" : ret_str,
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        return
        # old code
##        nd_dict, devices, devices_2, peers, dev_lut = ({}, {}, {}, {}, {})
##        nd_lut = {}
##        # get list of devices 
##        # netdevice version
##        all_nds = netdevice.objects.exclude(Q(device__device_type__identifier="MD")).select_related("device__device_type")
##        for db_rec in all_nds:
##            if not devices.has_key(db_rec.device.name):
##                devices_2[db_rec.device.name] = rhc_device(db_rec.device)
##                devices[db_rec.device.name] = db_rec.device
##                db_rec.device.nds = []
##                db_rec.device.nd_pks = set()
##                db_rec.device.peers = []
##                dev_lut[db_rec.device.pk] = db_rec.device.name
##            if db_rec.devname:
##                if not nd_dict.has_key(db_rec.pk):
##                    db_rec.peers = []
##                    nd_dict[db_rec.pk] = db_rec
##                    devices[db_rec.device.name].nds.append(db_rec)
##                    devices[db_rec.device.name].nd_pks.add(db_rec.pk)
##                    devices_2[db_rec.device.name].add_netdevice(db_rec)
##                    nd_lut[db_rec.pk] = devices_2[db_rec.device.name].device.name
##            #if db_rec.ip:
##            #    devices_2[db_rec.device.name].add_netip(db_rec)
##            
##        # get peerinfo
##        all_peers = peer_information.objects.all()
##        #my_dc.execute("SELECT p.s_netdevice, p.d_netdevice, p.penalty, p.peer_information_idx FROM peer_information p")
##        nd_keys = nd_dict.keys()
##        for act_peer in all_peers:
##            ps, pd = (act_peer.s_netdevice_id, act_peer.d_netdevice_id)
##            if ps in nd_keys and pd in nd_keys:
##                for src, dst in [(ps, pd), (pd, ps)]:
##                    if nd_dict[src].routing and nd_dict[dst].routing:
##                        devices_2[nd_lut[src]].add_ext_route(src, dst, act_peer.penalty)
##                    devices_2[nd_lut[src]].add_peer_information(src, dst, act_peer.penalty)
##                    peers.setdefault(src, {})[dst] = (act_peer.penalty, nd_dict[dst].routing)
##        dev_names = set(devices.keys())
##        # delete hopcounts
##        hopcount.objects.all().delete()
##        source_visit = set()
##        num_routes, num_dups = (0, 0)
##        # restarted ?
##        restarted = 0
##        num_devs = len(dev_names)
##        num_to_check = num_devs * num_devs
##        checks_left = num_to_check
##        old_perc, old_time = (1000, time.time())
##        for s_name in dev_names:
##            perc_done = max(0, min(100, 100. - (100. * checks_left) / num_to_check))
##            if abs(old_perc - perc_done) >= 10 or abs(time.time() - old_time) >= 5.:
##                old_perc, old_time = (perc_done, time.time())
##                self.log("%6.2f %% done" % perc_done)
##                state_var.val_int = int(perc_done)
##                state_var.save()
##            checks_left -= 2 * num_devs - 1
##            num_devs -= 1
##            s_nets = devices[s_name].nds
##            for d_name in dev_names - source_visit:
##                all_hops = []
##                d_nets = devices[d_name].nds
##                for s_net in s_nets:
##                    for d_net in d_nets:
##                        all_hops.extend([(sum(x + [s_net.penalty, d_net.penalty]), x, y) for x, y in find_path(s_net.pk, d_net.pk, devices, peers, nd_dict)])
##                if all_hops:
##                    if show:
##                        print "Found %3d routes from %10s (%3d) to %10s (%3d)" % (len(all_hops), s_name, devices[s_name].pk, d_name, devices[d_name].pk)
##                    # only count hops if source and destination netdevice differs
##                    # generate minhop-dict
##                    #pprint.pprint(all_hops)
##                    mh_d = generate_minhop_dict(all_hops)
##                    last_min, last_max, last_pen = (None, None, None)
##                    for min_pen, min_pens, min_hop in mh_d.values():
##                        min_idx, max_idx = (min_hop[0], min_hop[-1])
##                        num_hops = (len(min_hop) + 1) / 2
##                        if nd_dict[min_idx].device_id != nd_dict[max_idx].device_id:
##                            short_trace = ":".join(["%d" % (nd_dict[min_idx].device_id)] +
##                                                   ["%d" % (nd_dict[min_hop[x * 2 + 1]].device_id) for x in range(num_hops - 1)]+
##                                                   ["%d" % (nd_dict[max_idx].device_id)]
##                                                   )
##                            #print short_trace
##                            #print [nd_dict[x]["device"] for x in [min_idx]+min_hop[2:-1:4]+[max_idx]]
##                        else:
##                            short_trace = nd_dict[min_idx].device_id
##                        if min_idx == max_idx:
##                            if last_min != min_idx or last_max != max_idx or last_pen != min_pen:
##                                hopcount(s_netdevice=nd_dict[min_idx],
##                                         d_netdevice=nd_dict[max_idx],
##                                         value=min_pen,
##                                         trace=short_trace).save()
##                                last_min = min_idx
##                                last_max = max_idx
##                                last_pen = min_pen
##                                num_routes += 1
##                            else:
##                                print "skip"
##                        else:
##                            num_dups += 1
##                            hopcount(s_netdevice=nd_dict[min_idx],
##                                     d_netdevice=nd_dict[max_idx],
##                                     value=min_pen,
##                                     trace=short_trace).save()
##                            hopcount(s_netdevice=nd_dict[max_idx],
##                                     d_netdevice=nd_dict[min_idx],
##                                     value=min_pen,
##                                     trace=short_trace).save()
##                            num_routes += 1
####                                my_dc.execute("INSERT INTO hopcount VALUES(0,%d,%d,%d,'%s', null),(0,%d,%d,%d,'%s', null)" % (min_idx, max_idx, min_pen, short_trace, max_idx, min_idx, min_pen, short_trace))
##                        if show:
##                            trace = " -> ".join(["[%s (%s)] -> (%d)" % (nd_dict[min_idx].device.name, get_hcs(min_idx, nd_dict), min_pens[0])] +
##                                                ["[(%s) <%s> (%s)] -> (%d)" % (get_hcs(min_hop[x * 2 + 1], nd_dict),
##                                                                               nd_dict[min_hop[x * 2 + 1]].device.name,
##                                                                               get_hcs(min_hop[x * 2 + 2], nd_dict),
##                                                                               min_pens[x * 3 + 3]) for x in range(num_hops - 1)] +
##                                                ["[(%s) %s]" % (get_hcs(max_idx, nd_dict),
##                                                                nd_dict[max_idx].device.name)]
##                                                )
##                            print "  penalty %3d (%s)" % (
##                                min_pen,
##                                short_trace,
##                            )
##                            #print "  penalty %3d (%3d hops); %s" % (min_pen, num_hops, trace)
##                else:
##                    if show:
##                        print "Found no routes from %10s to %10s" % (s_name, d_name)
##            source_visit.add(s_name)
##            #break
##            # FIXME
##            #restarted = call_params.check_for_restart()
##            #if restarted:
##            #    break
##            #time.sleep(1)
##        if restarted:
##            ret_str = "error, command was restarted"
##        else:
##            ret_str = "ok wrote %d routing entries (%d dups)" % (num_routes, num_dups)
##            try:
##                reb_var = device_variable.objects.get(Q(device=cdg_dev) & Q(name=HOPCOUNT_REBUILT_VAR_NAME))
##            except device_variable.DoesNotExist:
##                reb_var = device_variable(device=cdg_dev,
##                                          name="hopcount_table_build_time")
##            reb_var.var_type = "d"
##            reb_var.description = "rebuilt at %s" % (self.global_config["SERVER_SHORT_NAME"])
##            reb_var.val_date = pytz.utc.localize(datetime.datetime(*time.localtime()[0:6]))
##            reb_var.save()
##            state_var.delete()
##            if not self.global_config["COMMAND"] and False:
##                print "broadcast"
##                self.log("broadcasting write_etc_hosts to other cluster-servers")
##                self.process_pool.send_broadcast("write_etc_hosts")
##                my_dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE n.device=%d" % (self.server_idx))
##                my_netdev_idxs = [db_rec["netdevice_idx"] for db_rec in my_dc.fetchall()]
##                # start sending of nscd_reload commands
##                my_dc.execute("SELECT d.name, i.ip, h.value FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg INNER JOIN device_type dt INNER JOIN " + \
##                              "hopcount h INNER JOIN netdevice n INNER JOIN netip i LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND " + \
##                              "dg.device_group_idx=d.device_group AND dc.new_config=c.new_config_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND c.name='mother_server' AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND h.s_netdevice=n.netdevice_idx AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in my_netdev_idxs])))
##                serv_ip_dict = {}
##                for db_rec in my_dc.fetchall():
##                    serv_ip_dict.setdefault(db_rec["name"], db_rec["ip"])
##                htc_com = "hopcount_table_changed"
##                self.log("Contacting %s (%s): %s" % (logging_tools.get_plural("mother", len(serv_ip_dict.keys())),
##                                                     htc_com,
##                                                     ", ".join(["%s (IP %s)" % (k, v) for k, v in serv_ip_dict.iteritems()])))
##                for serv_name, serv_ip in serv_ip_dict.iteritems():
##                    # FIXME
##                    #call_params.nss_queue.put(("contact_server", (serv_name, serv_ip, 8001, htc_com)))
##                    pass
##            self.log("%6.2f %% done" % (100))
##        self.srv_com["result"].attrib.update({
##            "reply" : ret_str,
##            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
