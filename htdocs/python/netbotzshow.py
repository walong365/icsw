#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2008 Andreas Lang-Nevyjel, init.at
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
""" shows netbotz pictures """

import functions
import logging_tools
import os
import os.path
import time
import datetime
import html_tools
    
def module_info():
    return {"nbs" : {"description"           : "Netbotz show",
                     "default"               : 0,
                     "enabled"               : 1,
                     "left_string"           : "Netbotz pictures",
                     "right_string"          : "Shows the Imags from the installed Netbotzes",
                     "priority"              : -100,
                     "capability_group_name" : "info"}}

class netbotz(object):
    def __init__(self, name, idx):
        self.__name = name
        self.__dev_idx = idx
        self.__pictures = {}
        self.__num_pictures = 0
        self.set_ip("???")
    def set_ip(self, ip):
        self.__ip = ip
    def get_ip(self):
        return self.__ip
    def get_name(self):
        return self.__name
    def get_dev_idx(self):
        return self.__dev_idx
    def get_first_date(self):
        d_f = []
        act_d = self.__pictures
        for i in range(4):
            d_f.append(min(act_d.keys()))
            act_d = act_d[d_f[-1]]
        act_d = act_d[0]
        d_f.extend([act_d[0], act_d[1]])
        return time.localtime(time.mktime(d_f + [0, 0, -1]))
    def get_last_date(self):
        d_f = []
        act_d = self.__pictures
        for i in range(4):
            d_f.append(max(act_d.keys()))
            act_d = act_d[d_f[-1]]
        act_d = act_d[-1]
        d_f.extend([act_d[0], act_d[1]])
        return time.localtime(time.mktime(d_f + [0, 0, -1]))
    def get_num_pictures(self, year=None, month=None, day=None):
        def get_num_p(in_d):
            if type(in_d) == type([]):
                return len(in_d)
            else:
                return sum([get_num_p(d) for d in in_d.values()])
        if year:
            act_d = self.__pictures.get(year, {})
            if month:
                act_d = act_d.get(month, {})
                if day:
                    act_d = act_d.get(day, {})
            return get_num_p(act_d)
        else:
            return self.__num_pictures
    def get_years(self):
        return self.__pictures.keys()
    def get_months(self, year):
        return self.__pictures.get(year, {}).keys()
    def get_days(self, year, month):
        return self.__pictures.get(year, {}).get(month, {}).keys()
    def get_dict_for_day(self, year, month, day):
        return self.__pictures.get(year, {}).get(month, {}).get(day, {})
    def get_cursor(self, pos=1):
        if pos == 1:
            act_day = self.get_last_date()
        return act_day
    def copy_cursor(self, act_c):
        return [x for x in act_c]
    def get_seconds(self, act_c):
        return time.mktime(act_c)
    def cursor_back(self, act_c):
        act_d_l = self.__pictures[act_c[0]][act_c[1]][act_c[2]][act_c[3]]
        prev_ms = None
        for l_min, l_sec, l_path in act_d_l:
            if l_min == act_c[4] and l_sec == act_c[5]:
                break
            prev_ms = (l_min, l_sec)
        if prev_ms:
            act_c[4] = prev_ms[0]
            act_c[5] = prev_ms[1]
        else:
            act_hours = sorted(self.__pictures[act_c[0]][act_c[1]][act_c[2]].keys())
            if act_c[3] == act_hours[0]:
                act_days = sorted(self.__pictures[act_c[0]][act_c[1]].keys())
                if act_c[2] == act_days[0]:
                    act_months = sorted(self.__pictures[act_c[0]].keys())
                    if act_c[1] == act_months[0]:
                        act_years = sorted(self.__pictures.keys())
                        if act_c[0] == act_years[0]:
                            # finally...
                            pass
                        else:
                            act_c[0] = act_years[act_years.index(act_c[0]) - 1]
                        act_months = sorted(self.__pictures[act_c[0]].keys())
                        act_c[1] = act_months[-1]
                    else:
                        act_c[1] = act_months[act_months.index(act_c[1]) - 1]
                    act_days = sorted(self.__pictures[act_c[0]][act_c[1]].keys())
                    act_c[2] = act_days[-1]
                else:
                    act_c[2] = act_days[act_days.index(act_c[2]) - 1]
                act_hours = sorted(self.__pictures[act_c[0]][act_c[1]][act_c[2]].keys())
                act_c[3] = act_hours[-1]
            else:
                act_c[3] = act_hours[act_hours.index(act_c[3]) - 1]
            act_c[4] = self.__pictures[act_c[0]][act_c[1]][act_c[2]][act_c[3]][-1][0]
            act_c[5] = self.__pictures[act_c[0]][act_c[1]][act_c[2]][act_c[3]][-1][1]
    def get_picture_path(self, cursor):
        act_d = self.__pictures[cursor[0]][cursor[1]][cursor[2]][cursor[3]]
        return [z for x, y, z in act_d if x == cursor[4] and y == cursor[5]][0]
    def add_picture(self, struct):
        self.__num_pictures += 1
        self.__pictures.setdefault(struct["year"], {}).setdefault(struct["month"], {}).setdefault(struct["day"], {}).setdefault(struct["hour"], []).append((struct["minute"], struct["second"], struct["path"]))
    
