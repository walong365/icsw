# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" A raw ICMP baseclass (icmp protocol), based on seafelt lib/icmp.py """

import array
import os
import socket
import struct
import time

from initat.tools import logging_tools


def _octets_to_hex(octets):
    return ".".join(["%02x" % (ord(byte)) for byte in octets])


def _checksum(data):
    """ Calculate the 16-bit ones complement checksum of data """
    if len(data) % 2:
        data += chr(0x0)
    cur_sum = sum([word & 0xffff for word in array.array("h", data)])
    hi, lo = (cur_sum >> 16, cur_sum & 0xffff)
    cur_sum = hi + lo
    cur_sum += cur_sum >> 16
    return (~cur_sum) & 0xffff


class ip_packet(object):
    """ IP Packet representation """
    def __init__(self, src_addr, dst_addr, payload,
                 version=4, tos=0, ident=0,
                 dont_fragment=True,
                 more_fragments=False,
                 frag_offset=0, ttl=64, protocol=1, options=""):
        self.ihl = 5 + len(options)
        self.ihlversion = self.ihl & 0xF0 + version
        self.tos = tos
        self.ident = ident
        self.dont_fragment = dont_fragment
        self.more_fragments = more_fragments
        self.frag_offset = frag_offset

        flags_fragment = 0x0000
        if dont_fragment:
            flags_fragment += 0x4000
        if more_fragments:
            flags_fragment += 0x2000
        self.flags_fragment = flags_fragment + (frag_offset & 0x1FFF)

        self.ttl = ttl
        self.protocol = protocol
        self.src_addr = src_addr
        self.dst_addr = dst_addr
        self.payload = payload
        self.options = options
        if options:
            raise NotImplementedError("Options are not implemented yet.")
        self.checksum = 0
        self.tot_len = self.ihl + len(payload)
        self.checksum = _checksum(self.packed())

    def packed(self):
        """ return packed version """
        if len(self.options) > 0:
            raise NotImplementedError("Options packing is not implemented")
        data = struct.pack(
            "!BBHHHBBH4s4s",
            self.ihlversion,
            self.tos,
            self.tot_len,
            self.ident,
            self.flags_fragment,
            self.ttl,
            self.protocol,
            self.checksum,
            self.src_addr,
            self.dst_addr)
        data += self.payload
        return data

    def __repr__(self):
        return "<ip_packet: {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}>".format(
            self.ihlversion,
            self.tos,
            self.tot_len,
            self.ident,
            self.flags_fragment,
            self.ttl,
            self.protocol,
            self.checksum,
            self.src_addr,
            self.dst_addr,
            _octets_to_hex(self.payload)
        )


def _parse_ip_packet(data):
    """ parse received data as IP packet """
    (
        ihlversion, tos, _tot_len,
        ident, flags_fragment, ttl,
        protocol, checksum,
        src_addr, dst_addr
    ) = struct.unpack("!BBHHHBBH4s4s", data[:20])
    src_addr = socket.inet_ntoa(src_addr)
    dst_addr = socket.inet_ntoa(dst_addr)
    version = ihlversion & 0xF0
    ihl = ihlversion & 0x0F
    _fragment_offset = flags_fragment & 0x1FFF
    dont_fragment = (flags_fragment & 0x4000 != 0)
    more_fragments = (flags_fragment & 0x2000 != 0)
    # If there are options, parse them
    if ihl > 20:
        raise NotImplementedError("Unable to handle packets with options!")
    payload = data[20:]
    return ip_packet(
        src_addr,
        dst_addr,
        payload,
        version,
        tos,
        ident,
        dont_fragment,
        more_fragments,
        flags_fragment,
        ttl,
        protocol,
    )


class icmp_datagram(object):
    """ base ICMP Datagram packet """
    packet_type = None

    def __init__(self, code=0, checksum=0, data="", unpack=False):
        self.code = code
        self.checksum = checksum
        self.data = data
        if unpack:
            self.unpack()

    def calc_checksum(self, data=""):
        if not data:
            self.checksum = 0
            data = struct.pack(
                "!BBH{:d}s".format(
                    len(self.data)
                ),
                self.packet_type,
                self.code,
                self.checksum,
                self.data
            )
            self.checksum = _checksum(data)
        else:
            return _checksum(data)

    def packed(self):
        self.calc_checksum()
        return struct.pack(
            "!BBH{:d}s".format(
                len(self.data)
            ),
            self.packet_type,
            self.code,
            socket.htons(self.checksum),
            self.data
        )

    def unpack(self):
        pass


