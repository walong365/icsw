#!/usr/bin/python-init -Otu
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw
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

""" create content for webfrontend on full rebuild """

import sys
from helper import parser
import subprocess
import os
import tempfile
import shutil
import tarfile

APP = "icsw"


def main():
    args = parser.parse()
    sys.exit(0)
    if args.increase_release_on_build:
        # print args
        print("specfile is at {}".format(args.specfile))
        _icsw_dir = os.path.normpath(
            os.path.join(
                os.path.dirname(args.specfile),
                "..",
                "..",
                APP,
                "initat",
                "cluster",
            )
        )
        binary_dir = os.path.join(args.binary_dir, APP)
        os.chdir(_icsw_dir)
        _temp_dir = tempfile.mkdtemp(suffix="_{}_wc".format(APP))
        _deploy_dir = os.path.join(_temp_dir, APP)
        _compile_dir = os.path.join(_temp_dir, "compile")
        subprocess.check_call(
            [
                "gulp",
                "--deploy-dir",
                _deploy_dir,
                "--compile-dir",
                _compile_dir,
                "create-content",
                "--production",
            ]
        )
        tar_file_name = os.path.join(binary_dir, "webcontent.tar.gz")
        tar_file = tarfile.open(tar_file_name, "w:gz")
        os.chdir(_temp_dir)
        tar_file.add(APP)
        tar_file.close()
        shutil.rmtree(_temp_dir)
    else:
        print("rebuild run, not modify specfile")
    sys.exit(0)


if __name__ == "__main__":
    main()
