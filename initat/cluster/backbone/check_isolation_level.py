#!/usr/bin/python-init -Otu

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def main():
    # check isolation level
    if settings.DATABASES["default"]["ENGINE"].count("mysql"):
        TARGET_IL = "READ-COMMITTED"
        from django.db import connections
        cursor = connections["default"].cursor()
        cursor.execute("SELECT @@global.tx_isolation")
        global_tx = cursor.fetchone()[0]
        cursor.execute("SELECT @@tx_isolation")
        local_tx = cursor.fetchone()[0]
        if (global_tx, local_tx) != (TARGET_IL, TARGET_IL):
            print("please insert to following lines to the [mysqld] section of /etc/my.cnf:")
            print("")
            print("transaction-isolation = READ-COMMITTED")
            print("")
            raise ImproperlyConfigured("wrong transaction-isolation level used (found: {}, need: {})".format(global_tx, TARGET_IL))

if __name__ == "__main__":
    main()