class icmp_echo(icmp_datagram):
    """ ICMP echo datagram """
    packet_type = 8

    def __init__(self, code=0, checksum=0, data="", ident=0, seqno=0, unpack=False):
        """ An icmp_echo datagram has additional fields to a base datagram:
        @param ident: An identifier used for matching echos
        with replies, may be zero.
        @param seqno: A sequence number, also handy for matching
        with replies. """
        self.ident = ident
        self.seqno = seqno
        if not data:
            data = "icmp echo testdata"
        if unpack:
            icmp_datagram.__init__(self, code, checksum, data, unpack)
        else:
            payload = struct.pack(
                "!hh{:d}s".format(
                    len(data)
                ),
                self.ident,
                self.seqno,
                data
            )
            icmp_datagram.__init__(self, code, checksum, payload, unpack)

    def unpack(self):
        ident, seqno = struct.unpack("!hh", self.data[:4])
        self.ident = ident
        self.seqno = seqno
        self.data = self.data[:8]


class icmp_echo_reply(icmp_datagram):
    """ ICMP echo eeply datagram """
    packet_type = 0

    def unpack(self):
        self.ident, self.seqno = struct.unpack("!hh", self.data[:4])
        self.data = self.data[:8]


class icmp_destination_unreachable(icmp_datagram):
    """ remote destination was unreachable """
    packet_type = 3
    code_dict = {
        0: "Network unreachable",
        1: "Host unreachable",
        2: "Protocol unreachable",
        3: "Port unreachable",
        4: "Datagram too big",
        5: "Source route failed",
        6: "Destination network unknown",
        7: "Destination host unknown",
        8: "Source host isolated",
        9: "Destination network is administratively prohibited",
        10: "Destination host is administratively prohibited",
        11: "Network unreachable for Type of Service",
        12: "Host unreachable for Type of Service",
        13: "Communication administratively prohibited",
        14: "Host precedence violation",
        15: "Precedence cutoff in effect"
    }

    def __repr__(self):
        return self.code_dict.get(self.code, "Unknown error code '{}'".format(self.code))

    def unpack(self):
        self.original_ippacket = _parse_ip_packet(self.data[4:])


class icmp_protocol(object):  # protocol.AbstractDatagramProtocol):
    def __init__(self, **kwargs):
        # start at seqno 32
        self.echo_seqno = 32L
        self._log_errors = hasattr(self, "log")
        self.socket = None
        self.__last_key_error = None
        self.__key_error_num = 0
        self.t_dict = {}

    def init_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)

    def close(self):
        self.socket.close()

    def datagram_received(self, datagram, addr):
        recv_time = time.time()
        parsed_dgram = self.parse_datagram(datagram)
        # if parsed_dgram.seqno in self.t_dict:
        #    print "*", recv_time - self.t_dict[parsed_dgram.seqno]
        # print time.time() - s_time
        # can be none because of error
        if parsed_dgram is not None:
            self.received(parsed_dgram, recv_time=recv_time)

    def received(self, dgram, **kwargs):
        """ to be overwritten """
        print("received datagram", dgram)

    def parse_datagram(self, datagram):
        packet = _parse_ip_packet(datagram)
        header = packet.payload[:4]
        data = packet.payload[4:]
        packet_type, code, checksum = struct.unpack("!BBH", header)
        chkdata = struct.pack("!BBH{:d}s".format(len(data)), packet_type, code, 0, data)
        chk = socket.htons(_checksum(chkdata))
        # init dgram
        if checksum != chk:
            err_str = "Checksum mismatch: {:d} != {:d}".format(checksum, chk)
            if self._log_errors:
                self.log(err_str, logging_tools.LOG_LEVEL_CRITICAL)
                dgram = None
            else:
                raise ValueError(err_str)
        else:
            type_lut_dict = {
                0: icmp_echo_reply,
                3: icmp_destination_unreachable,
                8: icmp_echo
            }
            try:
                dgram = type_lut_dict[int(packet_type)](code, checksum, data, unpack=True)
            except KeyError:
                dgram = None
                self.__key_error_num += 1
                act_time = time.time()
                if self.__last_key_error is None or abs(act_time - self.__last_key_error) > 2:
                    err_str = "Decoding of type '{:d}' datagrams not supported (counted: {:d})".format(packet_type, self.__key_error_num)
                    if self._log_errors:
                        self.log(err_str, logging_tools.LOG_LEVEL_CRITICAL)
                    else:
                        raise NotImplementedError(err_str)
                    self.__last_key_error = act_time
                    self.__key_error_num = 0
            except struct.error:
                dgram = None
                self.log("error decoding raw data (len was {:d})".format(len(data)), logging_tools.LOG_LEVEL_ERROR)
        return dgram

    def send_echo(self, addr, data="init.at NOCTUA/CORVUS ping data", ident=None):
        self.echo_seqno = (self.echo_seqno + 1) & 0x7fff
        if ident is None:
            ident = os.getpid() & 0x7FFF
        dgram = icmp_echo(data=data, ident=ident, seqno=self.echo_seqno)
        s_time = time.time()
        self.socket.sendto(dgram.packed(), (str(addr), 0))