def fetch_nb_dict(req):
    sql_str = "SELECT d.name, d.device_idx, i.ip FROM device d, device_type dt, netdevice n, netip i WHERE dt.device_type_idx=d.device_type AND dt.identifier='NB' AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx"
    req.dc.execute(sql_str)
    nb_dict = {}
    for db_rec in req.dc.fetchall():
        nb_dict[db_rec["name"]] = netbotz(db_rec["name"], db_rec["device_idx"])
        nb_dict[db_rec["name"]].set_ip(db_rec["ip"])
    if nb_dict:
        sql_str = "SELECT d.name, nb.* FROM netbotz_picture nb, device d WHERE nb.device=d.device_idx AND (%s) ORDER BY d.name, nb.year, nb.month, nb.day, nb.hour, nb.minute, nb.second" % (" OR ".join(["d.name='%s'" % (x) for x in nb_dict.keys()]))
        req.dc.execute(sql_str)
        for db_rec in req.dc.fetchall():
            nb_dict[db_rec["name"]].add_picture(db_rec)
    return nb_dict
    
def process_page(req):
    functions.write_header(req)
    functions.write_body(req)
    action_log = html_tools.message_log()
    # basic buttons
    select_button = html_tools.submit_button(req, "select")
    submit_button = html_tools.submit_button(req, "submit")
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    low_submit[""] = 1
    nb_dict = fetch_nb_dict(req)
    if nb_dict:
        stride_time_list = html_tools.selection_list(req, "sb", {})
        for st in range(1, 5) + range(5, 31, 5) + range(30, 61, 10):
            stride_time_list[st] = {"name" : logging_tools.get_plural("minute", st)}
        num_pics_list = html_tools.selection_list(req, "nb", {})
        for nb in range(3, 31):
            num_pics_list[nb] = {"name" : logging_tools.get_plural("picture", nb)}
        show_type_list = html_tools.selection_list(req, "st", {"a" : "last"})
        nb_sel_list = html_tools.radio_list(req, "dt", {}, sort_new_keys=0)
        nb_names = nb_dict.keys()
        nb_names.sort()
        nb_lut = {}
        for nb_name in nb_names:
            nb_s = nb_dict[nb_name]
            nb_lut[nb_s.get_dev_idx()] = nb_s
            nb_sel_list[nb_s.get_dev_idx()] = {}
        sel_nb = nb_sel_list.check_selection("", nb_dict[nb_names[0]].get_dev_idx())
        req.write(html_tools.gen_hline("Found %s with %s" % (logging_tools.get_plural("Netbotz", len(nb_names)),
                                                             logging_tools.get_plural("picture", sum([x.get_num_pictures() for x in nb_dict.values()])))))
        nb_table = html_tools.html_table(cls="normalsmall")
        nb_table[0]["class"] = "lineh"
        for head in ["Name", "IP", "Pictures", "first picture", "last picture"]:
            nb_table[None][0] = html_tools.content(head, type="th", cls="center")
        line_idx = 0
        for nb_name in nb_names:
            line_idx = 1 - line_idx
            nb_s = nb_dict[nb_name]
            nb_table[0]["class"] = "line1%d" % (line_idx)
            nb_table[None][0] = html_tools.content([nb_sel_list, nb_s.get_name()], cls="left")
            nb_table[None][0] = html_tools.content(nb_s.get_ip(), cls="left")
            nb_table[None][0] = html_tools.content("%d" % (nb_s.get_num_pictures()), cls="right")
            if nb_s.get_num_pictures():
                nb_table[None][0] = html_tools.content(time.strftime("%d. %b %Y, %H:%M:%S", nb_s.get_first_date()), cls="center")
                nb_table[None][0] = html_tools.content(time.strftime("%d. %b %Y, %H:%M:%S", nb_s.get_last_date()), cls="center")
            else:
                nb_table[None][0] = html_tools.content("---", cls="center")
                nb_table[None][0] = html_tools.content("---", cls="center")
        req.write(nb_table(""))
        act_nb = nb_lut[sel_nb]
        if act_nb.get_num_pictures():
            line_idx = 0
            day_table = html_tools.html_table(cls="normal")
            day_table[0]["class"] = "lineh"
            for head in ["Day", "Pictures", "first picture", "last picture", "rate"]:
                day_table[None][0] = html_tools.content(head, type="th", cls="center")
            for year in sorted(act_nb.get_years()):
                months = act_nb.get_months(year)
                for month in months:
                    act_date = datetime.date(year, month, 1)
                    day_table[0]["class"] = "line00"
                    day_table[None][0:5] = html_tools.content("%s, %s" % (act_date.strftime("%b %Y"),
                                                                        logging_tools.get_plural("picture", act_nb.get_num_pictures(year, month))), cls="center")
                    days = act_nb.get_days(year, month)
                    for day in days:
                        act_date = datetime.date(year, month, day)
                        line_idx = 1 - line_idx
                        day_dict = act_nb.get_dict_for_day(year, month, day)
                        day_table[0]["class"] = "line1%d" % (line_idx)
                        day_table[None][0] = html_tools.content(act_date.strftime("%d., %A"), cls="left")
                        day_pics = act_nb.get_num_pictures(year, month, day)
                        day_table[None][0] = html_tools.content(logging_tools.get_plural("picture", day_pics), cls="center")
                        if day_dict:
                            hours = sorted(day_dict.keys())
                            first_hour = hours[0]
                            last_hour = hours[-1]
                            s_time = datetime.time(first_hour, day_dict[first_hour][0][0], day_dict[first_hour][0][1])
                            e_time = datetime.time(last_hour, day_dict[last_hour][-1][0], day_dict[last_hour][-1][1])
                            day_table[None][0] = html_tools.content(s_time.strftime("%H:%M:%S"), cls="center")
                            day_table[None][0] = html_tools.content(e_time.strftime("%H:%M:%S"), cls="center")
                        else:
                            day_table[None][0] = html_tools.content("---", cls="center")
                        if day_pics > 1:
                            day_table[None][0] = html_tools.content("1 picture every %.2f seconds" % ((e_time.second - s_time.second + 60 * (e_time.minute - s_time.minute + 60 * (e_time.hour - s_time.hour))) / float(day_pics)), cls="center")
                        else:
                            day_table[None][0] = html_tools.content("---", cls="center")
                            
            req.write("%s\n%s" % (html_tools.gen_hline("Overview", 3),
                                  day_table("")))
            act_type = show_type_list.check_selection("", "a")
            act_st = stride_time_list.check_selection("", 1) * 60
            num_pics = num_pics_list.check_selection("", 3)
            select_button = html_tools.submit_button(req, "select")
            req.write("<form action=\"%s.py?%s\" method=post>\n" % (req.module_name,
                                                                    functions.get_sid(req)))
            req.write("<div class=\"center\">Showtype: %s%s, stride is %s, %s</div></form>" % (show_type_list(""),
                                                                                               num_pics_list(""),
                                                                                               stride_time_list(""),
                                                                                               select_button("")))
            act_root = req.document_root()
            if act_type == "a":
                cursor = act_nb.get_cursor(1)
                first_c_time = act_nb.get_seconds(cursor)
                pic_table = html_tools.html_table(cls="normalsmall")
                pics_per_line = 3
                act_line, act_row = (1, 1)
                lines_used = []
                for i in range(num_pics):
                    if act_line not in lines_used:
                        pic_table[2 * act_line - 1]["class"] = "line10"
                        pic_table[2 * act_line]["class"] = "line10"
                        lines_used.append(act_line)
                    pic_src = os.path.normpath(act_nb.get_picture_path(cursor))[len(act_root):]
                    pic_table[2 * act_line - 1][act_row] = html_tools.content("%d of %d, %s" % (i + 1, num_pics, datetime.datetime(*(cursor[0:7])).strftime("%d. %b %Y, %H:%M:%S")), cls="center")
                    pic_table[2 * act_line][act_row] = html_tools.content("<img alt=\"Netbotz picture\" src=\"%s\" >" % (pic_src))
                    if act_row == pics_per_line:
                        act_line += 1
                        act_row = 1
                    else:
                        act_row += 1
                    new_c = act_nb.copy_cursor(cursor)
                    min_diff = 6666666
                    while True:
                        act_nb.cursor_back(new_c)
                        act_diff = abs(first_c_time - (i + 1) * act_st - act_nb.get_seconds(new_c))
                        if act_diff < min_diff:
                            min_diff = act_diff
                            min_cursor = act_nb.copy_cursor(new_c)
                        else:
                            break
                    cursor = act_nb.copy_cursor(new_c)
                    #act_nb.cursor_back(cursor)
                if act_row != 1:
                    pic_table[2 * act_line - 1 : 2 * act_line][act_row : pics_per_line] = html_tools.content("&nbsp;")
                req.write(pic_table(""))
    else:
        req.write(html_tools.gen_hline("No Netbotzes found", 2))
    # get images
