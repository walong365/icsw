#!usr/bin/python -Ot
#
# Copyright (C) 2007,2012 Andreas Lang-Nevyjel
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
     peer_information

HOPCOUNT_REBUILT_VAR_NAME = "hopcount_table_build_time"
HOPCOUNT_STATE_VAR_NAME = "hopcount_state_var"

def generate_minhop_dict_old(in_hops):
    mh_d = {}
    for pen, pens, hop in in_hops:
        print hop, pens, len(hop), len(pens)
        #print pen, hop
        n_sig_1, n_sig_2 = (hop[0], hop[-1])
        sig = (n_sig_1, n_sig_2)
        for key in mh_d.keys():
            (sig_1, sig_2) = key
            if sig_1 == n_sig_1 and sig_2 == n_sig_2:
                sig = None
                if pen < mh_d[key][0]:
                    mh_d[key] = pen, pens, hop
        if sig:
            mh_d[sig] = (pen, pens, hop)
    return mh_d

def generate_minhop_dict(in_hops):
    # simpler (not needed) minhop_dict generator to honor loops (for redundant monitoring)
    mh_d = {}
    for run_idx, (pen, pens, hop) in enumerate(in_hops):
        mh_d[run_idx] = (pen, pens, hop)
    return mh_d

def get_hcs(hc, nd_dict):
    ndev = nd_dict[hc]
    #return "%s, %d (%d)" % (ndev["devname"], ndev["penalty"], hc)
    return "%s, %d" % (ndev.devname, ndev.penalty)
        
def find_path(source_ndev, dest_ndev, devs, peers, nd_dict):
    """ find path between source_ndev and dest_ndev """
    # net_devices touched
    #netdevs_touched = [source_ndev]
    # final connections
    final_cons = []
    # peer keys
    peer_keys = set(peers)
    # connection format is [penaltys], [hns, nds, nd2a, hn2, nd2b, nd3a, hn3, nd3b, ndd, hnd], [netdevs_touched]
    act_cons = [([], [source_ndev], set([source_ndev]))]
    while True:
        new_list = [(x, y, z) for x, y, z in act_cons if y[-1] in peer_keys]
        act_cons = []
        for act_peer, act_con, netdevs_touched in new_list:
            peer_stuff = peers[act_con[-1]]
            for nd, (new_p, d_route) in peer_stuff.iteritems():
                act_ndev = nd_dict[nd]
                if nd == dest_ndev:
                    final_cons.append((act_peer + [new_p], act_con + [nd]))
                elif d_route:
                    for next_nd in devs[act_ndev.device.name].nd_pks - netdevs_touched:
                        next_ndev = nd_dict[next_nd]
                        # needed ?
                        netdevs_touched.add(next_nd)
                        if act_ndev.pk not in act_con and next_nd != source_ndev and next_ndev.routing:
                            # routing device found
                            act_cons.append((act_peer + [new_p, act_ndev.penalty, next_ndev.penalty],
                                             act_con  + [nd, next_nd],
                                             netdevs_touched | set([nd, next_nd])))
        if not act_cons:
            break
    return final_cons

