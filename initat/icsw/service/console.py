#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" checks installed servers on system """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import argparse
import datetime
from initat.tools import logging_tools
from initat.tools import process_tools
import psutil
import stat
import urwid
import subprocess
import time


class ServiceOutput(urwid.Text):
    def __init__(self, opt_ns, srv_c, inst_xml):
        self.opt_ns = opt_ns
        self.srv_c = srv_c
        self.inst_xml = inst_xml
        self._srv_text = ("", [])
        urwid.Text.__init__(self, "", align="left", wrap="clip")

    def update(self):
        self.set_text("")
        self.srv_c.check_system(self.opt_ns, self.inst_xml)
        self._srv_text = self.srv_c.instance_to_form_list(self.opt_ns, self.inst_xml).urwid_encode()

    def get_text(self):
        return self._srv_text


class HeaderText(urwid.Text):
    def start_update(self):
        self.set_text("updating...")

    def update(self):
        self.set_text("Service overview ({})".format(time.ctime(time.time())))


class SrvController(object):
    def __init__(self, opt_ns, srv_c, inst_xml):
        self.srv_text = ServiceOutput(opt_ns, srv_c, inst_xml)
        self.top_text = HeaderText("", align="left")
        self.bottom_text = urwid.Text("bottom", align="left")
        self.main_text = urwid.Text("Wait please...", align="left")
        # self.bottom_text = urwid.Text("bottom", align="left")
        palette = [
            ('banner', 'black', 'light gray', 'standout,underline'),
            ("", "default", "default"),
            ("ok", "dark green,bold", "black"),
            ("warning", "yellow,bold", "black"),
            ("critical", "dark red,bold", "black"),
        ]
        urwid_map = urwid.AttrMap(
            urwid.Filler(
                urwid.Pile(
                    [
                        urwid.AttrMap(
                            self.top_text,
                            "banner"
                        ),
                        urwid.Columns(
                            [
                                ("weight", 60, self.srv_text),
                                ("weight", 40, urwid.AttrMap(
                                    self.main_text,
                                    "banner"
                                )),

                            ]
                        ),
                        urwid.AttrMap(
                            urwid.Pile(
                                [
                                    self.bottom_text,
                                ]
                            ),
                            "banner"
                        ),
                    ]
                ),
                "top"
            ),
            ""
        )
        self.mainloop = urwid.MainLoop(urwid_map, palette, unhandled_input=self._handler_data)
        self.mainloop.set_alarm_in(10, self._alarm_callback)
        self._update_screen()

    def _handler_data(self, in_char):
        if in_char == "q":
            self.close()
        elif in_char == " ":
            self._update_screen()

    def _update_screen(self):
        self.top_text.start_update()
        self.mainloop.draw_screen()
        self.top_text.update()
        self.srv_text.update()

    def _alarm_callback(self, main_loop, user_data):
        self._update_screen()
        self.mainloop.set_alarm_in(10, self._alarm_callback)

    def loop(self):
        self.mainloop.run()

    def close(self):
        raise urwid.ExitMainLoop()


def main(opt_ns, srv_c, inst_xml):
    SrvController(opt_ns, srv_c, inst_xml).loop()
