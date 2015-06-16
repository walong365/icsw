#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
""" migrate to configuration catalogs """

from django.core.management.base import BaseCommand
from initat.cluster.backbone.models import mon_icinga_log_last_read,\
    mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data,\
    mon_icinga_log_raw_host_flapping_data,\
    mon_icinga_log_raw_service_notification_data,\
    mon_icinga_log_raw_host_notification_data, mon_icinga_log_file,\
    mon_icinga_log_raw_service_flapping_data,\
    mon_icinga_log_aggregated_host_data, mon_icinga_log_aggregated_service_data,\
    mon_icinga_log_aggregated_timespan, mon_icinga_log_full_system_dump,\
    mon_icinga_log_raw_host_downtime_data, mon_icinga_log_raw_service_downtime_data


class Command(BaseCommand):
    help = ("Delete data parsed by the icinga log parser")
    args = ''

    def handle(self, **options):
        mon_icinga_log_last_read.objects.all().delete()

        mon_icinga_log_full_system_dump.objects.all().delete()

        mon_icinga_log_raw_host_alert_data.objects.all().delete()
        mon_icinga_log_raw_service_alert_data.objects.all().delete()
        mon_icinga_log_raw_service_flapping_data.objects.all().delete()
        mon_icinga_log_raw_host_flapping_data.objects.all().delete()
        mon_icinga_log_raw_service_notification_data.objects.all().delete()
        mon_icinga_log_raw_host_notification_data.objects.all().delete()
        mon_icinga_log_raw_service_downtime_data.objects.filter().delete()
        mon_icinga_log_raw_host_downtime_data.objects.filter().delete()
        mon_icinga_log_file.objects.all().delete()

        mon_icinga_log_aggregated_timespan.objects.all().delete()
        mon_icinga_log_aggregated_host_data.objects.all().delete()
        mon_icinga_log_aggregated_service_data.objects.all().delete()
        print "Removed all parsed icinga log data"
