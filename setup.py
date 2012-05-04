#!/usr/bin/python-init 

import os
import re
from distutils.core import setup

# Create list of media files
media_files = []
strip_leading = re.compile("src/initcore/")
for root, dirs, files in os.walk("src/initcore/media"):
    for i in files:
        stripped_root = re.sub(strip_leading, "", root)
        media_files.append(os.path.join(stripped_root, i))

setup(name="initcore",
      version="1.0.1",
      package_dir={"initcore": "src/initcore"},
      packages=["initcore", "initcore.management", "initcore.management.commands",
          "initcore.templatetags"],
      package_data={"initcore": ["templates/*.html", "templates/initcore/*.html",
      "templates/initcore/*.css"] +  media_files}
      )
