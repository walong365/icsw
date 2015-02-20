#!/usr/bin/python-init

import os
import re
import sys
from distutils.core import setup

# Create list of media files
static_files = []
symlinks = []
strip_leading = re.compile("src/initat/core/")
for root, dirs, files in os.walk("src/initat/core/static"):
    stripped_root = re.sub(strip_leading, "", root)
    #print files
    for i in files:
        static_files.append(os.path.join(stripped_root, i))
    for d in dirs:
        f_path = os.path.join(root, d)
        if os.path.islink(f_path):
            symlinks.append((os.path.join(stripped_root, d), os.readlink(f_path)))

if symlinks:
    print "Symlinks found: %s" % (symlinks)
    sys.exit(1)

setup(name="initat",
      version="2.0.0",
      package_dir={"initat": "src/initat"},
      packages=["initat", "initat.core",]
      package_data={"initat.core": ["templates/initcore/*.html", "templates/initcore/*.xml"] + static_files}
      )
