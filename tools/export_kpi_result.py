#!/usr/bin/python-init

"""
Auxiliary script to export kpi results to csv.
Will be used as baseline for proper kpi result export.
"""


import collections
import csv
import json
import os
import re
import sys
import math

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from initat.cluster.backbone.models import Kpi, KpiStoredResult

import django
django.setup()


def main():
    with open("/tmp/a.csv", "w") as f:
        writer = csv.writer(f)

        for kpi in Kpi.objects.all():
            res = json.loads(kpi.kpistoredresult.result)
            kpi_objs = res['objects']

            if len(kpi_objs) == 1:
                kpi_obj = kpi_objs[0]
                if 'aggregated_tl' in kpi_obj:
                    tl = kpi_obj['aggregated_tl']
                    print 'kpi', kpi
                    print tl
                    data = tl
                    ok_val = data.pop('Ok', 0)
                    warn_val = data.pop('Warning', 0)
                    crit_val = data.pop('Critical', 0)
                    undet_val = data.pop('Undetermined', 0) + data.pop("Unknown", 0)
                    if data:
                        raise RuntimeError("item not used: {}".format(data))

                    format = lambda f: "{:.5f}".format(f)

                    print 'writ'
                    writer.writerow([kpi.name])
                    writer.writerow(["Month", "Ok", 'Warn', 'Critical', 'Undetermined'])
                    writer.writerow([
                        "Jun",
                        format(ok_val),
                        format(warn_val),
                        format(crit_val),
                        format(undet_val)
                    ])

if __name__ == "__main__":
    main()
