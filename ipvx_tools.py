#!/usr/bin/python -Ot
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
""" handles ipv4 addresses """

import sys

class ipv4(object):
    def __init__(self, in_value):
        # cast tuple to list
        if type(in_value) in [long, int]:
            in_value = list(in_value)
        if type(in_value) in [str, unicode]:
            # value is a string
            if len([x for x in [int(y) for y in in_value.strip().split(".") if y.isdigit()] if x >=0 and x <= 255]) == 4:
                self.parts = [int(y) for y in in_value.strip().split(".")]
                self.inv_parts = [x for x in self.parts]
                self.inv_parts.reverse()
                #print "+",in_value, self.parts, self.inv_parts, "*<br>"
            else:
                raise ValueError
        elif type(in_value) == type([]):
            if type(in_value[0]) in [type(0), type(0L)]:
                # value is a list of integer
                self.parts = [val for val in in_value]
            else:
                # value is a list of strings
                self.parts = [int(val) for val in in_value]
            self.inv_parts = [x for x in self.parts]
            self.inv_parts.reverse()
        else:
            # value is an integer
            self.inv_parts = []
            for idx in range(4):
                self.inv_parts.append(in_value & 255)
                in_value = in_value >> 8
            self.parts = [x for x in self.inv_parts]
            self.parts.reverse()
    def value(self):
        bin_ip, mult = (0, 1)
        for idx in range(4):
            bin_ip += self.inv_parts[idx] * mult
            mult = mult * 256
        return bin_ip
    def netmask_bits(self):
        bin_mask = self.value()
        if bin_mask:
            bits = 32
            while (not (bin_mask & 1)) and bin_mask:
                bits -= 1
                bin_mask = bin_mask/2
        else:
            bits = 0
        return bits
    def __str__(self):
        return ".".join([str(y) for y in self.parts])
    def __repr__(self):
        return ".".join([str(y) for y in self.parts])
    def __len__(self):
        return len(str(self))
    def __invert__(self):
        return ipv4(".".join([str(255 - x) for x in self.parts]))
    def __and__(self, other):
        return ipv4(".".join([str(x & y) for x, y in zip(self.parts, other.parts)]))
    def __or__(self, other):
        return ipv4(".".join([str(x | y) for x, y in zip(self.parts, other.parts)]))
    def __eq__(self, other):
        return len([True for x, y in zip(self.parts, other.parts) if x == y]) == 4
    def __ne__(self, other):
        return len([True for x, y in zip(self.parts, other.parts) if x == y]) != 4
    def __add__(self, other):
        ov = 0
        new_v = [0] * 4
        for i in range(3, -1, -1):
            new_val = self.parts[i] + other.parts[i] + ov
            ov = 0
            while new_val > 255:
                new_val -= 256
                ov += 1
            new_v[i] = new_val
        if ov:
            raise ValueError, "Overflow while adding IPv4 addresses %s and %s" % (str(self), str(other))
        else:
            return ipv4(".".join([str(x) for x in new_v]))
    def __lt__(self, other):
        for i in range(4):
            if self.parts[i] > other.parts[i]:
                return False
            elif self.parts[i] < other.parts[i]:
                return True
        return False
    def __gt__(self, other):
        for i in range(4):
            if self.parts[i] < other.parts[i]:
                return False
            elif self.parts[i] > other.parts[i]:
                return True
        return False
    def __le__(self, other):
        for i in range(4):
            if self.parts[i] > other.parts[i]:
                return False
            elif self.parts[i] < other.parts[i]:
                return True
        return True
    def __ge__(self, other):
        for i in range(4):
            if self.parts[i] < other.parts[i]:
                return False
            elif self.parts[i] > other.parts[i]:
                return True
        return True
    def find_matching_network(self, nw_list):
        match_list = []
        for nw_stuff in nw_list:
            network, netmask = (ipv4(nw_stuff.network), ipv4(nw_stuff.netmask))
            if self & netmask == network:
                match_list.append((netmask.netmask_bits(), nw_stuff))
        return sorted(match_list, reverse=True)
    def network_matches(self, nw_stuff):
        print self & ipv4(nw_stuff.netmask), ipv4(nw_stuff.network)
        return self & ipv4(nw_stuff.netmask) == ipv4(nw_stuff.network)

def get_network_name_from_mask(mask):
    return {"255.255.255.0" : "C",
            "255.255.0.0"   : "B",
            "255.0.0.0"     : "A"}.get(mask, mask)

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
