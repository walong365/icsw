#!/usr/bin/python-init 

from distutils.core import setup

setup(name="initcore",
      version="1.0.0",
      package_dir={"": "src"},
      packages=["initcore", "initcore.management", "initcore.management.commands",
          "initcore.templatetags"],
      )
