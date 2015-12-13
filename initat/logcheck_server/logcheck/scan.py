#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" keeps syslog check commands from FS in sync with database """

import os
import json
from django.db.models import Q
from initat.constants import USER_EXTENSION_ROOT
from initat.cluster.backbone.models import SyslogCheck
from initat.tools import logging_tools, process_tools
from lxml import etree


CONFIG_NG = """
<element name="syslog-check" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="ignore">
        <choice>
            <value>0</value>
            <value>1</value>
        </choice>
    </attribute>
    <attribute name="version">
        <choice>
            <value>1</value>
        </choice>
    </attribute>
    <attribute name="enabled">
        <choice>
            <value>0</value>
            <value>1</value>
        </choice>
    </attribute>
    <element name="parameters">
        <element name="name">
            <text/>
        </element>
        <element name="minutes-to-consider">
            <text/>
        </element>
    </element>
    <element name="expressions">
        <oneOrMore>
            <element name="expression">
                <attribute name="level">
                    <choice>
                        <value>warn</value>
                        <value>crit</value>
                    </choice>
                </attribute>
                <attribute name="format">
                    <choice>
                        <value>re</value>
                    </choice>
                </attribute>
                <text/>
            </element>
        </oneOrMore>
    </element>
</element>
"""


class LogCheckFile(object):
    def __init__(self, scanner, path):
        self.scanner = scanner
        self.name = os.path.basename(path)
        self.path = path
        self.database_obj = None
        self.read()
        self.scanner.add_check(self)

    def update(self, other):
        # copy all relevant content from ohter
        self.content = other.content
        self.xml = other.xml
        self.file_dict = other.file_dict

    def read(self):
        self.content = file(self.path, "r").read()
        self.xml = etree.fromstring(self.content)
        self.valid = self.scanner.relax.validate(self.xml)
        if self.valid:
            if int(self.xml.get("ignore")):
                raise ValueError("{} is valid but to ignore".format(self.name))
            self.log("is valid")
            self.file_dict = {
                "name": str(self.xml.findtext(".//parameters/name")),
                "version": int(self.xml.get("version")),
                "enabled": True if int(self.xml.get("enabled")) else False,
                "minutes_to_consider": int(self.xml.findtext(".//parameters/minutes-to-consider")),
                "expressions": [
                    {
                        "text": str(_el.text),
                        "level": _el.get("level"),
                        "format": _el.get("format")
                    } for _el in self.xml.findall(".//expressions/expression")
                ]
            }
        else:
            self.log(
                "XML is invalid: {}".format(
                    str(self.scanner.relax.error_log),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.scanner.log("[LCF {}] {}".format(self.name, what), log_level)

    def create_database_object(self):
        if self.database_obj is None:
            try:
                self.database_obj = SyslogCheck.objects.get(Q(name=self.file_dict["name"]))
            except SyslogCheck.DoesNotExist:
                new_check = SyslogCheck(
                    name=self.file_dict["name"]
                )
                new_check.save()
                self.database_obj = new_check

    def sync(self):
        # sync database with entries form file_dict
        self.database_obj.xml_source = self.content
        self.database_obj.version = self.file_dict["version"]
        self.database_obj.enabled = self.file_dict["enabled"]
        self.database_obj.minutes_to_consider = self.file_dict["minutes_to_consider"]
        self.database_obj.expressions = json.dumps(self.file_dict["expressions"])
        self.database_obj.save()


class LogcheckScanner(object):
    def __init__(self, proc):
        self.proc = proc
        self.root_dir = os.path.join(USER_EXTENSION_ROOT, "logcheck_server.d")
        self.log("init LogCheckScanner")
        self.relax = etree.RelaxNG(etree.fromstring(CONFIG_NG))
        self.checks = {}
        self.rescan()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.proc.log("[LCS] {}".format(what), log_level)

    def rescan(self):
        pre_checks = []
        if not os.path.isdir(self.root_dir):
            self.log("dir {} does not exist, skipping scan", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("scanning {} for new / updated SyslogCheck(s)".format(self.root_dir))
        for _file in os.listdir(self.root_dir):
            if _file.endswith(".xml"):
                try:
                    _new_file = LogCheckFile(self, os.path.join(self.root_dir, _file))
                except:
                    self.log(
                        "error reading {}: {}".format(
                            _file,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        post_checks = self.checks.keys()

    def add_check(self, check):
        _name = check.file_dict["name"]
        if _name not in self.checks:
            self.log("adding new check '{}' from file".format(_name))
            self.checks[_name] = check
            check.create_database_object()
        else:
            self.checks[_name].update(check)
        self.checks[_name].sync()
