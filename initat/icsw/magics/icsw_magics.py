#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# Send feedback to: <lang-nevyjel@init.at>
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
"""
magics for ipython for ICSW shell
"""

from IPython.core.magic import Magics, magics_class, line_magic
from IPython.testing.skipdoctest import skip_doctest

from initat.icsw import icsw_parser


@magics_class
class ICSWMagics(Magics):
    # def _ipython_key_completions_(self, *args, **kwargs):
    #    print("ccc", args, kwargs)

    def __init__(self, shell, data):
        # You must call the parent constructor
        super(ICSWMagics, self).__init__(shell)
        self.server_mode = data

    @skip_doctest
    @line_magic
    def icsw(self, parameter_s=''):
        opts = icsw_parser.ICSWParser().parse_args(
            self.server_mode,
            parameter_s.split(),
        )
        try:
            opts.execute(opts)
        except SystemExit as e:
            return e.code


def apt_completers(self, event):
    """ This should return a list of strings with possible completions.

    Note that all the included strings that don't start with event.symbol
    are removed, in order to not confuse readline.

    """
    print("*", self, event.line)
    return ["service", "config", ]
