#!/usr/bin/python-init -Otu
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" parse docupage for external icinga commands """

from __future__ import print_function, unicode_literals

from bs4 import BeautifulSoup


def main():
    _f = BeautifulSoup(file("extcommands2.html", "r").read(), "html.parser")
    _dict = {}
    # print(_f)
    for entry in _f.find_all("span", class_="bold"):
        _p = entry.find_parent("p")
        _cmd = _p("strong")[0].string
        _p_list = []
        _next_p = _p
        while True:
            _next_p = _next_p.find_next_sibling("p")
            if not _next_p:
                break
            if _next_p.find("strong"):
                break
            else:
                _p_list.append(_next_p)
        _code = _p_list.pop(0)
        _args = None
        for _idx, _str in enumerate(_code.stripped_strings):
            if _idx:
                _args = _str
        _dict[_cmd] = {
            "args": _args,
            "info": [_entry.string for _entry in _p_list],
        }
    for _cmd in sorted(_dict.keys()):
        _stuff = _dict[_cmd]
        # info string
        _info = " ".join(_stuff["info"]).replace("\n", " ").replace("  ", " ").replace("  ", " ")
        print("    {} = IcingaCommand(".format(_cmd.lower()))
        print("        name=\"{}\",".format(_cmd))
        # arguments
        _args = _stuff["args"]
        if _args:
            if _args.count("["):
                _args = _args.split(";")
                # print("*", _args)
                # sys.exit(0)
            else:
                _args = _args.split(";")
            print("        args=[")
            _arg_names = []
            _next_opt = False
            for _arg in _args:
                _this_opt = _next_opt
                _next_opt = False
                if _arg.endswith("["):
                    _next_opt = True
                elif _arg.endswith("]"):
                    _this_opt = True
                _arg = _arg.replace("<", "").replace(">", "").replace("[", "").replace("]", "")
                _arg_names.append(_arg)
                if _this_opt:
                    print("            IcingaCommandArg(\"{}\", optional=True),".format(_arg))
                else:
                    print("            IcingaCommandArg(\"{}\", optional=False),".format(_arg))
            print("        ],")
            for arg_name, flag_name in [
                ("host_name", "for_host"),
                ("service_description", "for_service"),
                ("contact_name", "for_contact"),
                ("contactgroup_name", "for_contactgroup"),
                ("servicegroup_name", "for_servicegroup"),
                ("hostgroup_name", "for_hostgroup"),
            ]:
                _stuff[flag_name] = arg_name in _arg_names
        else:
            print("        args=[],")
        # print("        args=[{}],".format(", ".join(["\"{}\"".format(_arg.replace("<", "").replace(">", "")) for _arg in _args])))
        # info
        _parts = _info.split()
        _first = True
        while _parts:
            if _first:
                _pf = "info="
                _first = False
            else:
                _pf = "     "
            _line = ""
            while len(_line) < 60 and _parts:
                _line = "{} {}".format(_line, _parts.pop(0)).strip()
            _line = _line.replace("\"", "\\\"")
            print("        {}\"{}{}".format(_pf, _line, " \"" if _parts else "\",")),
        for _flag in ["host", "service", "hostgroup", "servicegroup", "contact", "contactgroup"]:
            print("        for_{}={},".format(_flag, _stuff.get("for_{}".format(_flag), False)))
        print("    )")
    # pprint.pprint(_dict)


if __name__ == "__main__":
    main()
