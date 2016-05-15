# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
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
""" inject addons in already compiled main.html """

from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings
from initat.tools import logging_tools
import sys
import os
import re
from lxml import etree
from django.db.models import Q
from initat.cluster.backbone import factories
from initat.cluster.backbone.models import device_group


class FileModify(object):
    def __init__(self, name, modify):
        self.name = name
        self.modify = modify
        self.read()

    def debug(self, str):
        if not self.modify:
            print(str)

    def read(self):
        self._content = file(self.name, "r").read()
        self.debug(
            "read {} from {}".format(
                logging_tools.get_size_str(len(self._content)),
                self.name
            )
        )

    def cleanup_path(self):
        # cleanup include paths
        _body_found = False
        new_content = []
        for line_num, line in enumerate(self._content.split("\n"), 1):
            if not _body_found:
                if line.count("css") and line.count("link"):
                    line = line.strip().replace(">", "/>")
                try:
                    _xml = etree.fromstring(line)
                except:
                    pass
                else:
                    _new_dict = {}
                    for _key, _value in _xml.attrib.iteritems():
                        if _key in {"href", "src"}:
                            _new_dict[_key] = "{}{}".format(
                                "static/" if "/static/" in _value else "",
                                os.path.basename(_value)
                            )
                    for _key, _value in _new_dict.iteritems():
                        _xml.attrib[_key] = _value
                    line = etree.tostring(_xml, method="html")
                if line.lower().count("<body>"):
                    _body_found = True
            new_content.append(line)
        self._content = "\n".join(new_content)

    def inject(self):
        for _attr_name in [
            "ADDITIONAL_ANGULAR_APPS",
            "ICSW_ADDITIONAL_JS",
            "ICSW_ADDITIONAL_HTML",
        ]:
            self.debug("attribute '{}'".format(_attr_name))
            _val = getattr(settings, _attr_name)
            self.debug("  ->  {}".format(str(_val)))
        marker_re = re.compile("^.*<!-- ICSWAPPS:(?P<type>[A-Z]+):(?P<mode>[A-Z]+) -->.*$")
        new_content = []
        in_marker = False
        for line_num, line in enumerate(self._content.split("\n"), 1):
            marker_m = marker_re.match(line)
            if marker_m:
                new_content.append(line)
                _gd = marker_m.groupdict()
                in_marker = _gd["mode"] == "START"
                marker_type = _gd["type"]
                self.debug(
                    "found marker type {} ({}) in line {:d}".format(
                        marker_type,
                        _gd["mode"],
                        line_num,
                    )
                )
                _injected = 0
                if in_marker:
                    if marker_type == "MODULES":
                        for _app in settings.ADDITIONAL_ANGULAR_APPS:
                            _injected += 1
                            new_content.append("        \"{}\",".format(_app))
                    elif marker_type == "JAVASCRIPT":
                        for _js in settings.ICSW_ADDITIONAL_JS:
                            _injected += 1
                            new_content.append(
                                "        <script src='{}'></script>".format(
                                    os.path.basename(_js)
                                )
                            )
                    elif marker_type == "HTML":
                        for _html in settings.ICSW_ADDITIONAL_HTML:
                            _injected += 1
                            new_content.append(file(_html, "r").read())
                self.debug("injected {:d} lines".format(_injected))
            elif in_marker:
                # ignore everything inside marker (i.e. replace with new content)
                pass
            else:
                new_content.append(line)
        self._content = "\n".join(new_content)

    def write(self):
        dest = self.name
        self.debug(
            "would wrote {} to {}".format(
                logging_tools.get_size_str(len(self._content)),
                dest,
            )
        )
        if self.modify:
            file(dest, "w").write(self._content)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            "--srcfile",
            action="append",
            dest="files",
            default=[],
            help="Name of the files to modify",
        ),
        make_option(
            "--modify",
            action="store_true",
            default=False,
            help="rewrite file (and disable debug)",
        ),
        make_option(
            "--cleanup-path",
            action="store_true",
            default=False,
            help="fix wrong relative imports",
        )
    )
    help = ("Inject module code in files.")
    args = ''

    def handle(self, **options):
        if not options["files"]:
            print("No files given")
            sys.exit(2)
        if not all([os.path.exists(_file) for _file in options["files"]]):
            print("Not all files reachable ({})".format(", ".join(sorted(options["files"]))))
            sys.exit(2)
        for name in options["files"]:
            f_obj = FileModify(name, options["modify"])
            if options["cleanup_path"]:
                f_obj.cleanup_path()
            else:
                f_obj.inject()
            f_obj.write()
