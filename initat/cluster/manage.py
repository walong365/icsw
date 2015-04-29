#!/usr/bin/python-init -Otu

import os
import sys

abs_path = os.path.abspath(__file__)
if not abs_path.startswith("/opt/python-init"):
    abs_path = os.path.split(os.path.split(os.path.split(abs_path)[0])[0])[0]
    if abs_path not in sys.path:
        sys.path.insert(0, abs_path)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
