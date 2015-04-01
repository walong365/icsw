#!/usr/bin/python-init -Otu
#
# Copyright (c) 2007 Andreas Lang, init.at
#
# this file is part of module_tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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

import optparse
import sys
import xml_tools
import curses
import curses.wrapper
import curses.textpad
import time

def flash():
    curses.flash()

class gauge_bar(object):
    def __init__(self, win, x_bar=True, **args):
        self.__win = win
        self.__x_bar = x_bar
        self.__act_len, self.__offset = (args.get("act_len", 10),
                                         args.get("offset", 0))
        self._resize()
    def _resize(self):
        if self.__x_bar:
            self.__view_len = self.__win.get_effective_width()
        else:
            self.__view_len = self.__win.get_effective_height()
    def get_offset(self):
        return self.__offset
    def set_offset(self, val):
        self.__offset = val
        self._draw_it()
    offset = property(get_offset, set_offset)
    def get_act_len(self):
        return self.__act_len
    def set_act_len(self, val):
        self.__act_len = val
        self._draw_it()
    act_len = property(get_act_len, set_act_len)
    def shift(self, d_val, test):
        new_offset = max(min(self.offset + d_val, self.act_len - (self.__view_len - 1)), 0)
        if test:
            return new_offset != self.offset
        else:
            self.offset = new_offset
            return True
    def _draw_it(self):
        d_win = self.__win.get_win()
        if self.__act_len:
            n_drawn = min(int((self.__view_len * self.__view_len) / self.__act_len), self.__view_len - 1)
            pre_clean = int((self.__view_len * self.__offset) / self.__act_len)
        else:
            n_drawn, pre_clean = (self.__view_len - 1, 0)
        if self.__x_bar:
            start = self.__win.get_start_x()
            if pre_clean:
                d_win.hline(self.__win.get_effective_height(False), start, " ", pre_clean)
            d_win.attrset(curses.A_REVERSE)
            d_win.hline(self.__win.get_effective_height(False), start + pre_clean, " ", n_drawn)
            d_win.attroff(curses.A_REVERSE)
            if n_drawn + pre_clean < self.__view_len:
                d_win.hline(self.__win.get_effective_height(False), start + pre_clean + n_drawn, " ", self.__view_len - n_drawn - pre_clean)
        else:
            start = self.__win.get_start_y()
            if pre_clean:
                d_win.vline(start, self.__win.get_effective_width(), " ", pre_clean)
            d_win.attrset(curses.A_REVERSE)
            d_win.vline(start + pre_clean, self.__win.get_effective_width(), " ", n_drawn)
            d_win.attroff(curses.A_REVERSE)
            if n_drawn + pre_clean < self.__view_len:
                d_win.vline(start + pre_clean + n_drawn, self.__win.get_effective_width(), " ", self.__view_len - n_drawn - pre_clean)
        