class rhc_device(object):
    def __init__(self, dev_record):
        self.device = dev_record
        self.__peers = []
        self.__netdevs = {}
        self.__routing = False
        self.device_type = "nc"
        self.__cts_f = []
        # all possible routes through this device in the form (src, dst)
        self.__int_routes = []
        # all routes from this device to all other external nds in the form (src, dst, route)
        self.__ext_routes = []
    def get_dot_str(self, d_dict, nd_lut):
        # device part
        d_f = ["%s [" % (self.device.name)]
        d_f.append("  label=\"%s|%s\"" % (self.device.name,
                                          "|".join(["<f%d>%s; %s" % (d_idx, d_stuff["devname"], ", ".join(d_stuff["ips"])) for d_idx, d_stuff in self.__netdevs.iteritems()])))
        d_f.append("  shape=record")
        d_f.append("];")
        # link part
        for a, b in self.__int_routes:
            if a in self.__netdevs.keys() and a != b:
                d_f.append("%s:f%d -- %s:f%d" % (d_dict[nd_lut[a]].name,
                                                 a,
                                                 d_dict[nd_lut[b]].name,
                                                 b))
        for a, b, c in self.__ext_routes:
            if a in self.__netdevs.keys():
                d_f.append("%s:f%d -- %s:f%d" % (d_dict[nd_lut[a]].name,
                                                 a,
                                                 d_dict[nd_lut[b]].name,
                                                 b))
        return "\n".join(d_f)
    def add_netdevice(self, nd_record):
        self.__netdevs[nd_record.pk] = nd_record
        nd_record.peers = []
        if self.device_type == "nc":
            self.device_type = "leaf"
        if nd_record.routing:
            self.__int_routes.append((nd_record.pk, nd_record.pk))
            for y in [i for i in self.__netdevs.keys() if i != nd_record.pk]:
                self.__int_routes.append((nd_record.pk, y))
                self.__int_routes.append((y, nd_record.pk))
            self.__routing = True
            self.device_type = "router"
    def get_routing_netdevice_idx_list(self):
        return [x for x in self.__netdevs.keys() if self.__netdevs[x]["routing"]]
    def get_netdevice_idx_list(self):
        return self.__netdevs.keys()
    def get_netdevice_info(self, idx):
        return self.__netdevs[idx]
    def add_ext_route(self, src_nd, dst_nd, r_info):
        if (src_nd, dst_nd) in self.__int_routes or (dst_nd, src_nd) in self.__int_routes:
            # route already covered by internal route, skip
            pass
        else:
            self.__ext_routes.append((src_nd, dst_nd, r_info))
    def get_peers(self, src_idx):
        return [(y, 0) for x, y in self.__int_routes if x == src_idx] + [(y, z) for x, y, z in self.__ext_routes if x == src_idx]
    def get_num_int_routes(self):
        return len(self.__int_routes)
    def get_num_ext_routes(self):
        return len(self.__ext_routes)
    def get_num_routes(self):
        return self.get_num_int_routes() + self.get_num_ext_routes()
    def get_nd_info(self, idx):
        act_nd = self.__netdevs[idx]
        return "%s (%d, %d)" % (
            act_nd["devname"],
            act_nd["penalty"],
            act_nd["routing"])
    def get_num_nds(self):
        return len(self.__netdevs.keys())
    def get_simple_peers(self, src_idx):
        return [(y, z) for x, y, z in self.__peers if x == src_idx]
    def add_peer_information(self, s_idx, d_idx, penalty):
        self.__netdevs[s_idx].peers.append((d_idx, penalty))
        self.__peers.append((s_idx, d_idx, penalty))
        self.__cts_f.append("%d.%d.%d" % (s_idx, d_idx, penalty))
        self.__cts_f.sort()
    def is_routing_device(self):
        return self.__routing
    def get_connection_type_str(self):
        return ":".join(self.__cts_f)
    
class r_route(object):
    def __init__(self, s_dev, d_dev):
        self.__s_dev = s_dev
        self.__d_dev = d_dev
    def find_routes(self, dev_dict, nd_lut):
        s_dev = dev_dict[nd_lut[self.__s_dev]]
        d_dev = dev_dict[nd_lut[self.__d_dev]]
        # find routes excluding penalty of s/d_netdevice
        if self.__s_dev == self.__d_dev:
            found = [(0, [self.__s_dev])]
            print "Loop (%s %s): %s" % (s_dev.name,
                                        s_dev.get_nd_info(self.__s_dev),
                                        str(found))
        else:
            act_nds = [(0, [self.__s_dev])]
##             act_nds = [(s_dev.get_netdevice_info(self.__s_dev)["penalty"], [self.__s_dev])]
            found = []
            while act_nds:
                #print "pass"
                new_nds = []
                for pen, x in act_nds:
                    for add_nd, add_pen, nd_pen in [(nd, np, dev_dict[nd_lut[nd]].get_netdevice_info(nd)["penalty"]) for nd, np in dev_dict[nd_lut[x[-1]]].get_peers(x[-1]) if not nd in x]:
                        #print x + [y]
                        if add_nd == self.__d_dev:
                            found.append((pen + add_pen, x + [add_nd]))
                        else:
                            new_nds.append((pen + add_pen + nd_pen, x + [add_nd]))
                act_nds = new_nds
            if found:
                print "From %s %s to %s %s (%d -> %d): %s" % (s_dev.name,
                                                              s_dev.get_nd_info(self.__s_dev),
                                                              d_dev.name,
                                                              d_dev.get_nd_info(self.__d_dev),
                                                              self.__s_dev,
                                                              self.__d_dev,
                                                              str(found))
        return found

