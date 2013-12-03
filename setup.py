#!/usr/bin/python-init

import os
import re
from distutils.core import setup

# Create list of media files
static_files = []
strip_leading = re.compile("src/initat/core/")
for root, dirs, files in os.walk("src/initat/core/static"):
    print root, dirs, files
    for i in files:
        stripped_root = re.sub(strip_leading, "", root)
        static_files.append(os.path.join(stripped_root, i))

setup(name="initat",
      version="2.0.0",
      package_dir={"initat": "src/initat"},
      packages=["initat", "initat.core", "initat.core.templatetags", "initat.core.alfresco",
                "initat.core.management", "initat.core.management.commands"],
      package_data={"initat.core": ["templates/initcore/*.html", "templates/initcore/*.xml"] + static_files}
      )
