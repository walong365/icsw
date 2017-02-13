#!/usr/bin/python3-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014,2016-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" delete oldmigrate to configuration catalogs """

import time

from django.core.management.base import BaseCommand

from initat.cluster.backbone.models import MonIcingaLastRead,\
    mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data,\
    mon_icinga_log_raw_host_flapping_data,\
    mon_icinga_log_raw_service_notification_data,\
    mon_icinga_log_raw_host_notification_data, mon_icinga_log_file,\
    mon_icinga_log_raw_service_flapping_data,\
    mon_icinga_log_aggregated_host_data, mon_icinga_log_aggregated_service_data,\
    mon_icinga_log_aggregated_timespan, mon_icinga_log_full_system_dump,\
    mon_icinga_log_raw_host_downtime_data, mon_icinga_log_raw_service_downtime_data
from initat.tools import logging_tools


class Command(BaseCommand):
    help = "Delete data parsed by the icinga log parser"

    def add_arguments(self, parser):
        parser.add_argument(
            "--empty-aggregated",
            default=False,
            action="store_true",
            help="delete aggregated data [%(default)s]"
        )
        parser.add_argument(
            "--empty-raw",
            default=False,
            action="store_true",
            help="delete raw data [%(default)s]",
        )

    def handle(self, **options):
        for class_type, class_list in [
            (
                "raw",
                [
                    mon_icinga_log_raw_service_alert_data,
                    mon_icinga_log_raw_service_flapping_data,
                    mon_icinga_log_raw_service_notification_data,
                    mon_icinga_log_raw_service_downtime_data,
                    mon_icinga_log_raw_host_alert_data,
                    mon_icinga_log_raw_host_flapping_data,
                    mon_icinga_log_raw_host_notification_data,
                    mon_icinga_log_raw_host_downtime_data,
                    # extra
                    MonIcingaLastRead,
                    mon_icinga_log_full_system_dump,
                    mon_icinga_log_file,
                ]
            ),
            (
                "aggregated",
                [
                    mon_icinga_log_aggregated_timespan,
                    mon_icinga_log_aggregated_host_data,
                    mon_icinga_log_aggregated_service_data,
                ]
            )
        ]:
            if options["empty_{}".format(class_type)]:
                print("Start clearing {} data".format(class_type))
                for _class in class_list:
                    time_0 = time.time()
                    _count = _class.objects.all().count()
                    time_1 = time.time()
                    print(
                        "  Deleting raw class {} ({:d} entries)".format(
                            _class,
                            _count
                        )
                    )
                    if _count:
                        print(_class.objects.all().delete())
                    time_2 = time.time()
                    print(
                        "    Execution times: {} / {}".format(
                            logging_tools.get_diff_time_str(time_1 - time_0),
                            logging_tools.get_diff_time_str(time_2 - time_1),
                        )
                    )

                print("Removed all {} icinga log data".format(class_type))
                print("")
