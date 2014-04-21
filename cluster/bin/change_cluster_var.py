#!/usr/bin/python-init -Otu
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone
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

""" change cluster variables via commandline """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from initat.cluster.backbone.models import config_str
import argparse
import re

def _show_var(var):
    print "{:4d} :: {:<40s} ({:<20s}) : {}".format(
        var.idx,
        var.name,
        var.config.name,
        var.value,
        )

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--list", dest="list_mode", default=False, action="store_true", help="list variables [%(default)s]")
    my_parser.add_argument("--name", dest="name_re", default=".*", help="name search string [%(default)s]")
    my_parser.add_argument("--value", dest="value_re", default=".*", help="value search string [%(default)s]")
    my_parser.add_argument("--exclude", action="append", default=[], type=int, help="exclude PKs [%(default)s]")
    my_parser.add_argument("--set", dest="new_val", type=str, default="", help="new value to set [%(default)s]")
    options = my_parser.parse_args()
    if options.list_mode:
        all_vars = config_str.objects.all().select_related("config").order_by("config__name", "name")
        for _var in all_vars:
            _show_var(_var)
        sys.exit(0)
    name_re, value_re = (re.compile(options.name_re, re.IGNORECASE), re.compile(options.value_re, re.IGNORECASE))
    # print options
    for _var in config_str.objects.all().select_related("config").order_by("config__name", "name"):
        if name_re.search(_var.name) and value_re.search(_var.value) and _var.idx not in options.exclude:
            _show_var(_var)
            if options.new_val and _var.value != options.new_val:
                _var.value = options.new_val
                _var.save()
                print "after change -->"
                _show_var(_var)

if __name__ == "__main__":
    main()
