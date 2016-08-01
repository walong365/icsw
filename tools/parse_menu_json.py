#!/usr/bin/python-init -Otu

import sys
sys.path.append(".")
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.cluster.backbone.models import device, csw_permission
from lxml import etree
from lxml.builder import E
import pprint
import inflection

# f_path = "/usr/local/share/home/local/development/git/icsw/initat/cluster/frontend/static/icsw/tools/init.coffee"
# f_path = "/usr/local/share/home/local/development/git/liebherr/initat/cluster/liebherr/static/icsw/liebherr/cransys.coffee"


class Route(object):
    def __init__(self, name):
        self.name = name
        self.dicts = {}

    def _trim_value(self, value):
        if value.isdigit():
            return int(value)
        elif value[0] in ["'", '"']:
            return value[1:-1]
        elif value[0] in ["["]:
            return [self._trim_value(_p.strip()) for _p in value[1:-1].strip().split(",")]
        else:
            return value

    def add_sub(self, name):
        self.dicts[name] = {}

    def add_sub2(self, name, sub_name):
        self.dicts[name][sub_name] = {}

    def add_sub_element(self, name, key, value):
        self.dicts[name][key] = self._trim_value(value)

    def add_sub2_element(self, name, sub_name, key, value):
        self.dicts[name][sub_name][key] = self._trim_value(value)

    def __unicode__(self):
        return "Route {} ({:d})".format(self.name, len(self.dicts))

    def __repr__(self):
        return unicode(self)

    def _list_to_xml(self, l_name, l_values):
        _xml = getattr(E, l_name)(type="list")
        for _value in l_values:
            if l_name == "rights":
                if not _value.startswith("$$") and not _value.startswith("backbone"):
                    _value = "backbone.{}".format(_value)
            _xml.append(E.value(_value))
        return _xml

    def _dict_to_xml(self, s_dict, d_name):

        _allowed_keys = {
            "stateData": ["url", "template", "templateUrl", "resolve", "abstract"],
            "icswData": [
                "pageTitle", "licenses", "menuEntry",
                "dashboardEntry", "rights", "menuHeader",
                "service_types", "redirect_to_from_on_error",
                "valid_for_quicklink",
            ],
            "menuEntry": [
                "ordering", "menukey", "icon",
                "preSpacer", "postSpacer", "name", "labelClass",
            ],
            "menuHeader": [
                "ordering", "name", "key", "icon",
            ],
            "dashboardEntry":  [
                "size_x", "size_y", "allow_state", "default_enabled",
                "valid_for_quicklink",
            ],
        }
        _list_keys = ["licenses", "service_types", "rights"]
        _dict_keys = ["menuEntry", "dashboardEntry", "menuHeader"]
        _bool_keys = [
            "allow_state", "redirect_to_from_on_error", "resolve", "valid_for_quicklink",
            "preSpacer", "postSpacer", "default_enabled", "abstract",
        ]
        _allowed_keys = _allowed_keys[d_name]
        _xml = getattr(E, d_name)(type="dict")
        _dict = s_dict[d_name]
        for _key in _dict.keys():
            if _key not in _allowed_keys:
                raise KeyError(
                    "key '{}' not in {} ({})".format(
                        _key,
                        str(_allowed_keys),
                        d_name,
                    )
                )
            _t_key = inflection.camelize(_key, uppercase_first_letter=False)
            if _key in _list_keys:
                _xml.append(self._list_to_xml(_t_key, _dict[_key]))
            elif _key in _dict_keys:
                _xml.append(self._dict_to_xml(_dict, _key))
            elif _key in _bool_keys:
                _xml.attrib["{}_bool".format(_t_key)] = "yes" if _dict[_key] else "no"
            else:
                _val = _dict[_key]
                if type(_val) in [int, long]:
                    _xml.attrib["{}_int".format(_t_key)] = "{:d}".format(_val)
                else:
                    _xml.attrib["{}_str".format(_t_key)] = _val
        return _xml

    def to_xml(self):
        _r = E.route(
            name=self.name
        )
        for _sn in ["stateData", "icswData"]:
            _r.append(self._dict_to_xml(self.dicts, _sn))
        return _r


def main():
    routes = []
    _found = False
    for _line in file(f_path, "r").xreadlines():
        _line = _line.rstrip()
        if _line.lstrip().startswith("\"ICSW_MENU_JSON\", {"):
            _found = True
        elif _line == "    }":
            _found = False
        elif _found:
            _fs = _line.strip()
            if _fs.startswith("#"):
                continue
            _indent = len(_line) - len(_line.lstrip())
            if _indent == 8:
                # start / stop
                if _fs == "}":
                    # stop
                    routes.append(cur_r)
                else:
                    cur_r = Route(_fs.split("\"")[1])
            elif _indent == 12:
                cur_subs = _fs.replace(":", "")
                cur_r.add_sub(cur_subs)
            elif _indent == 16:
                _parts = [_p.strip() for _p in _fs.strip().split(":") if _p.strip()]
                if len(_parts) == 2:
                    cur_r.add_sub_element(cur_subs, _parts[0], _parts[1])
                else:
                    cur_subs2 = _parts[0]
                    cur_r.add_sub2(cur_subs, cur_subs2)
            elif _indent == 20:
                _key, _value = [_p.strip() for _p in _fs.strip().split(":")]
                cur_r.add_sub2_element(cur_subs, cur_subs2, _key, _value)
            else:
                print("Unhandled indent level {:d}: {}".format(_indent, _fs))
    xml_routes = E.routes()
    for _r in routes:
        xml_routes.append(_r.to_xml())
    _my_relax = MenuRelax()
    print etree.tostring(xml_routes, pretty_print=True)
    _my_relax.validate(xml_routes)


if __name__ == "__main__":
    main()