class single_line_input_widget(object):
    def __init__(self, master_win, **args):
        self.__master_win = master_win
        self.__width = args.get("width", curses.COLS - 20)
        self.__win = self.__master_win.derwin(3, self.__width, min(1, curses.LINES / 2), (curses.COLS - self.__width) / 2)
        self.__win.border()
        self.__act_offset = 0
        self.__cursor = 0
        # master_win is a scroll_window
        self.__buffer = args.get("input_buffer", "buffer")
        self.__act_buffer_len = len(self.__buffer) + 1
        self.__max_buffer_len = max(self.__act_buffer_len - 1, args.get("buffer_len", 16))
        self.__valid_chars = args.get("valid_characters", "a0").replace("a", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ").replace("0", "0123456789")
        self._draw_it()
    def get_act_buffer(self):
        return self.__buffer
    def main_loop(self):
        self.__loop_flag = True
        off_y, off_x = self.__win.getparyx()
        while self.__loop_flag:
            act_key = self.__master_win.getch(off_y + 1, off_x + 1 + self.__cursor - self.__act_offset)
            if act_key == curses.KEY_RIGHT:
                if self.__cursor + 1 == self.__act_buffer_len:
                    curses.flash()
                else:
                    self.__cursor += 1
                    if self.__cursor - self.__act_offset == self.__width - 2:
                        self.__act_offset += 1
                        self._draw_it(False)
                    self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                    self.__win.refresh()
            elif act_key == curses.KEY_LEFT:
                if not self.__cursor:
                    curses.flash()
                else:
                    self.__cursor -= 1
                    if self.__cursor < self.__act_offset:
                        self.__act_offset -= 1
                        self._draw_it(False)
                    self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                    self.__win.refresh()
            elif act_key == curses.KEY_HOME:
                if not self.__cursor:
                    curses.flash()
                else:
                    self.__cursor = 0
                    if self.__cursor < self.__act_offset:
                        self.__act_offset = 0
                        self._draw_it(False)
                    self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                    self.__win.refresh()
            elif act_key == curses.KEY_END:
                if self.__cursor + 1 == self.__act_buffer_len:
                    curses.flash()
                else:
                    self.__cursor = self.__act_buffer_len - 1
                    if self.__cursor - self.__act_offset > self.__width - 1:
                        self.__act_offset = self.__cursor - self.__width + 3
                        self._draw_it(False)
                    self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                    self.__win.refresh()
            elif act_key == curses.KEY_BACKSPACE:
                if not self.__cursor:
                    curses.flash()
                else:
                    self.__cursor -= 1
                    if self.__cursor:
                        self.__buffer = "".join([self.__buffer[0 : self.__cursor],
                                                 self.__buffer[self.__cursor + 1 :]])
                    else:
                        self.__buffer = self.__buffer[1:]
                    if self.__cursor < self.__act_offset:
                        self.__act_offset -= 1
                    self._draw_it(False)
                    self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                    self.__win.refresh()
            elif act_key == curses.KEY_DC:
                if self.__cursor:
                    self.__buffer = "".join([self.__buffer[0 : self.__cursor],
                                             self.__buffer[self.__cursor + 1 :]])
                else:
                    self.__buffer = self.__buffer[1:]
                self.__act_buffer_len = len(self.__buffer) + 1
                if self.__cursor < self.__act_offset:
                    self.__act_offset -= 1
                self._draw_it(False)
                self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                self.__win.refresh()
            elif act_key == 10:
                self.__loop_flag = False
            else:
                try:
                    act_chr = chr(act_key)
                except:
                    curses.flash()
                else:
                    if act_chr in self.__valid_chars:
                        if self.__cursor + 1 == self.__max_buffer_len or self.__act_buffer_len >= self.__max_buffer_len:
                            curses.flash()
                        else:
                            if self.__cursor:
                                self.__buffer = "".join([self.__buffer[0 : self.__cursor],
                                                         act_chr,
                                                         self.__buffer[self.__cursor : ]])
                            else:
                                self.__buffer = "".join([act_chr,
                                                         self.__buffer])
                            self.__act_buffer_len = len(self.__buffer) + 1
                            self.__cursor += 1
                            if self.__cursor - self.__act_offset == self.__width - 2:
                                self.__act_offset += 1
                            self._draw_it(False)
                            self.__win.move(1, 1 + self.__cursor - self.__act_offset)
                            self.__win.refresh()
                    else:
                        curses.flash()
    def _draw_it(self, full=True):
        if full:
            self.__win.addstr(0, 1, ("please edit, enter to exit")[0 : self.__width - 1])
        out_str = (self.__buffer[self.__act_offset:] + " " * self.__width)[:self.__width - 2]
        self.__win.addstr(1, 1, out_str)
        self.__win.move(1, 1 + self.__cursor - self.__act_offset)
        self.__win.refresh()
        
class scroll_window(object):
    def __init__(self, master_win, **args):
        self.__master_win = master_win
        self.x_gauge, self.y_gauge = (None, None)
        self._resize(**args)
        self.__win = self.__master_win.derwin(self.__height,
                                              self.__width,
                                              args.get("y_offset", 0),
                                              args.get("x_offset", 0))
        # content type. can be
        # text ....... lines of text
        # list ....... every line is a list of strings, length is padded automatically
        self.__content_type = args.get("content_type", "text")
        self.__headline = args.get("headline", "")
        self.__title = args.get("title", "")
        if args.get("draw_border", True):
            self.__win.border()
        self.x_gauge = gauge_bar(self, True , act_len=200, offset=args.get("x", 0))
        self.y_gauge = gauge_bar(self, False, act_len=200, offset=args.get("y", 0))
        self.__sel_bar = args.get("use_selection_bar", False)
        self.__sel_bar_position = 0
        self.set_buffer([])
    def _resize(self, **args):
        self.__height, self.__width = (args.get("height", curses.LINES),
                                       args.get("width" , curses.COLS ))
        if self.x_gauge:
            self.x_gauge._resize()
            self.y_gauge._resize()
    def get_effective_height(self, with_headline=True):
        if self.__headline and with_headline:
            hl_height = 1
        else:
            hl_height = 0
        return self.__height - (2 + hl_height)
    def get_effective_width(self):
        return self.__width - 2
    def get_start_x(self):
        return 1
    def get_start_y(self):
        if self.__headline:
            return 2
        else:
            return 1
    def get_win(self):
        return self.__win
    def get_master_win(self):
        return self.__master_win
    def get_selection_bar_position(self):
        return self.__sel_bar_position
    def __setitem__(self, l_num, value):
        if l_num is None:
            append = True
        else:
            if len(self.__buffer) > l_num:
                append = False
            else:
                append = True
        if append:
            if type(value) == type([]) and self.__content_type == "text":
                self.__buffer.extend(value)
            else:
                self.__buffer.append(value)
        else:
            self.__buffer[l_num] = value
        self._buffer_resize()
    def set_buffer(self, in_buffer):
        self.__buffer = in_buffer
        self._buffer_resize()
    def _buffer_resize(self):
        self.y_gauge.act_len = len(self.__buffer)
        self.__len_list = []
        if self.y_gauge.act_len:
            if self.__content_type == "text":
                self.x_gauge.act_len = max([len(line) for line in self.__buffer])
            else:
                # calc line lens
                len_matrix = [[len(part) for part in line] for line in self.__buffer + (self.__headline and [self.__headline] or [])]
                if len_matrix:
                    len_idxs = max([len(line) for line in len_matrix])
                    self.__len_list = [max([len(line) > idx and line[idx] or 0 for line in len_matrix]) for idx in xrange(len_idxs)]
                    self.x_gauge.act_len = sum(self.__len_list) + len(self.__len_list) - 1
                else:
                    self.x_gauge.act_len = 0
        else:
            self.x_gauge.act_len = 0
        self._draw_it()
    def feed_move_key(self, act_key):
        dv = None
        if act_key == curses.KEY_DOWN:
            dv = (0, 1)
        elif act_key == curses.KEY_UP:
            dv = (0, -1)
        elif act_key == curses.KEY_LEFT:
            dv = (-1, 0)
        elif act_key == curses.KEY_RIGHT:
            dv = (1, 0)
        elif act_key == curses.KEY_HOME:
            dv = (0, -self.y_gauge.act_len)
        elif act_key == curses.KEY_END:
            dv = (0, self.y_gauge.act_len)
        elif act_key == curses.KEY_NPAGE:
            dv = (0, self.get_effective_height() - 2)
        elif act_key == curses.KEY_PPAGE:
            dv = (0, -(self.get_effective_height() - 2))
        if dv:
            if self.shift(dv, True):
                self.shift(dv)
            else:
                curses.flash()
    def shift(self, dv, test=False):
        dx, dy = dv
        if dx:
            ret_v = self.x_gauge.shift(dx, test)
        else:
            if self.__sel_bar:
                eff_h = self.get_effective_height()
                new_sel_bar_position = max(min(self.__sel_bar_position + dy, self.y_gauge.act_len - 1), 0)
                if test:
                    ret_v = (new_sel_bar_position != self.__sel_bar_position)
                else:
                    self.__sel_bar_position = new_sel_bar_position
                    ret_v = True
                    if new_sel_bar_position > self.y_gauge.offset + eff_h - 2:
                        self.y_gauge.offset = new_sel_bar_position - (eff_h - 2)
                    elif new_sel_bar_position < self.y_gauge.offset:
                        self.y_gauge.offset = new_sel_bar_position
            else:
                ret_v = self.y_gauge.shift(dy, test)
        if not test:
            self._draw_it()
        return ret_v
    def fw_str(self, in_str):
        if self.__content_type == "text":
            pass
        else:
            in_str = " ".join([("%%-%ds" % (max_len)) % (s_part) for s_part, max_len in zip(in_str, self.__len_list)])
        d_width = max(self.x_gauge.act_len, self.__width - 3)
        if len(in_str) < d_width:
            return "%s%s" % (in_str, " " * (d_width - len(in_str)))
        else:
            return in_str
    def _draw_it(self):
        if self.__headline:
            self.__win.addstr(1, 1, (self.fw_str(self.__headline))[self.x_gauge.offset : self.__width + self.x_gauge.offset - 3])
        y_start = self.get_start_y()
        for draw_y in range(y_start, self.__height - 2):
            if draw_y + self.y_gauge.offset - y_start >= self.y_gauge.act_len:
                draw_str = ""
            else:
                draw_str = self.__buffer[draw_y + self.y_gauge.offset - y_start]
            draw_str = (self.fw_str(draw_str))[self.x_gauge.offset : self.__width + self.x_gauge.offset - 3]
            is_sel_line = False
            if self.__sel_bar:
                if draw_y - y_start + self.y_gauge.offset == self.__sel_bar_position:
                    is_sel_line = True
            self.__win.addstr(draw_y, 1, draw_str, is_sel_line and curses.A_REVERSE or 0)
        if self.__title:
            self.__win.addnstr(0, 1, self.__title, curses.COLS - 2)
        #self.__win.addstr(0, 1, "%d / %d / %d    " % (self.x_gauge.act_len, self.x_gauge.offset, self.__width))
        self.__win.move(0, 0)
        self.__win.refresh()
    def main_loop(self, lu_dict, **args):
        move_keys = [curses.KEY_DOWN, curses.KEY_UP, curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_HOME, curses.KEY_END, curses.KEY_NPAGE, curses.KEY_PPAGE]
        self.__loop_flag = True
        while self.__loop_flag:
            act_key = self.__master_win.getch()
            if act_key in move_keys:
                self.feed_move_key(act_key)
            elif act_key == curses.KEY_RESIZE:
                self._resize()
                self._draw_it()
            elif act_key in lu_dict.keys():
                redraw_com = lu_dict[act_key](self)
                if redraw_com == 1:
                    self.__win.refresh()
                elif redraw_com == 2:
                    self._draw_it()
    def exit_loop(self):
        self.__loop_flag = False

def input_test(stdscr, **args):
    curses.use_default_colors()
    e_win = single_line_input_widget(stdscr, width=32, valid_characters="a0.,:;")
    e_win.main_loop()
    
def main():
    curses.wrapper(input_test)
    test_mod = cluster_module(name="bla")
    test_mod.add_env_variable(cluster_module_env(name="PATH", mode="append", value="/opt/cluster/bin"))
    test_mod.add_env_variable(cluster_module_env(name="PxATH", mode="append", value="/opt/cluster/bin"))
    print test_mod.get_name()
    xml_rep = test_mod.get_xml_representation()
    print xml_rep
    test_mod_2 = cluster_module(src_type="string", src_name=xml_rep)
    
if __name__ == "__main__":
    main()
