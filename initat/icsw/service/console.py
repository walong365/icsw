#
# Copyright (C) 2001-2009,2011-2016 Andreas Lang-Nevyjel, init.at
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

import time

from prompt_toolkit.application import Application
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.layout.controls import FillControl, TokenListControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token

from initat.tools import logging_tools


class ServiceOutput(object):
    def __init__(self, opt_ns, srv_c, inst_xml):
        self.opt_ns = opt_ns
        self.srv_c = srv_c
        self.inst_xml = inst_xml
        self._srv_text = ("", [])

    def update(self):
        self.srv_c.check_system(self.opt_ns, self.inst_xml)
        self._srv_text = self.srv_c.instance_to_form_list(self.opt_ns, self.inst_xml.tree).prompt_encode()

    def get_text(self):
        return self._srv_text


class SrvController(object):
    def __init__(self, opt_ns, srv_c, inst_xml):
        manager = KeyBindingManager()  # Start with the `KeyBindingManager`.

        self.srv_text = ServiceOutput(opt_ns, srv_c, inst_xml)
        layout = HSplit([
            # One window that holds the BufferControl with the default buffer on the
            # left.
            Window(
                height=D.exact(1),
                content=TokenListControl(
                    self.get_title_line, default_char=Char(" ", token=Token.String.ICSW.Header)
                )
            ),
            Window(
                height=D.exact(1),
                content=FillControl('-', token=Token.Line)
            ),
            # Display the text 'Hello world' on the right.
            Window(
                content=TokenListControl(
                    self.get_icsw_output,
                )
            ),
        ])

        self._updating = False

        @manager.registry.add_binding(Keys.ControlC, eager=True)
        @manager.registry.add_binding("q", eager=True)
        def _handler_data(event):
            event.cli.set_return_value(0)

        our_style = style_from_dict(logging_tools.get_icsw_prompt_styles())
        application = Application(
            layout=layout,
            use_alternate_screen=True,
            style=our_style,
            on_input_timeout=self.input_timeout,
            key_bindings_registry=manager.registry,
        )
        event_loop = create_eventloop()
        self.application = application
        self.event_loop = event_loop

    def loop(self):
        try:
            cli = CommandLineInterface(application=self.application, eventloop=self.event_loop)
            cli.run()
        finally:
            self.event_loop.close()

    def input_timeout(self, cli):
        cli.request_redraw()

    def get_title_line(self, cli):
        return [
            (
                Token.String.ICSW.Header,
                "Service overview ({}) {}".format(
                    time.ctime(time.time()),
                    " updating" if self._updating else "",
                )
            ),
        ]

    def get_icsw_output(self, cli):
        self._updating = True
        cli.request_redraw()
        self.srv_text.update()
        self._updating = False
        _r_list = []
        for _line in self.srv_text.get_text():
            _r_list.extend(
                [
                    (_token, _text) for _token, _text in _line
                ] + [
                    (Token.Text, "\n"),
                ]
            )
        return _r_list


def main(opt_ns, srv_c, inst_xml):
    if len(srv_c.check_system(opt_ns, inst_xml)):
        SrvController(opt_ns, srv_c, inst_xml).loop()
    else:
        srv_c.log("nothing to do", logging_tools.LOG_LEVEL_ERROR)
