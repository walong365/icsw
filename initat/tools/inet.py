"""Internet packet basic

Simple operations like performing checksums and swapping byte orders.
"""

# Copyright 1997, Corporation for National Research Initiatives
# written by Jeremy Hylton, jeremy@cnri.reston.va.us
# from _ip import *

import array
import struct
from socket import htons, ntohs


def cksum(s):
    if len(s) & 1:
        s += '\0'
    words = array.array('h', s)
    _sum = 0
    for word in words:
        _sum += word & 0xffff
    hi = _sum >> 16
    lo = _sum & 0xffff
    _sum = hi + lo
    _sum += _sum >> 16
    return (~_sum) & 0xffff

# Should generalize from the *h2net patterns

# This python code is suboptimal because it is based on C code where
# it doesn't cost much to take a raw buffer and treat a section of it
# as a u_short.


def gets(s):
    return struct.unpack('H', s)[0] & 0xffff


def mks(h):
    return struct.pack('H', h)


def iph2net(s):
    _len = htons(gets(s[2:4]))
    _id = htons(gets(s[4:6]))
    off = htons(gets(s[6:8]))
    return s[:2] + mks(_len) + mks(_id) + mks(off) + s[8:]


def net2iph(s):
    _len = ntohs(gets(s[2:4]))
    _id = ntohs(gets(s[4:6]))
    off = ntohs(gets(s[6:8]))
    return s[:2] + mks(_len) + mks(_id) + mks(off) + s[8:]


def udph2net(s):
    sp = htons(gets(s[0:2]))
    dp = htons(gets(s[2:4]))
    _len = htons(gets(s[4:6]))
    return mks(sp) + mks(dp) + mks(_len) + s[6:]


def net2updh(s):
    sp = ntohs(gets(s[0:2]))
    dp = ntohs(gets(s[2:4]))
    _len = ntohs(gets(s[4:6]))
    return mks(sp) + mks(dp) + mks(_len) + s[6:]
