#!/usr/bin/python-init -Otu

import os
import sys

abs_path = os.path.abspath(__file__)
if not abs.path.startswith("/opt/python-init"):
    pass
sys.path.insert(0, "/usr/local/share/home/local/development/clustersoftware/build-extern/cluster-backbone-sql")

if __name__ == "__main__":
    #os.environ.setdefault("DJANGO_SETTINGS_MODULE", "init.cluster.settings")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cluster.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

