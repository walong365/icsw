#!/usr/bin/python-init -Otu

from lxml import html, etree
from lxml.html.clean import clean_html
import re

_f = "all_forms.html"

_c = file(_f, "r").read()

_h = html.fromstring(_c)

for el in _h.xpath(".//*"):
    if el.tag == "script":
        _scr = html.fromstring(el.text)
        el.text = None
        el.append(_scr)

for el in _h.xpath(".//*"):
    # print el.tag
    _del_keys = []
    for _key, _value in el.attrib.iteritems():
        if _key == "class" and not _value.strip():
            _del_keys.append(_key)
        else:
            el.attrib[_key] = _value.replace("\n", "").strip()
    for _dk in _del_keys:
        del el.attrib[_dk]

_c = html.tostring(_h, pretty_print=True)

_start = 0
_num = 0
while True:
    _found = list(re.finditer("<input ", _c[_start:]))
    if _found:
        _num += 1
        m = _found[0]
        # print m.start(), m.end()
        close_start = list(re.finditer(">", _c[_start + m.end():]))[0].start()
        # print "*", _c[_start + m.start(): _start + m.end() + close_start + 1]
        _c = _c[:_start + m.end() + close_start] + "></input>" + _c[m.end() + _start + close_start + 1:]
        # print _c[_start + m.start(): _start + m.end() + close_start + 20]
        _start = _start + m.end() + close_start + 2
    else:
        break

_c = _c.replace(" checked ", " checked=\"checked\" ")
_c = _c.replace(" multiple ", " multiple=\"multiple\" ")

print _c
