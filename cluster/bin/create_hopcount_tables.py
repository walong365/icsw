#!/usr/bin/python-init -Ot

import sys
import MySQLdb
import MySQLdb.cursors, MySQLdb.converters
import getopt
import configfile
import os
import os.path
import pprint

class db_con:
    con=0
    sc=0
    dc=0
    def __init__(self,config):
        self.con=MySQLdb.connect(config["MYSQL_HOST"],user=config["MYSQL_USER"],passwd=config["MYSQL_PASSWD"],db=config["MYSQL_DATABASE"])
        self.sc=MySQLdb.cursors.Cursor(self.con)
        self.dc=MySQLdb.cursors.DictCursor(self.con)
    def __del__(self):
        self.dc.close()
        self.sc.close()

def get_dbcon():
    cf1n="/usr/local/cluster/etc/mysql.cf"
    csuc,cfile=configfile.readconfig(cf1n,1)
    if not csuc:
        print "Unable to read configfile %s"%(cf1n)
        print "No config found, exiting..."
        sys.exit(0)
    dbcon=db_con(cfile)
    return dbcon

def get_hcs(hc):
    if hc["alias"]:
        return "%s, %s"%(hc["devname"],hc["alias"])
    else:
        return "%s"%(hc["devname"])
        
def find_path(source_ndev,dest_ndev,devs,peers,nd_dict):
    con_idx=0
    # net_devices touched
    netdevs_touched=[source_ndev]
    # final connections
    final_cons={}
    # peer keys
    peer_keys=peers.keys()
    # connection format is idx:(penalty,[hns,nds,nd2a,hn2,nd2b,nd3a,hn3,nd3b,ndd,hnd])
    act_cons={con_idx:(0,[{"name":nd_dict[source_ndev]["name"],"devname":nd_dict[source_ndev]["devname"],"alias":nd_dict[source_ndev]["alias"],"idx":source_ndev}])}
    while 1:
        #print act_cons
        act_dict={}
        for ci in act_cons.keys():
            act_pen,act_con=act_cons[ci]
            act_dict[act_con[-1]["idx"]]=ci
        act_list=act_dict.keys()
        # build dictionaries of open connections
        new_dict={}
        for act in [x for x in act_list if x in peer_keys]:
            new_dict[act]=(peers[act],act_cons[act_dict[act]])
        act_cons={}
        for ak,(peer_stuff,(act_p,act_con)) in new_dict.iteritems():
            for nd,(new_p,d_route) in peer_stuff.iteritems():
                act_ndev=nd_dict[nd]
                if nd==dest_ndev:
                    con_idx+=1
                    final_cons[con_idx]=(act_p+new_p,act_con+[new_p,{"idx":nd,"alias":act_ndev["alias"],"devname":act_ndev["devname"],"name":act_ndev["name"]}])
                elif d_route:
                    for next_ndev in [x for x in devs[act_ndev["name"]]["nds"] if x["netdevice_idx"] not in netdevs_touched]:
                        netdevs_touched+=[next_ndev["netdevice_idx"]]
                        if act_ndev["netdevice_idx"] not in act_con and next_ndev["netdevice_idx"] != source_ndev and next_ndev["routing"]:
                            # routing device found
                            con_idx+=1
                            act_cons[con_idx]=(act_p+new_p+act_ndev["penalty"]+next_ndev["penalty"],
                                               act_con+[new_p,
                                                        {"idx":nd,"alias":act_ndev["alias"],"devname":act_ndev["devname"],"name":act_ndev["name"]},
                                                        act_ndev["penalty"]+next_ndev["penalty"],
                                                        {"name":act_ndev["name"],"devname":next_ndev["devname"],"alias":next_ndev["alias"],"idx":next_ndev["netdevice_idx"]}])
        # any open edges ?
        if not len(act_cons):
            break
    #print final_cons
    return final_cons