class rebuild_hopcount(cs_base_class.server_com):
    class Meta:
        blocking = True
        needed_configs = ["rebuild_hopcount"]
        restartable = True
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
        nd_dict, devices, devices_2, peers, dev_lut = ({}, {}, {}, {}, {})
        nd_lut = {}
        # get list of devices 
        # netdevice version
        all_nds = netdevice.objects.exclude(Q(device__device_type__identifier="MD")).select_related("device__device_type")
        for db_rec in all_nds:
            if not devices.has_key(db_rec.device.name):
                devices_2[db_rec.device.name] = rhc_device(db_rec.device)
                devices[db_rec.device.name] = db_rec.device
                db_rec.device.nds = []
                db_rec.device.nd_pks = set()
                db_rec.device.peers = []
                dev_lut[db_rec.device.pk] = db_rec.device.name
            if db_rec.devname:
                if not nd_dict.has_key(db_rec.pk):
                    db_rec.peers = []
                    nd_dict[db_rec.pk] = db_rec
                    devices[db_rec.device.name].nds.append(db_rec)
                    devices[db_rec.device.name].nd_pks.add(db_rec.pk)
                    devices_2[db_rec.device.name].add_netdevice(db_rec)
                    nd_lut[db_rec.pk] = devices_2[db_rec.device.name].device.name
            #if db_rec.ip:
            #    devices_2[db_rec.device.name].add_netip(db_rec)
            
        # get peerinfo
        all_peers = peer_information.objects.all()
        #my_dc.execute("SELECT p.s_netdevice, p.d_netdevice, p.penalty, p.peer_information_idx FROM peer_information p")
        nd_keys = nd_dict.keys()
        for act_peer in all_peers:
            ps, pd = (act_peer.s_netdevice_id, act_peer.d_netdevice_id)
            if ps in nd_keys and pd in nd_keys:
                for src, dst in [(ps, pd), (pd, ps)]:
                    if nd_dict[src].routing and nd_dict[dst].routing:
                        devices_2[nd_lut[src]].add_ext_route(src, dst, act_peer.penalty)
                    devices_2[nd_lut[src]].add_peer_information(src, dst, act_peer.penalty)
                    peers.setdefault(src, {})[dst] = (act_peer.penalty, nd_dict[dst].routing)
        dev_names = set(devices.keys())
        # delete hopcounts
        hopcount.objects.all().delete()
        source_visit = set()
        num_routes, num_dups = (0, 0)
        # restarted ?
        restarted = 0
        num_devs = len(dev_names)
        num_to_check = num_devs * num_devs
        checks_left = num_to_check
        old_perc, old_time = (1000, time.time())
        for s_name in dev_names:
            perc_done = max(0, min(100, 100. - (100. * checks_left) / num_to_check))
            if abs(old_perc - perc_done) >= 10 or abs(time.time() - old_time) >= 5.:
                old_perc, old_time = (perc_done, time.time())
                self.log("%6.2f %% done" % perc_done)
                state_var.val_int = int(perc_done)
                state_var.save()
            checks_left -= 2 * num_devs - 1
            num_devs -= 1
            s_nets = devices[s_name].nds
            for d_name in dev_names - source_visit:
                all_hops = []
                d_nets = devices[d_name].nds
                for s_net in s_nets:
                    for d_net in d_nets:
                        all_hops.extend([(sum(x + [s_net.penalty, d_net.penalty]), x, y) for x, y in find_path(s_net.pk, d_net.pk, devices, peers, nd_dict)])
                if all_hops:
                    if show:
                        print "Found %3d routes from %10s to %10s" % (len(all_hops), s_name, d_name)
                    # only count hops if source and destination netdevice differs
                    # generate minhop-dict
                    #pprint.pprint(all_hops)
                    mh_d = generate_minhop_dict(all_hops)
                    for min_pen, min_pens, min_hop in mh_d.values():
                        min_idx, max_idx = (min_hop[0], min_hop[-1])
                        num_hops = (len(min_hop) + 1) / 2
                        if nd_dict[min_idx].device_id != nd_dict[max_idx].device_id:
                            short_trace = ":".join(["%d" % (nd_dict[min_idx].device_id)] +
                                                   ["%d" % (nd_dict[min_hop[x * 2 + 1]].device_id) for x in range(num_hops - 1)]+
                                                   ["%d" % (nd_dict[max_idx].device_id)]
                                                   )
                            #print short_trace
                            #print [nd_dict[x]["device"] for x in [min_idx]+min_hop[2:-1:4]+[max_idx]]
                        else:
                            short_trace = nd_dict[min_idx].device_id
                        if min_idx == max_idx:
                            hopcount(s_netdevice=nd_dict[min_idx],
                                     d_netdevice=nd_dict[max_idx],
                                     value=min_pen,
                                     trace=short_trace).save()
                        else:
                            num_dups += 1
                            hopcount(s_netdevice=nd_dict[min_idx],
                                     d_netdevice=nd_dict[max_idx],
                                     value=min_pen,
                                     trace=short_trace).save()
                            hopcount(s_netdevice=nd_dict[max_idx],
                                     d_netdevice=nd_dict[min_idx],
                                     value=min_pen,
                                     trace=short_trace).save()
