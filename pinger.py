#!/opt/python-init/bin/python -Ot

import icmp, ip
import socket
import select
import string
import os,sys
import time
import re

FailMark=-666

class Pinger(object):
    def __init__(self, addrs, num):
        ip_ms=re.compile("^\d+\.\d+\.\d+\.\d+$")
        self.num=num
        self.sent=0
        self.seq=0
        self.sents={}
        self.deltas={}
        self.summary={}
        self.socket=icmp.PingSocket()
        if self.socket:
            self.addrs=[]
            for addr in addrs:
                if not ip_ms.match(addr):
                    try:
                        fqname,aliases,ip_list=socket.gethostbyname_ex(addr)
                    except socket.gaierror:
                        addr=None
                    else:
                        addr=ip_list[0]
                if addr:
                    self.addrs.append(addr)
                    self.deltas[addr]=[]
        else:
            self.addrs=None
        self.pid = os.getpid()
    def send_packet(self):
        pkt=icmp.Packet()
        pkt.type=icmp.ICMP_ECHO
        pkt.id=self.pid
        self.sent+=1
        self.waitfor={}
        for addr in self.addrs:
            pkt.seq=self.seq
            pkt.data='init.at pingtest'
            buf=pkt.assemble()
            self.deltas[addr].append(FailMark)
            self.sents[addr]=time.time()
            self.socket.sendto(addr,buf)
            self.waitfor[pkt.seq]=1
            self.seq+=1
        self.plen=len(buf)

    def recv_packet(self, pkt, when,src):
        try:
            sent=self.sents[src]
        except KeyError:
            print "KeyError",src
            return
        if self.waitfor.has_key(pkt.seq):
            del self.waitfor[pkt.seq]
        # limit to ms precision
        delta=int((when-sent)*1000.)
        # max() because maybe we receive a `delayed` package
        self.deltas[src][-1]=max(self.deltas[src][-1],delta)
    def ping(self,timeout=2.0,flood=0):
        if len(self.addrs):
            # don't wait more than timeout seconds from now for first reply
            self.last_arrival = time.time()
            while 1:
                if self.sent < self.num:
                    self.send_packet()
                # all packages sent and received
                elif not self.waitfor:
                    break
                else:
                    now = time.time()
                    # Wait no more than timeout seconds
                    if (now - self.last_arrival) > timeout:
                        break
                self.wait(timeout,flood)

    def wait(self,timeout_w,flood=0):
        start=time.time()
        timeout=timeout_w
        while timeout > 0:
            if self.waitfor or not flood:
                rd,wt,er=select.select([self.socket.socket],[],[],timeout)
                if rd:
                    arrival = time.time()
                    # okay to use time here, because select has told us
                    # there is data and we don't care to measure the time
                    # it takes the system to give us the packet.
                    try:
                        pkt,who=self.socket.recvfrom(4096)
                    except socket.error:
                        continue
                    # could also use the ip module to get the payload
                    repip=ip.Packet(pkt)
                    try:
                        reply=icmp.Packet(repip.data)
                    except ValueError:
                        continue
                    if reply.id == self.pid:
                        self.recv_packet(reply,arrival,repip.src)
                        self.last_arrival=arrival
                timeout=(start+timeout_w)-time.time()
            else:
                timeout=-1
            
    def get_summary(self):
        for addr in self.addrs:
            dltas=self.deltas[addr]
            dmin=min(dltas)
            dmax=max(dltas)
            miss=dltas.count(FailMark)
            sent=len(dltas)
            recv=sent-miss
            if miss==sent:
                davg=0
                dmin=0
                dmax=0
            else:
                davg=(reduce(lambda x,y:x+y,dltas)-miss*FailMark)/(sent-miss)
            loss=100*int(float(sent-recv)/float(sent))
            self.summary[addr]=(sent,recv,loss,dmin,davg,dmax)

