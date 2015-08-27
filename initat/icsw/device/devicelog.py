#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2004,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to cluster-backbone
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

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()
from initat.tools import logging_tools
from initat.cluster.backbone.models import DeviceLogEntry, LogLevel, device, LogSource
from django.db.models import Q


def populate_parser(child_parser):
    try:
        def_source = LogSource.objects.get(Q(identifier="commandline"))
    except:
        pass
    else:
        parser = child_parser.add_parser("log", help="create device log entries")
        parser.set_defaults(childcom="log", execute=main)
        parser.add_argument(
            "--mode",
            type=str,
            default="list",
            choices=["list", "create"],
            help="operation mode [%(default)s]"
        )
        parser.add_argument(
            "--level",
            type=str,
            default="",
            choices=LogLevel.objects.values_list("identifier", flat=True),
            help="log status [%(default)s]"
        )
        parser.add_argument(
            "--source",
            type=str,
            default="",
            choices=LogSource.objects.values_list("identifier", flat=True),
            help="log source [%(default)s]"
        )
        parser.add_argument(
            "--device",
            type=str,
            default="",
            choices=device.objects.all().values_list("name", flat=True).order_by("name"),
            help="device to show logs for [%(default)s]"
        )
        parser.add_argument("text", nargs="*")


def main(opts):
    ret_code = -1
    if opts.mode == "list":
        def_query = Q()
        if opts.level:
            def_query &= Q(level__identifier=opts.level)
        if opts.source:
            def_query &= Q(source__identifier=opts.source)
        if opts.device:
            def_query &= Q(device__name=opts.device)
        # print def_query
        all_logs = DeviceLogEntry.objects.filter(
            def_query
        ).select_related(
            "source",
            "source__device",
            "level",
            "user",
            "device"
        ).order_by("-date")
        print("{} found:".format(logging_tools.get_plural("Log entry", all_logs.count())))
        new_entry = logging_tools.new_form_list()
        for cur_dl in all_logs:
            new_entry.append([
                logging_tools.form_entry(unicode(cur_dl.date), header="date"),
                logging_tools.form_entry(unicode(cur_dl.device), header="device"),
                logging_tools.form_entry(unicode(cur_dl.source), header="source"),
                logging_tools.form_entry(unicode(cur_dl.source.device or "---"), header="sdevice"),
                logging_tools.form_entry(unicode(cur_dl.level), header="level"),
                logging_tools.form_entry(unicode(cur_dl.user or "---"), header="user"),
                logging_tools.form_entry(unicode(cur_dl.text), header="text"),
            ])
        print(unicode(new_entry))
        ret_code = 0
    elif opts.mode == "create":
        if not opts.text:
            print "no text entered"
        else:
            log_dev = device.objects.get(Q(name=opts.device))
            new_log_entry = DeviceLogEntry.new(
                device=log_dev,
                source=def_source,
                level=LogLevel.objects.get(Q(identifier=opts.level)),
                text=" ".join(opts.text),
            )
            ret_code = 0
            print("created '{}'".format(unicode(new_log_entry)))
    else:
        print "Uknown mode '{}'".format(opts.mode)
    sys.exit(ret_code)
