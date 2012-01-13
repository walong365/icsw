#!/usr/bin/python-init -Otu

import time
#from scapy.all import sr,IP,ICMP,RandShort, TCP, conf, Ether,sr1
#conf.resolve.remove(Ether.dst)

if False:
    for idx in xrange(1):
        print conf.netcache.arp_cache
        #conf.netcache.arp_cache["192.168.1.60"] = "a"
        s_time = time.time()
        p = sr([IP(dst="192.168.1.60")/ICMP(), IP(dst="192.168.2.60")/ICMP()], timeout=3, verbose=1, nofilter=1)
        e_time = time.time()
        print p
        print e_time - s_time

import net_tools

s_time = time.time()
my_ns = net_tools.network_send(timeout=1)
ping_obj = net_tools.icmp_bind(exit_on_finish=True)
my_ns.add_object(ping_obj)
my_c = net_tools.icmp_client(host_list=["192.168.1.%d" % (idx) for idx in xrange(21, 26)], timeout=2, fast_mode=True)
ping_obj.add_icmp_client(my_c)
while not my_ns.exit_requested():
    my_ns.step()
my_ns.remove_object(ping_obj)
print "-"
my_ns.step()
e_time = time.time()
import pprint
pprint.pprint(my_c.get_result())
print e_time - s_time
