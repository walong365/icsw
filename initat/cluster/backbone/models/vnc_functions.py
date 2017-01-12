# Copyright (C) 2012-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
# -*- coding: utf-8 -*-
#
# Modified DES required by vnc

#  D3DES (V5.09) -
#
#  A portable, public domain, version of the Data Encryption Standard.
#
#  Written with Symantec's THINK (Lightspeed) C by Richard Outerbridge.
#  Thanks to: Dan Hoey for his excellent Initial and Inverse permutation
#  code;  Jim Gillogly & Phil Karn for the DES key schedule code; Dennis
#  Ferguson, Eric Young and Dana How for comparing notes; and Ray Lau,
#  for humouring me on.
#
#  Copyright (c) 1988,1989,1990,1991,1992 by Richard Outerbridge.
#  (GEnie : OUTER; CIS : [71755,204]) Graven Imagery, 1992.
#


import pdb
import sys
from struct import pack, unpack


__all__ = [
    "ForkedPdb",
    "desfunc",
    "deskey",
    "get_vnc_enc",
]


# vnc des key
vnckey = [23, 82, 107, 6, 35, 78, 88, 7]

# strange des adaption
# bytebit = [ 0200, 0100, 040, 020, 010, 04, 02, 01 ] # original
bytebit = [0o1, 0o2, 0o4, 0o10, 0o20, 0o40, 0o100, 0o200]  # VNC version


bigbyte = [
    0x800000, 0x400000, 0x200000, 0x100000,
    0x80000, 0x40000, 0x20000, 0x10000,
    0x8000, 0x4000, 0x2000, 0x1000,
    0x800, 0x400, 0x200, 0x100,
    0x80, 0x40, 0x20, 0x10,
    0x8, 0x4, 0x2, 0x1
]

# Use the key schedule specified in the Standard (ANSI X3.92-1981).

pc1 = [
    56, 48, 40, 32, 24, 16, 8, 0, 57, 49, 41, 33, 25, 17,
    9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35,
    62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37, 29, 21,
    13, 5, 60, 52, 44, 36, 28, 20, 12, 4, 27, 19, 11, 3
]

totrot = [1, 2, 4, 6, 8, 10, 12, 14, 15, 17, 19, 21, 23, 25, 27, 28]

pc2 = [
    13, 16, 10, 23, 0, 4, 2, 27, 14, 5, 20, 9,
    22, 18, 11, 3, 25, 7, 15, 6, 26, 19, 12, 1,
    40, 51, 30, 36, 46, 54, 29, 39, 50, 44, 32, 47,
    43, 48, 38, 55, 33, 52, 45, 41, 49, 35, 28, 31
]


def deskey(key, decrypt):      # Thanks to James Gillogly & Phil Karn!
    key = unpack('8B', key.encode("ascii"))

    pc1m = [0] * 56
    pcr = [0] * 56
    kn = [0] * 32
  
    for j in range(56):
        l = pc1[j]
        m = l & 0o7
        if key[l >> 3] & bytebit[m]:
            pc1m[j] = 1
        else:
            pc1m[j] = 0

    for i in range(16):
        if decrypt:
            m = (15 - i) << 1
        else:
            m = i << 1
        n = m + 1
        kn[m] = kn[n] = 0
        for j in range(28):
            l = j + totrot[i]
            if l < 28:
                pcr[j] = pc1m[l]
            else:
                pcr[j] = pc1m[l - 28]
        for j in range(28, 56):
            l = j + totrot[i]
            if l < 56:
                pcr[j] = pc1m[l]
            else:
                pcr[j] = pc1m[l - 28]
        for j in range(24):
            if pcr[pc2[j]]:
                kn[m] |= bigbyte[j]
            if pcr[pc2[j + 24]]:
                kn[n] |= bigbyte[j]

    return cookey(kn)


def cookey(raw):
    key = []
    for i in range(0, 32, 2):
        (raw0, raw1) = (raw[i], raw[i + 1])
        k = (raw0 & 0x00fc0000) << 6
        k |= (raw0 & 0x00000fc0) << 10
        k |= (raw1 & 0x00fc0000) >> 10
        k |= (raw1 & 0x00000fc0) >> 6
        key.append(k)
        k = (raw0 & 0x0003f000) << 12
        k |= (raw0 & 0x0000003f) << 16
        k |= (raw1 & 0x0003f000) >> 4
        k |= (raw1 & 0x0000003f)
        key.append(k)
    return key

