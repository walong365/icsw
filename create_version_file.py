#!/usr/bin/python-init -Otu

import argparse
import datetime
import sys
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, help="Version [%(default)s]", default="1.0")
    parser.add_argument("--release", type=str, help="Release [%(default)s]", default="1")
    parser.add_argument("--target", type=str, help="version file target [%(default)s]", default="/tmp/version.py")
    opts = parser.parse_args()
    _now = datetime.datetime.now()
    content = [
        "# version file, created on {}".format(str(_now.strftime("%a, %d. %b %Y %H:%M:%S"))),
        "",
        "VERSION_STRING = \"{}-{}\"".format(opts.version, opts.release),
        "BUILD_TIME = \"{}\"".format(_now.strftime("%Y-%m-%d %H:%M:%S")),
        "BUILD_MACHINE = \"{}\"".format(os.uname()[1]),
        "",
    ]
    file(opts.target, "w").write("\n".join(content))
    sys.exit(0)


if __name__ == "__main__":
    main()
