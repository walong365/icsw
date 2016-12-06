# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
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
""" inject addons in already compiled main.html """

from __future__ import unicode_literals, print_function

import codecs
import json
import os
import re
import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from lxml import etree
from lxml.builder import E

from initat.cluster.backbone.models import csw_permission
from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, process_tools


class ConfigRelax(object):
    def __init__(self):
        _inst = InstanceXML(quiet=True)
        all_instances = sum([_inst.xpath(".//config-enums/config-enum/text()") for _inst in _inst.get_all_instances()], [])
        all_perms = [_perm.perm_name for _perm in csw_permission.objects.all()] + ["$$CHECK_FOR_SUPERUSER"]
        _content = file(
            "{}/config_relax.xml".format(os.path.join(settings.FILE_ROOT, "config")),
            "r",
        ).read()
        _content = _content.replace(
            "<value>RIGHTSLIST</value>",
            "".join(
                [
                    "<value>{}</value>".format(_pn) for _pn in all_perms
                ]
            )
        ).replace(
            "<value>SERVICETYPESLIST</value>",
            "".join(
                [
                    "<value>{}</value>".format(_stn) for _stn in all_instances
                ]
            )
        )
        # sys.exit(0)
        self.ng = etree.RelaxNG(
            etree.fromstring(
                _content,
            )
        )

    def validate(self, in_xml):
        _valid = self.ng.validate(in_xml)
        if not _valid:
            # not beautifull but working
            raise ValueError(str(self.ng.error_log))