SP1 = [
    0x01010400, 0x00000000, 0x00010000, 0x01010404,
    0x01010004, 0x00010404, 0x00000004, 0x00010000,
    0x00000400, 0x01010400, 0x01010404, 0x00000400,
    0x01000404, 0x01010004, 0x01000000, 0x00000004,
    0x00000404, 0x01000400, 0x01000400, 0x00010400,
    0x00010400, 0x01010000, 0x01010000, 0x01000404,
    0x00010004, 0x01000004, 0x01000004, 0x00010004,
    0x00000000, 0x00000404, 0x00010404, 0x01000000,
    0x00010000, 0x01010404, 0x00000004, 0x01010000,
    0x01010400, 0x01000000, 0x01000000, 0x00000400,
    0x01010004, 0x00010000, 0x00010400, 0x01000004,
    0x00000400, 0x00000004, 0x01000404, 0x00010404,
    0x01010404, 0x00010004, 0x01010000, 0x01000404,
    0x01000004, 0x00000404, 0x00010404, 0x01010400,
    0x00000404, 0x01000400, 0x01000400, 0x00000000,
    0x00010004, 0x00010400, 0x00000000, 0x01010004
]

SP2 = [
    0x80108020, 0x80008000, 0x00008000, 0x00108020,
    0x00100000, 0x00000020, 0x80100020, 0x80008020,
    0x80000020, 0x80108020, 0x80108000, 0x80000000,
    0x80008000, 0x00100000, 0x00000020, 0x80100020,
    0x00108000, 0x00100020, 0x80008020, 0x00000000,
    0x80000000, 0x00008000, 0x00108020, 0x80100000,
    0x00100020, 0x80000020, 0x00000000, 0x00108000,
    0x00008020, 0x80108000, 0x80100000, 0x00008020,
    0x00000000, 0x00108020, 0x80100020, 0x00100000,
    0x80008020, 0x80100000, 0x80108000, 0x00008000,
    0x80100000, 0x80008000, 0x00000020, 0x80108020,
    0x00108020, 0x00000020, 0x00008000, 0x80000000,
    0x00008020, 0x80108000, 0x00100000, 0x80000020,
    0x00100020, 0x80008020, 0x80000020, 0x00100020,
    0x00108000, 0x00000000, 0x80008000, 0x00008020,
    0x80000000, 0x80100020, 0x80108020, 0x00108000
]

SP3 = [
    0x00000208, 0x08020200, 0x00000000, 0x08020008,
    0x08000200, 0x00000000, 0x00020208, 0x08000200,
    0x00020008, 0x08000008, 0x08000008, 0x00020000,
    0x08020208, 0x00020008, 0x08020000, 0x00000208,
    0x08000000, 0x00000008, 0x08020200, 0x00000200,
    0x00020200, 0x08020000, 0x08020008, 0x00020208,
    0x08000208, 0x00020200, 0x00020000, 0x08000208,
    0x00000008, 0x08020208, 0x00000200, 0x08000000,
    0x08020200, 0x08000000, 0x00020008, 0x00000208,
    0x00020000, 0x08020200, 0x08000200, 0x00000000,
    0x00000200, 0x00020008, 0x08020208, 0x08000200,
    0x08000008, 0x00000200, 0x00000000, 0x08020008,
    0x08000208, 0x00020000, 0x08000000, 0x08020208,
    0x00000008, 0x00020208, 0x00020200, 0x08000008,
    0x08020000, 0x08000208, 0x00000208, 0x08020000,
    0x00020208, 0x00000008, 0x08020008, 0x00020200
]

SP4 = [
    0x00802001, 0x00002081, 0x00002081, 0x00000080,
    0x00802080, 0x00800081, 0x00800001, 0x00002001,
    0x00000000, 0x00802000, 0x00802000, 0x00802081,
    0x00000081, 0x00000000, 0x00800080, 0x00800001,
    0x00000001, 0x00002000, 0x00800000, 0x00802001,
    0x00000080, 0x00800000, 0x00002001, 0x00002080,
    0x00800081, 0x00000001, 0x00002080, 0x00800080,
    0x00002000, 0x00802080, 0x00802081, 0x00000081,
    0x00800080, 0x00800001, 0x00802000, 0x00802081,
    0x00000081, 0x00000000, 0x00000000, 0x00802000,
    0x00002080, 0x00800080, 0x00800081, 0x00000001,
    0x00802001, 0x00002081, 0x00002081, 0x00000080,
    0x00802081, 0x00000081, 0x00000001, 0x00002000,
    0x00800001, 0x00002001, 0x00802080, 0x00800081,
    0x00002001, 0x00002080, 0x00800000, 0x00802001,
    0x00000080, 0x00800000, 0x00002000, 0x00802080
]

