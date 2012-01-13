#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
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
""" for graph drawing """

try:
    import gd
except ImportError:
    raise
import os
import stat
import time
import process_tools

font_name = "/usr/share/rrdtool/fonts/DejaVuSansMono-Roman.ttf"

def get_rgb_val(p_val, c_path):
    # p_val from 0 to 100, hits color_path_vars
    # determine correct color_path_pair
    try:
        num_c_path = len(c_path)
        if num_c_path == 1:
            # single color
            return c_path[0]
        elif p_val >= 100.0:
            return c_path[-1]
        else:
            divs = 100. / float(num_c_path - 1)
            first_idx = int(p_val / divs)
            if first_idx == num_c_path:
                # in case of p_val == 100.0
                first_idx -= 1
            # correct p_val
            p_val_c = (p_val - first_idx * divs) * 100 / divs
            s_rgb = [int(c_path[first_idx][0:2], 16),
                     int(c_path[first_idx][2:4], 16),
                     int(c_path[first_idx][4:6], 16)]
            e_rgb = [int(c_path[first_idx + 1][0:2], 16),
                     int(c_path[first_idx + 1][2:4], 16),
                     int(c_path[first_idx + 1][4:6], 16)]
            return "".join(["%02x" % ((s * 100 + p_val_c * (e - s)) / 100) for s, e in zip(s_rgb, e_rgb)])
    except:
        raise ValueError, "Cannot create colorpath: p_val=%s, c_path=%s" % (str(p_val),
                                                                            str(c_path))
    
def to_rgb_tuple(val):
    return (int(val[0:2], 16),
            int(val[2:4], 16),
            int(val[4:6], 16))

class info_graph(object):
    def __init__(self, target_dir):
        self.__target_dir = target_dir
        self.__in_dict = {}
        self.__idx = 0
        self.clear_target_dir()
    def clear_target_dir(self):
        act_time = time.time()
        for entry in os.listdir(self.__target_dir):
            f_path = "%s/%s" % (self.__target_dir, entry)
            if abs(act_time - os.stat(f_path)[stat.ST_MTIME]) > 60:
                try:
                    os.unlink(f_path)
                except:
                    pass
    def __setitem__(self, key, val):
        self.__in_dict[key] = val
    def __getitem__(self, key):
        return self.__in_dict[key]
    def __delitem__(self, key):
        del self.__in_dict[key]
    def create_graph(self, name, draw_vals):
        self.__idx += 1
        x_size, y_size = (self.__in_dict.get("width", 100),
                          self.__in_dict.get("height", 20))
        im = gd.image((x_size, y_size))
        white_color = im.colorAllocate((255, 255, 255))
        black_color = im.colorAllocate((255, 255, 255))
        im.colorTransparent(white_color)
        im.interlace(1)
        # drawing size
        d_xs, d_ys = (0, 0)
        d_xe, d_ye = (x_size - 1, y_size - 1)
        if self.__in_dict.has_key("bgcolor"):
            im.filledRectangle((0, 0), (d_xe, d_ye), im.colorAllocate(to_rgb_tuple(self.__in_dict["bgcolor"])))
        if self.__in_dict.has_key("bordercolor"):
            im.rectangle((0, 0), (d_xe, d_ye), im.colorAllocate(to_rgb_tuple(self.__in_dict["bordercolor"])))
        if self.__in_dict.has_key("outlinecolor"):
            outl_color = im.colorAllocate(to_rgb_tuple(self.__in_dict["outlinecolor"]))
        else:
            outl_color = None
        b_size = self.__in_dict.get("bordersize", 0)
        d_xs += b_size
        d_ys += b_size
        d_xe -= b_size
        d_ye -= b_size
        d_width  = d_xe - d_xs
        d_height = d_ye - d_ys
        im_type = self.__in_dict["type"]
        if im_type == "rectgr":
            y_stride = self.__in_dict["ystride"]
            all_k = sorted(draw_vals.keys())
            num_k = len(all_k)
            for offset in all_k:
                length, color = draw_vals[offset]
                im.filledRectangle((d_xs, d_ys + y_stride * offset), (d_xs + int(d_width * length / 100), d_ye - y_stride * (num_k - offset - 1)), im.colorAllocate(to_rgb_tuple(color)))
                if outl_color:
                    im.rectangle((d_xs, d_ys + y_stride * offset), (d_xs + int(d_width * length / 100), d_ye - y_stride * (num_k - offset - 1)), outl_color)
        else:
            im.string_ttf(font_name, (y_size - 2) * 0.8, 0.0, (0, y_size - 1), "ut:%s" % (im_type), black_color)
        self.__act_name = "%s_%s_%d" % (name, self.__in_dict.get("add_name", ""), self.__idx)
        try:
            im.writePng(file("%s/%s" % (self.__target_dir, self.__act_name), "w"))
        except IOError:
            print "An error occured: %s" % (process_tools.get_except_info())
        del im
    def get_last_name(self):
        return self.__act_name
        
