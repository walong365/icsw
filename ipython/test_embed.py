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
from traitlets.config import Config

import icsw_magics

# from IPython.config.loader import Config
try:
    get_ipython
except NameError:
    # normally called
    nested = 0
    cfg = Config()
else:
    print("Running nested copies of IPython.")
    print("The prompts for the nested copy have been modified")
    nested = 1
    cfg = Config()

# First import the embeddable shell class
from IPython.terminal.embed import InteractiveShellEmbed

# Now create an instance of the embeddable shell. The first argument is a
# string with options exactly as you would type them if you were starting
# IPython at the system command line. Any parameters you want to define for
# configuration can thus be specified here.
ipshell = InteractiveShellEmbed(
    config=cfg,
    banner1="starting icsw",
    exit_msg="bye.",
)
from IPython.terminal.prompts import Prompts, Token
# import pprint
# pprint.pprint(dir(ipshell))


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
# Make a second instance, you can have as many as you want.
cfg2 = cfg.copy()
# prompt_config = cfg2.PromptManager
# prompt_config.in_template = 'In2<\\#>: '
# if not nested:
#    prompt_config.in_template = 'In2<\\#>: '
#    prompt_config.in2_template = '   .\\D.: '
#    prompt_config.out_template = 'Out<\\#>: '

# ipshell2 = InteractiveShellEmbed(
#    config=cfg,
#    banner1='Second IPython instance.'
# )

# print('\nHello. This is printed from the main controller program.\n')

# print("use %autocall 2 to ease usage")


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
# You can then call ipshell() anywhere you need it (with an optional
# message):
ipshell(
    "Welcome to the CORVUS interactive shell"
    # 'Hit Ctrl-D to exit interpreter and continue program.\n'
    "Note that if you use %kill_embedded, you can fully deactivate\n"
    "This embedded instance so it will never turn on again",
)