SP5 = [
    0x00000100, 0x02080100, 0x02080000, 0x42000100,
    0x00080000, 0x00000100, 0x40000000, 0x02080000,
    0x40080100, 0x00080000, 0x02000100, 0x40080100,
    0x42000100, 0x42080000, 0x00080100, 0x40000000,
    0x02000000, 0x40080000, 0x40080000, 0x00000000,
    0x40000100, 0x42080100, 0x42080100, 0x02000100,
    0x42080000, 0x40000100, 0x00000000, 0x42000000,
    0x02080100, 0x02000000, 0x42000000, 0x00080100,
    0x00080000, 0x42000100, 0x00000100, 0x02000000,
    0x40000000, 0x02080000, 0x42000100, 0x40080100,
    0x02000100, 0x40000000, 0x42080000, 0x02080100,
    0x40080100, 0x00000100, 0x02000000, 0x42080000,
    0x42080100, 0x00080100, 0x42000000, 0x42080100,
    0x02080000, 0x00000000, 0x40080000, 0x42000000,
    0x00080100, 0x02000100, 0x40000100, 0x00080000,
    0x00000000, 0x40080000, 0x02080100, 0x40000100
]

SP6 = [
    0x20000010, 0x20400000, 0x00004000, 0x20404010,
    0x20400000, 0x00000010, 0x20404010, 0x00400000,
    0x20004000, 0x00404010, 0x00400000, 0x20000010,
    0x00400010, 0x20004000, 0x20000000, 0x00004010,
    0x00000000, 0x00400010, 0x20004010, 0x00004000,
    0x00404000, 0x20004010, 0x00000010, 0x20400010,
    0x20400010, 0x00000000, 0x00404010, 0x20404000,
    0x00004010, 0x00404000, 0x20404000, 0x20000000,
    0x20004000, 0x00000010, 0x20400010, 0x00404000,
    0x20404010, 0x00400000, 0x00004010, 0x20000010,
    0x00400000, 0x20004000, 0x20000000, 0x00004010,
    0x20000010, 0x20404010, 0x00404000, 0x20400000,
    0x00404010, 0x20404000, 0x00000000, 0x20400010,
    0x00000010, 0x00004000, 0x20400000, 0x00404010,
    0x00004000, 0x00400010, 0x20004010, 0x00000000,
    0x20404000, 0x20000000, 0x00400010, 0x20004010
]

SP7 = [
    0x00200000, 0x04200002, 0x04000802, 0x00000000,
    0x00000800, 0x04000802, 0x00200802, 0x04200800,
    0x04200802, 0x00200000, 0x00000000, 0x04000002,
    0x00000002, 0x04000000, 0x04200002, 0x00000802,
    0x04000800, 0x00200802, 0x00200002, 0x04000800,
    0x04000002, 0x04200000, 0x04200800, 0x00200002,
    0x04200000, 0x00000800, 0x00000802, 0x04200802,
    0x00200800, 0x00000002, 0x04000000, 0x00200800,
    0x04000000, 0x00200800, 0x00200000, 0x04000802,
    0x04000802, 0x04200002, 0x04200002, 0x00000002,
    0x00200002, 0x04000000, 0x04000800, 0x00200000,
    0x04200800, 0x00000802, 0x00200802, 0x04200800,
    0x00000802, 0x04000002, 0x04200802, 0x04200000,
    0x00200800, 0x00000000, 0x00000002, 0x04200802,
    0x00000000, 0x00200802, 0x04200000, 0x00000800,
    0x04000002, 0x04000800, 0x00000800, 0x00200002
]

