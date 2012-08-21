#!/usr/bin/python-init

import os
import re
from distutils.core import setup

# Create list of media files
static_files = []
strip_leading = re.compile("src/initcore/")
for root, dirs, files in os.walk("src/initcore/static"):
    for i in files:
        stripped_root = re.sub(strip_leading, "", root)
        static_files.append(os.path.join(stripped_root, i))

setup(name="initcore",
      version="1.0.6.1",
      package_dir={"initcore": "src/initcore"},
      packages=["initcore", "initcore.templatetags"],
      package_data={"initcore": ["templates/*.html", "templates/initcore/*.html",
                                 "templates/initcore/*.css"] + static_files}
      )