def main():
    db=get_dbcon()
    dc=db.dc
    # get device-structs
    dc.execute("SELECT d.name,dt.identifier,d.device_idx FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx ORDER BY d.name")
    dev_struct={}
    # get list of devices 
    for x in dc.fetchall():
        dev_struct[x["name"]]=x
    nd_dict={}
    devices={}
    for act_dev_k,act_dev in dev_struct.iteritems():
        dc.execute("SELECT d.netdevice_idx,d.devname,d.routing,d.alias,d.penalty FROM netdevice d WHERE d.device=%d"%(act_dev["device_idx"]))
        af=dc.fetchall()
        for x in af:
            x["name"]=act_dev["name"]
            nd_dict[x["netdevice_idx"]]=x
        devices[act_dev["name"]]={"id":act_dev["identifier"],"nds":af}
    # get peerinfo
    dc.execute("SELECT p.s_netdevice,p.d_netdevice,p.penalty,p.peer_information_idx FROM peer_information p")
    all_peers=[x for x in dc.fetchall()]
    peers={}
    for act_peer in all_peers:
        ps=act_peer["s_netdevice"]
        pd=act_peer["d_netdevice"]
        for src,dst in [(ps,pd),(pd,ps)]:
            if not peers.has_key(src):
                peers[src]={}
            peers[src][dst]=((act_peer["penalty"],nd_dict[dst]["routing"]))
    # delete hopcounts
    #dc.execute("DELETE FROM hopcount")
    source_visit=[]
    dev_names=dev_struct.keys()
    dev_names.sort()
    num_p_w=0
    for s_name in dev_names:
        s_nets=devices[s_name]["nds"]
        for d_name in [x for x in dev_names if x not in source_visit]:
            all_hops=[]
            d_nets=devices[d_name]["nds"]
            for s_net in s_nets:
                for d_net in d_nets:
                    a=find_path(s_net["netdevice_idx"],d_net["netdevice_idx"],devices,peers,nd_dict)
                    all_hops+=a.values()
            if len(all_hops):
                print "Found %3d routes from %10s to %10s"%(len(all_hops),s_name,d_name)
                # generate minhop-dict
                mh_d={}
                for pen,hop in all_hops:
                    #print pen,hop
                    n_sig_1  =hop[ 0]["idx"]
                    n_sig_2  =hop[-1]["idx"]
                    n_alias_1=hop[ 0]["alias"]
                    n_alias_2=hop[-1]["alias"]
                    sig="%010d%010d%20s%20s"%(n_sig_1,n_sig_2,n_alias_1,n_alias_2)
                    new=1
                    for key in mh_d.keys():
                        sig_1=int(key[0:10])
                        sig_2=int(key[10:20])
                        alias_1=key[20:40]
                        alias_2=key[40:60]
                        if (sig_1 == n_sig_1 and alias_1 == n_alias_1) or (sig_2 == n_sig_2 and n_alias_2 == alias_2):
                            new=0
                            if pen < mh_d[key][0]:
                                mh_d[key]=pen,hop
                    if new:
                        mh_d[sig]=pen,hop
                min_hop,min_pen=(None,0)
                for pen,hop in all_hops:
                    if not min_hop or min_pen > pen:
                        min_pen,min_hop=(pen,hop)
                for h_key in mh_d:
                    min_pen,min_hop=mh_d[h_key]
                    num_hops=(len(min_hop)+1)/4
                    trace=" -> ".join(["[%s (%s)]"%(min_hop[0]["name"],get_hcs(min_hop[0]))]+
                                      ["[(%s) %s / %d (%s)]"%(get_hcs(min_hop[x*4+2]),min_hop[x*4+2]["name"],min_hop[x*4+3],get_hcs(min_hop[x*4+4])) for x in range(num_hops-1)]+
                                      ["[(%s) %s]"%(get_hcs(min_hop[-1]),min_hop[-1]["name"])]
                                      )
                    #dc.execute("INSERT INTO hopcount VALUES(0,%d,%d,%d,null)"%(min_hop[0]["idx"],min_hop[-1]["idx"],min_pen))
                    print "  penalty %3d (%3d hops); %s"%(min_pen,num_hops,trace)
                    num_p_w+=1
            else:
                print "Found no routes from %10s to %10s"%(s_name,d_name)
        source_visit+=[s_name]
    print num_p_w
    return 0

if __name__=="__main__":
    main()
    
