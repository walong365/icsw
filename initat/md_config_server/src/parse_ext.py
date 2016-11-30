#!/usr/bin/python-init -Otu

from __future__ import print_function, unicode_literals

import pprint

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
        _args = []
        for _idx, _str in enumerate(_code.stripped_strings):
            if _idx:
                _args = _str.split(";")
        _dict[_cmd] = {
            "args": _args,
            "info": [_entry.string for _entry in _p_list],
            "for_host": True if _cmd.count("HOST") else False,
            "for_service": True if _cmd.count("SVC") else False,
            "for_hostgroup": True if _cmd.count("HOSTGROUP") else False,
            "for_servicegroup": True if _cmd.count("SERVICEGROUP") else False,
        }
    for _cmd in sorted(_dict.keys()):
        _stuff = _dict[_cmd]
        _info = " ".join(_stuff["info"]).replace("\n", " ").replace("  ", " ").replace("  ", " ")
        print("    {} = IcingaCommand(".format(_cmd.lower()))
        print("        name=\"{}\",".format(_cmd))
        print("        args=[{}],".format(", ".join(["\"{}\"".format(_arg.replace("<", "").replace(">", "")) for _arg in _stuff["args"]])))
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
        for _flag in ["host", "service", "hostgroup", "servicegroup"]:
            print("        for_{}={},".format(_flag, _stuff["for_{}".format(_flag)]))
        print("    )")
    # pprint.pprint(_dict)


if __name__ == "__main__":
    main()
