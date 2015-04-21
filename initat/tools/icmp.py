"""ICMP packets.
"""

# Copyright 1997, Corporation for National Research Initiatives
# written by Jeremy Hylton, jeremy@cnri.reston.va.us

import inet
import array
import struct
import socket

ICMP_MINLEN = 8
ICMP_MASKLEN = 12
ICMP_ECHOREPLY = 0
ICMP_UNREACH = 3
ICMP_UNREACH_NET = 0
ICMP_UNREACH_HOST = 1
ICMP_UNREACH_PROTOCOL = 2
ICMP_UNREACH_PORT = 3
ICMP_UNREACH_NEEDFRAG = 4
ICMP_UNREACH_SRCFAIL = 5
ICMP_SOURCEQUENCH = 4
ICMP_REDIRECT = 5
ICMP_REDIRECT_NET = 0
ICMP_REDIRECT_HOST = 1
ICMP_REDIRECT_TOSNET = 2
ICMP_REDIRECT_TOSHOST = 3
ICMP_ECHO = 8
ICMP_TIMXCEED = 11
ICMP_TIMXCEED_INTRANS = 0
ICMP_TIMXCEED_REASS = 1
ICMP_PARAMPROB = 12
ICMP_TSTAMP = 13
ICMP_TSTAMPREPLY = 14
ICMP_IREQ = 15
ICMP_IREQREPLY = 16
ICMP_MASKREQ = 17
ICMP_MASKREPLY = 18

class PingSocket:
    def __init__(self):
        self.open_icmp_socket()
    def open_icmp_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_RAW,socket.IPPROTO_ICMP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            #self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_WRTBUF,262144)
            #self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
            self.socket.setblocking(0)
        except:
            self.socket=None
    def fileno(self):
        return self.socket.fileno()
    def close(self):
        self.socket.close()
    def sendto(self,dest,packet):
        if self.socket:
            try:
                self.socket.sendto(packet,(socket.gethostbyname(dest),0))
            except:
                pass
    def recvfrom(self,maxbytes):
        if self.socket:
            return self.socket.recvfrom(maxbytes)
        else:
            return None
    def socket_ok(self):
        return self.socket and True or False

class Packet:
    """Basic ICMP packet definition.

    Equivalent to ICMP_ECHO_REQUEST and ICMP_REPLY packets.
    Other packets are defined as subclasses probably.
    """

    def __init__(self, packet=None, cksum=1):
        if packet:
            self.__disassemble(packet, cksum)
        else:
            self.type = 0
            self.code = 0
            self.cksum = 0
            self.id = 0
            self.seq = 0
            self.data = ''

    def __repr__(self):
        return "<ICMP packet %d %d %d %d>" % (self.type, self.code,
                                              self.id, self.seq)

    def assemble(self, cksum=1):
        idseq = struct.pack('hh', self.id, self.seq)
        packet = chr(self.type) + chr(self.code) + '\000\000' + idseq \
                 + self.data
        if cksum:
            self.cksum = inet.cksum(packet)
            packet = chr(self.type) + chr(self.code) \
                     + struct.pack('H', self.cksum) + idseq + self.data
        # Don't need to do any byte-swapping, because idseq is
        # appplication defined and others are single byte values.
        self.__packet = packet
        return self.__packet

    def __disassemble(self, packet, cksum=1):
        if cksum:
            our_cksum = inet.cksum(packet)
            if our_cksum != 0:
                raise ValueError, packet

        self.type = ord(packet[0])
        self.code = ord(packet[1])
        elts = struct.unpack('hhh', packet[2:8])
        [self.cksum, self.id, self.seq] = map(lambda x:x & 0xffff, elts)
        self.data = packet[8:]

    def __compute_cksum(self):
        "Use inet.cksum instead"
        return inet.cksum(self.packet)
        packet = self.packet
        if len(packet) & 1:
            packet = packet + '\0'
        words = array.array('h', packet)
        sum = 0
        for word in words:
            sum = sum + (word & 0xffff)
        hi = sum >> 16
        lo = sum & 0xffff
        sum = hi + lo
        sum = sum + (sum >> 16)
        return (~sum) & 0xffff


class TimeExceeded(Packet):

    def __init__(self, packet=None, cksum=1):
        Packet.__init__(self, packet, cksum)
        if packet:
            if self.type != ICMP_TIMXCEED:
                raise ValueError, "supplied packet of wrong type"
        else:
            self.type = ICMP_TIMXCEED
            self.id = self.seq = 0

class Unreachable(Packet):

    def __init__(self, packet=None, cksum=1):
        Packet.__init__(self, packet, cksum)
        if packet:
            if self.type != ICMP_UNREACH:
                raise ValueError, "supplied packet of wrong type"
        else:
            self.type = ICMP_UNREACH
            self.id = self.seq = 0