##                                my_dc.execute("INSERT INTO hopcount VALUES(0,%d,%d,%d,'%s', null),(0,%d,%d,%d,'%s', null)" % (min_idx, max_idx, min_pen, short_trace, max_idx, min_idx, min_pen, short_trace))
                        num_routes += 1
                        if show:
                            trace = " -> ".join(["[%s (%s)] -> (%d)" % (nd_dict[min_idx].device.name, get_hcs(min_idx, nd_dict), min_pens[0])] +
                                                ["[(%s) <%s> (%s)] -> (%d)" % (get_hcs(min_hop[x * 2 + 1], nd_dict),
                                                                               nd_dict[min_hop[x * 2 + 1]].device.name,
                                                                               get_hcs(min_hop[x * 2 + 2], nd_dict),
                                                                               min_pens[x * 3 + 3]) for x in range(num_hops - 1)] +
                                                ["[(%s) %s]" % (get_hcs(max_idx, nd_dict),
                                                                nd_dict[max_idx].device.name)]
                                                )
                            print "  penalty %3d (%3d hops); %s" % (min_pen, num_hops, trace)
                else:
                    if show:
                        print "Found no routes from %10s to %10s" % (s_name, d_name)
            source_visit.add(s_name)
            #break
            # FIXME
            #restarted = call_params.check_for_restart()
            #if restarted:
            #    break
            #time.sleep(1)
        if restarted:
            ret_str = "error, command was restarted"
        else:
            ret_str = "ok wrote %d routing entries (%d dups)" % (num_routes, num_dups)
            try:
                reb_var = device_variable.objects.get(Q(device=cdg_dev) & Q(name=HOPCOUNT_REBUILT_VAR_NAME))
            except device_variable.DoesNotExist:
                reb_var = device_variable(device=cdg_dev,
                                          name="hopcount_table_build_time")
            reb_var.var_type = "d"
            reb_var.description = "rebuilt at %s" % (self.global_config["SERVER_SHORT_NAME"])
            reb_var.val_date = pytz.utc.localize(datetime.datetime(*time.localtime()[0:6]))
            reb_var.save()
            state_var.delete()
            if not self.global_config["COMMAND"] and False:
                print "broadcast"
                self.log("broadcasting write_etc_hosts to other cluster-servers")
                self.process_pool.send_broadcast("write_etc_hosts")
                my_dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE n.device=%d" % (self.server_idx))
                my_netdev_idxs = [db_rec["netdevice_idx"] for db_rec in my_dc.fetchall()]
                # start sending of nscd_reload commands
                my_dc.execute("SELECT d.name, i.ip, h.value FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg INNER JOIN device_type dt INNER JOIN " + \
                              "hopcount h INNER JOIN netdevice n INNER JOIN netip i LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND " + \
                              "dg.device_group_idx=d.device_group AND dc.new_config=c.new_config_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND c.name='mother_server' AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND h.s_netdevice=n.netdevice_idx AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in my_netdev_idxs])))
                serv_ip_dict = {}
                for db_rec in my_dc.fetchall():
                    serv_ip_dict.setdefault(db_rec["name"], db_rec["ip"])
                htc_com = "hopcount_table_changed"
                self.log("Contacting %s (%s): %s" % (logging_tools.get_plural("mother", len(serv_ip_dict.keys())),
                                                     htc_com,
                                                     ", ".join(["%s (IP %s)" % (k, v) for k, v in serv_ip_dict.iteritems()])))
                for serv_name, serv_ip in serv_ip_dict.iteritems():
                    # FIXME
                    #call_params.nss_queue.put(("contact_server", (serv_name, serv_ip, 8001, htc_com)))
                    pass
            self.log("%6.2f %% done" % (100))
        self.srv_com["result"].attrib.update({
            "reply" : ret_str,
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