SP8 = [
    0x10001040, 0x00001000, 0x00040000, 0x10041040,
    0x10000000, 0x10001040, 0x00000040, 0x10000000,
    0x00040040, 0x10040000, 0x10041040, 0x00041000,
    0x10041000, 0x00041040, 0x00001000, 0x00000040,
    0x10040000, 0x10000040, 0x10001000, 0x00001040,
    0x00041000, 0x00040040, 0x10040040, 0x10041000,
    0x00001040, 0x00000000, 0x00000000, 0x10040040,
    0x10000040, 0x10001000, 0x00041040, 0x00040000,
    0x00041040, 0x00040000, 0x10041000, 0x00001000,
    0x00000040, 0x10040040, 0x00001000, 0x00041040,
    0x10001000, 0x00000040, 0x10000040, 0x10040000,
    0x10040040, 0x10000000, 0x00040000, 0x10001040,
    0x00000000, 0x10041040, 0x00040040, 0x10000040,
    0x10040000, 0x10001000, 0x10001040, 0x00000000,
    0x10041040, 0x00041000, 0x00041000, 0x00001040,
    0x00001040, 0x00040040, 0x10000000, 0x10041000
]


def desfunc(block, keys):
    (left, right) = unpack('>II', block.encode("ascii"))
  
    work = ((left >> 4) ^ right) & 0x0f0f0f0f
    right ^= work
    left ^= (work << 4)
    work = ((left >> 16) ^ right) & 0x0000ffff
    right ^= work
    left ^= (work << 16)
    work = ((right >> 2) ^ left) & 0x33333333
    left ^= work
    right ^= (work << 2)
    work = ((right >> 8) ^ left) & 0x00ff00ff
    left ^= work
    right ^= (work << 8)
    right = ((right << 1) | ((right >> 31) & 1)) & 0xffffffff
    work = (left ^ right) & 0xaaaaaaaa
    left ^= work
    right ^= work
    left = ((left << 1) | ((left >> 31) & 1)) & 0xffffffff

    for i in range(0, 32, 4):
        work = (right << 28) | (right >> 4)
        work ^= keys[i]
        fval = SP7[work & 0x3f]
        fval |= SP5[(work >> 8) & 0x3f]
        fval |= SP3[(work >> 16) & 0x3f]
        fval |= SP1[(work >> 24) & 0x3f]
        work = right ^ keys[i + 1]
        fval |= SP8[work & 0x3f]
        fval |= SP6[(work >> 8) & 0x3f]
        fval |= SP4[(work >> 16) & 0x3f]
        fval |= SP2[(work >> 24) & 0x3f]
        left ^= fval
        work = (left << 28) | (left >> 4)
        work ^= keys[i + 2]
        fval = SP7[work & 0x3f]
        fval |= SP5[(work >> 8) & 0x3f]
        fval |= SP3[(work >> 16) & 0x3f]
        fval |= SP1[(work >> 24) & 0x3f]
        work = left ^ keys[i + 3]
        fval |= SP8[work & 0x3f]
        fval |= SP6[(work >> 8) & 0x3f]
        fval |= SP4[(work >> 16) & 0x3f]
        fval |= SP2[(work >> 24) & 0x3f]
        right ^= fval

    right = (right << 31) | (right >> 1)
    work = (left ^ right) & 0xaaaaaaaa
    left ^= work
    right ^= work
    left = (left << 31) | (left >> 1)
    work = ((left >> 8) ^ right) & 0x00ff00ff
    right ^= work
    left ^= (work << 8)
    work = ((left >> 2) ^ right) & 0x33333333
    right ^= work
    left ^= (work << 2)
    work = ((right >> 16) ^ left) & 0x0000ffff
    left ^= work
    right ^= (work << 16)
    work = ((right >> 4) ^ left) & 0x0f0f0f0f
    left ^= work
    right ^= (work << 4)

    left &= 0xffffffff
    right &= 0xffffffff
    return pack('>II', right, left)


def get_vnc_enc(password):
    passpadd = (password + '\x00' * 8)[:8]
    strkey = ''.join([chr(x) for x in vnckey])
    ekey = deskey(strkey, False)

    ctext = desfunc(passpadd, ekey)
    return ctext.hex()


class ForkedPdb(pdb.Pdb):
    """
    A Pdb subclass that may be used
    from a forked multiprocessing child

    """
    def interaction(self, *args, **kwargs):
        _stdin = sys.stdin
        try:
            sys.stdin = open('/dev/stdin')
            pdb.Pdb.interaction(self, *args, **kwargs)
        finally:
            sys.stdin = _stdin
