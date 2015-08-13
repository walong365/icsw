#!/usr/bin/python-init -Otu

import os
from lxml import etree


# dumps the current data_store xml structure
# ignore all in sub_dict, is an ancient structure


def _show_subs(tl, sub_dict, tag_dict, depth=0):
    _ind = " " * depth * 4
    print "{}[{} ({}) ->".format(
        _ind,
        tl,
        ", ".join(sorted(tag_dict[tl])),
    )
    for _sub in sub_dict.get(tl, []):
        _show_subs(_sub, sub_dict, tag_dict, depth+1)
    print "{}]".format(_ind)


def main():
    _dir = "/var/cache/rrd/data_store"
    tag_dict = {}
    sub_dict = {}
    top_levels = set()
    for _f in os.listdir(_dir):
        _xml = etree.fromstring(file(os.path.join(_dir, _f), "rb").read())
        for _el in _xml.iter():
            if _el.getparent() is not None:
                sub_dict.setdefault(_el.getparent().tag, set()).add(_el.tag)
            else:
                top_levels.add(_el.tag)
            tag_dict.setdefault(_el.tag, set())
            for _attr in _el.attrib.iterkeys():
                tag_dict[_el.tag].add(_attr)
    if "all" in top_levels:
        top_levels -= {"all"}
    print "top levels: {}".format(sorted(top_levels))
    for _tl in top_levels:
        _show_subs(_tl, sub_dict, tag_dict)

if __name__ == "__main__":
    main()
