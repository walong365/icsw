#!/opt/cluster/bin/python3
"""An example of how to embed an IPython shell into a running program.

Please see the documentation in the IPython.Shell module for more details.

The accompanying file embed_class_short.py has quick code fragments for
embedding which you can cut and paste in your code once you understand how
things work.

The code in this file is deliberately extra-verbose, meant for learning."""

# The basics to get you going:

# IPython injects get_ipython into builtins, so you can know if you have nested
# copies running.

# Try running this code both at the command line and from inside IPython (with
# %run example-embed.py)
print("Starting icsw")
import sys

sys.path.insert(0, "/usr/local/share/home/local/development/git/icsw/")

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

print("django.setup()")
import django
django.setup()

from traitlets.config import Config

import icsw_magics

cfg = Config()

# First import the embeddable shell class
from IPython.terminal.embed import InteractiveShellEmbed

# Now create an instance of the embeddable shell. The first argument is a
# string with options exactly as you would type them if you were starting
# IPython at the system command line. Any parameters you want to define for
# configuration can thus be specified here.
ipshell = InteractiveShellEmbed()
from IPython.terminal.prompts import Prompts, Token


class my_prompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [
            (Token, "[CORVUS]"),
            (Token.Prompt, ">"),
        ]

ipshell.prompts = my_prompt(ipshell)

ipshell.mouse_support = True
ipshell.confirm_exit = False
ipshell.autocall = 2
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

ipshell.register_magics(icsw_magics.ICSWMagics)

ipshell.run_cell(" ".join(sys.argv[1:]))
from initat.cluster.backbone.models import device, device_group
ipshell(
    header="starting icsw",
)
#ipshell.mainloop(display_banner="OK")
