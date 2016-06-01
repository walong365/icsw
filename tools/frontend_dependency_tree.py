#!/usr/bin/python-init -Ot
#
# Copyright (C) 2016 Gregor Kaufmann
#
#
# Send feedback to: <g,kaufmann@init.at>
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


import argparse
import os.path
import re
import time
import glob
from operator import itemgetter, attrgetter, methodcaller

import inflection

from initat.tools import logging_tools


class DirDefinition(object):
    def __init__(self, sink, dir_type, dir_name, file_name, line_num, line):
        self.sink = sink
        self.type = dir_type
        self.name = dir_name
        self.camel_name = inflection.camelize(self.name, False)
        self.hyphen_name = inflection.dasherize(inflection.underscore(self.name))
        self.dot_name = inflection.underscore(self.name).replace("_", ".")
        self.file_name = file_name[len(self.sink.start_path) + 1:]
        self.top_level_dir = self.file_name.split(os.sep)[0]
        self.line_num = line_num
        self.line = line
        self.refs = []
        # check valid name / path
        if self.dot_name.count(".") and self.dot_name.startswith("icsw."):
            self.namespace_ok = True
            _path_parts = ["icsw"] + self.file_name.split(os.sep)[:-1]
            _dot_parts = self.dot_name.split(".")
            if _path_parts[0] == "backend":
                _path_parts = _path_parts[1:]
            self.name_valid = _path_parts == _dot_parts[:len(_path_parts)]
        else:
            self.namespace_ok = False
            self.name_valid = False

    @property
    def is_valid(self):
        return self.namespace_ok and self.name_valid

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "{} {} ({:d}@{})".format(
            self.type[:1].upper(),
            self.name,
            self.line_num,
            self.file_name,
        )

    def add_reference(self, file_name, line_num, line):
        self.refs.append((file_name, line_num, line))


class DataSink(object):
    def __init__(self, start_path):
        self.start_path = start_path
        self._defs = []
        self._type_lut = {}

    def feed(self, file_name, line_num, line, dir_type, dir_name):
        _def = DirDefinition(self, dir_type, dir_name, file_name, line_num, line)
        self._defs.append(_def)
        self._type_lut.setdefault(_def.type, []).append(_def)

    def get_type_defs(self, dir_type):
        return self._type_lut[dir_type]

    def get_types(self):
        return sorted(self._type_lut.keys())


def main(args):
    coffefiles = []
    htmlfiles = []
    for root, dirs, files in os.walk(args.path, topdown=False):
        coffefiles.extend([os.path.join(root, f) for f in files if f.endswith("coffee")])
        htmlfiles.extend([os.path.join(root, f) for f in files if f.endswith("html")])

    print("{:d} Coffee and {:d} HTML files".format(len(coffefiles), len(htmlfiles)))

    def_matcher = re.compile(".*\.(?P<type>(directive|service|controller|factory))\((\'|\")(?P<name>(.*?))(\'|\").*")
    html_matcher = re.compile(".*script type=.text/ng-template. id=(\'|\")(?P<name>.*)(\'|\").")

    my_sink = DataSink(args.path)

    print("Getting defs...")

    # get definitions

    for name in coffefiles:
        for line_num, line in enumerate(open(name, "rb").xreadlines(), 1):
            match = def_matcher.match(line)
            if match:
                _gd = match.groupdict()
                my_sink.feed(name, line_num, line, _gd["type"], _gd["name"])
    print(
        "done (found {:d})".format(
            len(my_sink._defs)
        )
    )

    # find refs in HTML to services

    dir_defs = my_sink.get_type_defs("directive") + my_sink.get_type_defs("controller")
    dir_dict = {}
    for _def in dir_defs:
        dir_dict[_def.camel_name] = _def
        dir_dict[_def.hyphen_name] = _def
    dir_matcher = set(dir_dict.keys())

    _refs = 0
    s_time = time.time()
    for name in htmlfiles:
        for line_num, line in enumerate(open(name, "rb").xreadlines(), 1):
            match = html_matcher.match(line)
            if match:
                _gd = match.groupdict()
                my_sink.feed(name, line_num, line, "html", _gd["name"])
            else:
                # print line
                for word in re.split("([^a-zA-Z\-])+", line):
                    if word in dir_matcher:
                        dir_dict[word].add_reference(name, line_num, line)
                        _refs += 1
    e_time = time.time()
    print(
        "Reference from HTML to directive took {} (found: {:d})".format(
            logging_tools.get_diff_time_str(e_time - s_time),
            _refs,
        )
    )

    # find refs to Services and Factories in coffee
    sf_refs = my_sink.get_type_defs("factory") + my_sink.get_type_defs("service")
    sf_dict = {_sf.camel_name: _sf for _sf in sf_refs}
    sf_matcher = set(sf_dict.keys())
    _refs = 0
    s_time = time.time()
    for name in coffefiles:
        for line_num, line in enumerate(open(name, "rb").xreadlines(), 1):
            # print line
            for word in re.split("([^a-zA-Z])+", line):
                if word in sf_matcher:
                    sf_dict[word].add_reference(name, line_num, line)
                    _refs += 1
    e_time = time.time()
    print(
        "Reference from coffee to service / factory took {} (found: {:d})".format(
            logging_tools.get_diff_time_str(e_time - s_time),
            _refs,
        )
    )

    # generate output
    # raw list
    _list = sum([my_sink.get_type_defs(_type) for _type in my_sink.get_types()], [])

    # filter
    if args.ignore_valid:
        _list = [entry for entry in _list if not entry.is_valid]

    print("{:d} entries in list".format(len(_list)))

    if args.order_by == "name":
        _list = sorted(_list, key=attrgetter("name"))
    if args.order_by == "toplevel":
        _list = sorted(_list, key=attrgetter("top_level_dir"))
    out_list = logging_tools.new_form_list()

    for _def in _list:
        out_list.append(
            [
                logging_tools.form_entry(_def.type, header="Type"),
                logging_tools.form_entry(_def.name, header="Name"),
                logging_tools.form_entry(_def.file_name, header="File"),
                logging_tools.form_entry_right(_def.line_num, header="line"),
                logging_tools.form_entry_right(len(_def.refs), header="#refs"),
                logging_tools.form_entry_center("yes" if _def.namespace_ok else "no", header="NS ok"),
                logging_tools.form_entry_center("yes" if _def.name_valid else "no", header="valid"),
            ]
        )
    print(unicode(out_list))


if __name__ == "__main__":
    DP_LOC = os.path.expanduser("~/.icsw_static_path")
    if os.path.exists(DP_LOC):
        _def_path = file(DP_LOC, "r").read().strip()
    else:
        _def_path = "."
    parser = argparse.ArgumentParser(description="Directive Mapper")
    parser.add_argument("--path", default=_def_path, help="start path [%(default)s], located in {}".format(DP_LOC))
    parser.add_argument("--ignore-valid", default=False, action="store_true", help="ignore entries with valid names [%(default)s]")
    parser.add_argument("--order-by", type=str, default="default", choices=["default", "name", "toplevel"], help="set ordering [%(default)s]")

    args = parser.parse_args()

    parser.print_help()
    main(args)
