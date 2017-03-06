#!/opt/cluster/bin/python3 -Ot
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
Improved ICSW command with using IPython
"""

import os
import sys
import argparse


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument(
        "-q",
        dest="quiet",
        default=False,
        action="store_true",
        help="be quiet [%(default)s]"
    )
    my_parser.add_argument(
        "--logger",
        type=str,
        default="stdout",
        choices=["stdout", "logserver"],
        help="choose logging facility [%(default)s]"
    )
    my_parser.add_argument(
        "--logall",
        default=False,
        action="store_true",
        help="log all (no just warning / error), [%(default)s]"
    )
    my_parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="commands to execute"
    )
    opts = my_parser.parse_args()
    if opts.args:
        opts.quiet = True
    if not opts.quiet:
        print("Starting ICSW shell ... ", end="", flush=True)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

    try:
        import django
        if not opts.quiet:
            print("django.setup() ... ", end="", flush=True)
        django.setup()
    except:
        django = None
    else:
        from initat.cluster.backbone import db_tools
        try:
            if not db_tools.is_reachable():
                django = None
        except:
            # when installing a newer icsw-client package on a machine with an old icsw-server package
            django = None

    from initat.icsw.magics import icsw_magics

    # First import the embeddable shell class
    from IPython.terminal.prompts import Prompts, Token
    from IPython.terminal.embed import InteractiveShellEmbed

    # Now create an instance of the embeddable shell. The first argument is a
    # string with options exactly as you would type them if you were starting
    # IPython at the system command line. Any parameters you want to define for
    # configuration can thus be specified here.
    ipshell = InteractiveShellEmbed(
        header="X",
        user_ns={"django": django}
    )

    class ICSWPrompt(Prompts):
        def in_prompt_tokens(self, cli=None):
            return [
                (Token, "[CORVUS]"),
                (Token.Prompt, ">"),
            ]

    ipshell.prompts = ICSWPrompt(ipshell)

    ipshell.mouse_support = True
    ipshell.confirm_exit = False
    ipshell.autocall = 2
    # no banner
    ipshell.banner1 = ""
    ipshell.set_hook(
        'complete_command',
        icsw_magics.apt_completers,
        str_key='icsw'
    )

    if False:
        class st2(object):
            def __dir__(self):
                return ["bla", "blo"]

            def abc(self, var):
                print("*", var)

            def _ipython_key_completions_(self):
                return ["x", "y"]

            def bla(self):
                return "bla"

            def __call__(self, *args):
                return "C", args


        xicsw = st2()

        def stest(sthg):
            print("stest:", sthg)

    ipshell.register_magics(icsw_magics.ICSWMagics(ipshell, True if django else False))

    if opts.args:
        if "--" in opts.args:
            opts.args.remove("--")
        _args = ["icsw"]
        if opts.logall:
            _args.append("--logall")
        _args.append("--logger")
        _args.append(opts.logger)
        r = ipshell.run_cell(
            " ".join(
                _args + opts.args
            )
        )
        sys.exit(r.result)
    else:
        if not opts.quiet:
            print("done")
        from initat.cluster.backbone.models import device, device_group
        ipshell(
            header="Starting icsw",
        )

if __name__ == "__main__":
    if __package__ is None:
        _add_path = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        )
        sys.dont_write_bytecode = True
        if _add_path not in sys.path:
            sys.path.insert(0, _add_path)
    main()
