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

        print("p=", parameter_s)
        oldcwd = py3compat.getcwd()
        numcd = re.match(r'(-)(\d+)$', parameter_s)
        # jump in directory history by number
        if numcd:
            nn = int(numcd.group(2))
            try:
                ps = self.shell.user_ns['_dh'][nn]
            except IndexError:
                print('The requested directory does not exist in history.')
                return
            else:
                opts = {}
        elif parameter_s.startswith('--'):
            ps = None
            fallback = None
            pat = parameter_s[2:]
            dh = self.shell.user_ns['_dh']
            # first search only by basename (last component)
            for ent in reversed(dh):
                if pat in os.path.basename(ent) and os.path.isdir(ent):
                    ps = ent
                    break

                if fallback is None and pat in ent and os.path.isdir(ent):
                    fallback = ent

            # if we have no last part match, pick the first full path match
            if ps is None:
                ps = fallback

            if ps is None:
                print("No matching entry in directory history")
                return
            else:
                opts = {}
        else:
            opts, ps = self.parse_options(parameter_s, 'qb', mode='string')
        # jump to previous
        if ps == '-':
            try:
                ps = self.shell.user_ns['_dh'][-2]
            except IndexError:
                raise UsageError('%cd -: No previous directory to change to.')
        # jump to bookmark if needed
        else:
            if not os.path.isdir(ps) or 'b' in opts:
                bkms = self.shell.db.get('bookmarks', {})

                if ps in bkms:
                    target = bkms[ps]
                    print('(bookmark:%s) -> %s' % (ps, target))
                    ps = target
                else:
                    if 'b' in opts:
                        raise UsageError(
                            "Bookmark '%s' not found.  "
                            "Use '%%bookmark -l' to see your bookmarks." % ps
                        )

        # at this point ps should point to the target dir
        if ps:
            try:
                os.chdir(os.path.expanduser(ps))
                if hasattr(self.shell, 'term_title') and self.shell.term_title:
                    set_term_title('IPython: ' + abbrev_cwd())
            except OSError:
                print(sys.exc_info()[1])
            else:
                cwd = py3compat.getcwd()
                dhist = self.shell.user_ns['_dh']
                if oldcwd != cwd:
                    dhist.append(cwd)
                    self.shell.db['dhist'] = compress_dhist(dhist)[-100:]

        else:
            os.chdir(self.shell.home_dir)
            if hasattr(self.shell, 'term_title') and self.shell.term_title:
                set_term_title('IPython: ' + '~')
            cwd = py3compat.getcwd()
            dhist = self.shell.user_ns['_dh']

            if oldcwd != cwd:
                dhist.append(cwd)
                self.shell.db['dhist'] = compress_dhist(dhist)[-100:]
        if 'q' not in opts and self.shell.user_ns['_dh']:
            print(self.shell.user_ns['_dh'][-1])


def apt_completers(self, event):
    """ This should return a list of strings with possible completions.

    Note that all the included strings that don't start with event.symbol
    are removed, in order to not confuse readline.

    """
    print("*", self, event.line)
    return ["service", "config", ]