class FileModify(object):
    def __init__(self, name, modify):
        self.name = name
        self.modify = modify
        self.read()

    def debug(self, str):
        if not self.modify:
            print(str)

    def read(self):
        self._content = codecs.open(self.name, "r", "utf-8").read()
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
                    if _xml.attrib.get("rel", "") == "icon":
                        # ignore icon location
                        pass
                    else:
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

    def config_xml_to_json(self, xml):
        LIST_TEXT_TAGS = {"rights", "licenses", "serviceTypes"}
        LIST_TAGS = {"menuHeader", "routeSubGroup", "menuEntry", "route", "task", "taskStep"}
        # use attributes instead of ElementTag as key for parent dict
        NAME_DICT_TAGS = {
            "route": "name",
            "infoText": "language",
        }
        APPEND_TEXT_TAGS = {"value"}

        def _iter_dict(parent_el, el):
            if el.tag is etree.Comment:
                # filter out comments
                return
            # print("***", el.tag)
            # build local dict
            r_v = {}
            for _attr_name in el.attrib.iterkeys():
                if _attr_name.count("_") == 1:
                    _name, _type = _attr_name.split("_")
                else:
                    # all other attributes are of type str
                    _name, _type = (_attr_name, "str")
                if _type == "bool":
                    r_v[_name] = True if el.attrib[_attr_name] in ["yes"] else False
                elif _type == "int":
                    r_v[_name] = int(el.attrib[_attr_name])
                elif _type == "json":
                    r_v[_name] = eval(el.attrib[_attr_name])
                else:
                    r_v[_name] = el.attrib[_attr_name]
            if el.text and el.text.strip():
                r_v["text"] = el.text.strip()
            if el.tag in LIST_TEXT_TAGS:
                # special form of list of text values
                r_v = []
                parent_el.setdefault(el.tag, r_v)
            elif el.tag in NAME_DICT_TAGS:
                # use name of r_v as dict key
                parent_el[r_v[NAME_DICT_TAGS[el.tag]]] = r_v
            elif el.tag in LIST_TAGS:
                parent_el.setdefault(el.tag, []).append(r_v)
            elif el.tag in APPEND_TEXT_TAGS:
                # child of LIST_TEXT_TAG
                parent_el.append(el.text)
            else:
                parent_el[el.tag] = r_v
            for sub_el in el:
                _iter_dict(r_v, sub_el)

        _res = {}
        for el in xml:
            try:
                _iter_dict(_res, el)
            except:
                print(
                    "Error handling the element '{}': {}".format(
                        etree.tostring(el, pretty_print=True),
                        process_tools.get_except_info(),
                    )
                )
                raise
        return [
            "    {}".format(_line) for _line in json.dumps(_res, indent=4).split("\n")[1:-1]
        ]

    def read_configs(self, mp_list):
        # mp_list is a list of tuples (app, config.path)
        # relax instance
        _my_relax = ConfigRelax()
        ROOT_ELEMENTS = ["routes", "menu", "tasks"]
        _total_xml = E.config(
            *[
                getattr(E, _root_el_name)() for _root_el_name in ROOT_ELEMENTS
            ]
        )
        for _app_name, _file in mp_list:
            # simple merger, to be improved
            _full_path = os.path.join(settings.FILE_ROOT, _file)
            if os.path.isfile(_full_path):
                _src_xml = etree.fromstring(
                    file(_full_path, "r").read()
                )
                try:
                    _my_relax.validate(_src_xml)
                except:
                    sys.stderr.write(
                        "*** Error validating {} for app {}: {}\n".format(
                            _full_path,
                            _app_name,
                            process_tools.get_except_info(),
                        )
                    )
                else:
                    for _el_name in ROOT_ELEMENTS:
                        _src_el = _src_xml.find(_el_name)
                        if _src_el is not None:
                            _dst_el = _total_xml.find(_el_name)
                            for _el in _src_el:
                                if _el.tag is not etree.Comment:
                                    _el.attrib["app"] = _app_name
                                    _dst_el.append(_el)
            else:
                sys.stderr.write(
                    "*** file {} does not exist".format(_full_path)
                )
        # sys.exit(0)
        # check for validity
        try:
            _my_relax.validate(_total_xml)
        except:
            sys.stderr.write(
                "*** Error validating merged XML: {}\n".format(
                    process_tools.get_except_info(),
                )
            )
            raise
        # transform XML
        # _total_xml = self.transform(_total_xml)
        # transform to json
        # print("\n".join(self.config_xml_to_json(_total_xml)))
        return self.config_xml_to_json(_total_xml)

    def inject(self, options):
        _v_dict = {}
        for _attr_name, _default in [
            ("ADDITIONAL_ANGULAR_APPS", []),
            ("ICSW_ADDITIONAL_JS", []),
            ("ICSW_ADDITIONAL_HTML", []),
            ("ICSW_ADDITIONAL_APPS", {}),
        ]:
            self.debug("attribute '{}'".format(_attr_name))
            if options["with_addons"]:
                _val = getattr(settings, _attr_name)
            else:
                _val = _default
            self.debug("  ->  {}".format(str(_val)))
            _v_dict[_attr_name] = _val
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
                        for _app in _v_dict["ADDITIONAL_ANGULAR_APPS"]:
                            _injected += 1
                            new_content.append("        \"{}\",".format(_app))
                    elif marker_type == "JAVASCRIPT":
                        for _js in _v_dict["ICSW_ADDITIONAL_JS"]:
                            _injected += 1
                            new_content.append(
                                "        <script src='{}'></script>".format(
                                    os.path.basename(_js)
                                )
                            )
                    elif marker_type == "HTML":
                        for _html in _v_dict["ICSW_ADDITIONAL_HTML"]:
                            _injected += 1
                            new_content.append(file(_html, "r").read())
                    elif marker_type == "MENU":
                        menu_paths = [
                             ("frontend", os.path.join("config", "config.xml"))
                         ] + [
                            (_key, _value["config"]) for _key, _value in _v_dict["ICSW_ADDITIONAL_APPS"].iteritems()
                        ]
                        menu_json_lines = self.read_configs(menu_paths)
                        for _line in menu_json_lines:
                            _injected += 1
                            new_content.append(_line)
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
            codecs.open(dest, "w", "utf-8").write(self._content)


class Command(BaseCommand):
    help = "Inject module code in files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--srcfile",
            action="append",
            dest="files",
            default=[],
            help="Name of the files to modify",

        )
        parser.add_argument(
            "--modify",
            action="store_true",
            default=False,
            help="rewrite file (and disable debug)",
        )
        parser.add_argument(
            "--with-addons",
            type=str,
            default="false",
            help="inject menu JSON",
        )
        parser.add_argument(
            "--cleanup-path",
            action="store_true",
            default=False,
            help="fix wrong relative imports",
        )

    def handle(self, **options):
        if options["with_addons"].lower() in ["false"]:
            options["with_addons"] = False
        else:
            options["with_addons"] = True
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
                f_obj.inject(options)
            f_obj.write()
