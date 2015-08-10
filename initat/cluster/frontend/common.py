#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of webfrontend
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
import datetime
import pytz
from initat.cluster.backbone.models.functions import duration


class duration_utils(object):

    @staticmethod
    def parse_date(date, is_utc=True):
        date = datetime.datetime.fromtimestamp(int(date))
        if is_utc:
            date = date.replace(tzinfo=pytz.UTC)
        return date

    @staticmethod
    def parse_duration_from_request(request):
        '''
        Parse duration from a "usual" request
        '''
        date = request.GET["date"]
        in_duration_type = request.GET["duration_type"]
        return duration_utils.parse_duration(in_duration_type, date)

    @staticmethod
    def parse_duration(in_duration_type, date):
        '''
        :param str in_duration_type:
        :param str date: timestamp from request
        :return: tuple (unit of data to display, start, end)
        '''
        date = duration_utils.parse_date(date)
        # durations end one second before start of next, i.e. interval is inclusive
        if in_duration_type == "day":
            duration_type = duration.Hour
            start = duration.Day.get_time_frame_start(date)
            end = duration.Day.get_end_time_for_start(start) - datetime.timedelta(seconds=1)
        elif in_duration_type == "week":
            duration_type = duration.Day
            date_as_date = date.date()  # forget time
            date_day = datetime.datetime(year=date_as_date.year, month=date_as_date.month, day=date_as_date.day)
            start = date_day - datetime.timedelta(days=date_day.weekday())
            end = start + datetime.timedelta(days=7) - datetime.timedelta(seconds=1)
        elif in_duration_type == "month":
            duration_type = duration.Day
            start = duration.Month.get_time_frame_start(date)
            end = duration.Month.get_end_time_for_start(start) - datetime.timedelta(seconds=1)
        elif in_duration_type == "year":
            duration_type = duration.Month
            start = datetime.datetime(year=date.year, month=1, day=1)
            end = datetime.datetime(year=date.year+1, month=1, day=1) - datetime.timedelta(seconds=1)
        return (duration_type, start, end)

    @staticmethod
    def get_steps(in_duration_type, date):
        (duration_type, start, end) = duration_utils.parse_duration(in_duration_type, date)

        steps = []
        cur = start

        while cur < end:
            steps.append({"date": duration_type.get_display_date(cur), "full_date": cur.isoformat()})
            cur = duration_type.get_end_time_for_start(cur) + datetime.timedelta(seconds=1)

        return steps
