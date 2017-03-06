"""Implementation of magic functions for interaction with the OS.

Note: this module is named 'osm' instead of 'os' to avoid a collision with the
builtin.
"""
from __future__ import print_function

import os
import re
import sys

from IPython.core.error import UsageError
from IPython.core.magic import Magics, compress_dhist, magics_class, line_magic
from IPython.testing.skipdoctest import skip_doctest
from IPython.utils import py3compat
from IPython.utils.process import abbrev_cwd
from IPython.utils.terminal import set_term_title


# -----------------------------------------------------------------------------
# Magic implementation classes
# -----------------------------------------------------------------------------

from initat.icsw import icsw_parser


@magics_class
class ICSWMagics(Magics):
    """Magics to interact with the underlying OS (shell-type functionality).
    """

    def _ipython_key_completions_(self, *args, **kwargs):
        print("ccc", args, kwargs)

    @skip_doctest
    @line_magic
    def icsw(self, parameter_s=''):
        """Change the current working directory.

        This command automatically maintains an internal list of directories
        you visit during your IPython session, in the variable _dh. The
        command %dhist shows this history nicely formatted. You can also
        do 'cd -<tab>' to see directory history conveniently.

        Usage:

          cd 'dir': changes to directory 'dir'.

          cd -: changes to the last visited directory.

          cd -<n>: changes to the n-th directory in the directory history.

          cd --foo: change to directory that matches 'foo' in history

          cd -b <bookmark_name>: jump to a bookmark set by %bookmark
             (note: cd <bookmark_name> is enough if there is no
              directory <bookmark_name>, but a bookmark with the name exists.)
              'cd -b <tab>' allows you to tab-complete bookmark names.

        Options:

        -q: quiet.  Do not print the working directory after the cd command is
        executed.  By default IPython's cd command does print this directory,
        since the default prompts do not display path information.

        Note that !cd doesn't work for this purpose because the shell where
        !command runs is immediately discarded after executing 'command'.

        Examples
        --------
        ::

          In [10]: cd parent/child
          /home/tsuser/parent/child
        """
        print(icsw_parser.__file__)
        opts = icsw_parser.ICSWParser().parse_args(
            parameter_s.split()
        )
        opts.execute(opts)


def apt_completers(self, event):
    """ This should return a list of strings with possible completions.

    Note that all the included strings that don't start with event.symbol
    are removed, in order to not confuse readline.

    """
    print("*", self, event.line)
    return ["service", "config", ]
