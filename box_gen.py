#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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

""" draws nested boxes """

class div_box(object):
    def __init__(self, **args):
        self.__childs = []
        self.__cls = args.get("cls", "")
        self.__next_right = args.get("next_right", True)
        self.__size = {"x" : args.get("width", 0),
                       "y" : args.get("height", 0)}
        if args.get("blind", False):
            self.__inner_space = args.get("inner_space", 0)
            self.__outer_space = 0
            self.__border_size = 0
        else:
            self.__inner_space = args.get("inner_space", 1)
            self.__border_size = args.get("border_size", 1)
            self.__outer_space = args.get("outer_space", 0)
        # space for content
        self.__top_space = args.get("top_space", 0)
        self.__content = args.get("content", "")
        self.__position = args.get("position", "absolute")
        if args.has_key("childs"):
            self.set_childs(args["childs"])
    def set_childs(self, childs):
        self.__childs = childs
    def next_is_right(self):
        return self.__next_right
    def set_pos(self, act_p):
        self.__pos = {"x" : act_p["x"] + self.__outer_space,
                      "y" : act_p["y"] + self.__outer_space}
    def layout(self):
        act_size = {"x" : 0,
                    "y" : 0}
        in_s = self.__inner_space
        corner_pos = {"x" : in_s,
                      "y" : in_s + self.__top_space}
        self.__pos = {"x" : 0,
                      "y" : 0}
        if self.__childs:
            nc_right = False
            for child in self.__childs:
                child.layout()
                sub_size = child._get_size()
                child.set_pos(corner_pos)
                if nc_right:
                    act_size["x"] += sub_size["x"] + 2 * in_s
                    act_size["y"] = max(act_size["y"], sub_size["y"] + 2 * in_s)
                else:
                    act_size["x"] = max(act_size["x"], sub_size["x"] + 2 * in_s)
                    act_size["y"] += sub_size["y"] + 2 * in_s
                nc_right = child.next_is_right()
                if nc_right:
                    corner_pos["x"] += sub_size["x"] + 2 * in_s
                else:
                    corner_pos["y"] += sub_size["y"] + 2 * in_s
            act_size["y"] += self.__top_space
        else:
            act_size = self.__size
        self.__act_size = act_size
    def _get_size(self):
        return {"x" : self.__act_size["x"] + 2 * self.__outer_space + 2 * self.__border_size,
                "y" : self.__act_size["y"] + 2 * self.__outer_space + 2 * self.__border_size}
    def get_style_string(self):
        s_dict = {"width"  : "%dpx" % (self.__act_size["x"]),
                  "height" : "%dpx" % (self.__act_size["y"]),
                  "left"   : "%dpx" % (self.__pos["x"]),
                  "top"    : "%dpx" % (self.__pos["y"]),
                  "border" : "%dpx solid" % (self.__border_size),
                  "text-align" : "center",
                  "valign" : "top"}
        return "; ".join(["%s:%s" % (key, value) for key, value in s_dict.iteritems()])
    def get_lines(self, level=0):
        ind_str = "  " * level
        act_lines = ["%s<div%s style=\"position:%s; %s;\">%s" % (ind_str,
                                                                 " class=\"%s\"" % (self.__cls) if self.__cls else "",
                                                                 self.__position,
                                                                 self.get_style_string(),
                                                                 self.__content)]
        for child in self.__childs:
            act_lines.extend(child.get_lines(level + 1))
        act_lines.append("%s</div>" % (ind_str))
        return act_lines

def main():
    cpu_core_width = 32
    cpu_core_height = 32
    sockets = 5
    dies_per_socket = 3
    cores_per_die = 1
    socket_divs = [div_box(cls="cpusocket",
                           inner_space=2,
                           top_space=12,
                           content="Socket%d" % (sock_num)) for sock_num in xrange(sockets)]
    for socket_div in socket_divs:
        die_divs = [div_box(cls="cpudie",
                            inner_space=1,
                            content="die%d" % (die_num),
                            top_space=12) for die_num in xrange(dies_per_socket)]
        socket_div.set_childs(die_divs)
        for die_div in die_divs:
            core_divs = [div_box(cls="cpucore", width=cpu_core_width,
                                 height=cpu_core_height,
                                 content="core%d" % (core_num)) for core_num in xrange(cores_per_die)]
            cache_div = div_box(cls="cpucache",
                                width=(cpu_core_width + 4) * cores_per_die - 2,
                                height=20,
                                content="cache")
            die_div.set_childs([div_box(blind=True,
                                        inner_space=1,
                                        childs=core_divs,
                                        next_right=False),
                                cache_div])
    cpu_b = div_box(position="relative",
                    childs=socket_divs,
                    top_space=14,
                    content="System")
    cpu_b.layout()
    print "\n".join(cpu_b.get_lines())

if __name__ == "__main__":
    main()
