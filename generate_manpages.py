#!/usr/bin/python-init

import subprocess
import os

OUTDIR = "./man"

EXES = (
    ("populate_ramdisk.py.0", "cluster/bin/populate_ramdisk.py", ("--version-string", "3.0", "-N")),
)

def help2man(args):
    """
    Call help2man with the arguments specified in the tuple args and
    return the output
    """
    manpage = subprocess.check_output(("help2man", ) + args)
    return manpage


def main():
    for name, path, args in EXES:
        manpage = help2man(args + (path, ))
        manpath = os.path.join(OUTDIR, name)

        with open(manpath, "w") as f:
            f.write(manpage)
            print "Writing manpage %s" % manpath


if __name__ == "__main__":
    main()

