# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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
""" server command structure definitions """

import base64
import bz2
import collections
import datetime
import json
import marshal
import os
import pickle
import re

from lxml import etree
from lxml.builder import ElementMaker

from initat.host_monitoring.limits import mon_STATE_CRITICAL, mon_STATE_WARNING, \
    mon_STATE_OK
from initat.tools import logging_tools

XML_NS = "http://www.initat.org/lxml/ns"


def net_to_sys(in_val):
    try:
        result = pickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise ValueError
    return result


def sys_to_net(in_val):
    return pickle.dumps(in_val)

SRV_REPLY_STATE_OK = 0
SRV_REPLY_STATE_WARN = 1
SRV_REPLY_STATE_ERROR = 2
SRV_REPLY_STATE_CRITICAL = 3
SRV_REPLY_STATE_UNSET = 4


def srv_reply_to_log_level(srv_reply_state):
    return {
        SRV_REPLY_STATE_OK: logging_tools.LOG_LEVEL_OK,
        SRV_REPLY_STATE_WARN: logging_tools.LOG_LEVEL_WARN,
        SRV_REPLY_STATE_ERROR: logging_tools.LOG_LEVEL_ERROR,
    }.get(srv_reply_state, logging_tools.LOG_LEVEL_ERROR)


def srv_reply_to_nag_state(srv_reply_state):
    return {
        SRV_REPLY_STATE_OK: mon_STATE_OK,
        SRV_REPLY_STATE_WARN: mon_STATE_WARNING,
        SRV_REPLY_STATE_ERROR: mon_STATE_CRITICAL,
    }.get(srv_reply_state, mon_STATE_CRITICAL)


def nag_state_to_srv_reply(nag_state):
    return {
        mon_STATE_OK: SRV_REPLY_STATE_OK,
        mon_STATE_WARNING: SRV_REPLY_STATE_WARN,
        mon_STATE_CRITICAL: SRV_REPLY_STATE_ERROR,
    }.get(nag_state, SRV_REPLY_STATE_ERROR)


def log_level_to_srv_reply(log_level):
    return {
        logging_tools.LOG_LEVEL_OK: SRV_REPLY_STATE_OK,
        logging_tools.LOG_LEVEL_WARN: SRV_REPLY_STATE_WARN,
        logging_tools.LOG_LEVEL_ERROR: SRV_REPLY_STATE_ERROR,
    }.get(log_level, SRV_REPLY_STATE_ERROR)


def srv_reply_state_is_valid(srv_reply_state):
    return srv_reply_state in [
        SRV_REPLY_STATE_CRITICAL, SRV_REPLY_STATE_ERROR, SRV_REPLY_STATE_OK, SRV_REPLY_STATE_WARN
    ]


def compress(in_str, **kwargs):
    if kwargs.get("marshal", False):
        in_str = marshal.dumps(in_str)
    elif kwargs.get("pickle", False):
        in_str = pickle.dumps(in_str)
    elif kwargs.get("json", False):
        in_str = json.dumps(in_str)
    # print("*", in_str)
    # print("*", str.encode(in_str))
    # print("*", bz2.compress(str.encode(in_str)))
    # print("*", base64.b64encode(bz2.compress(str.encode(in_str))))

    if isinstance(in_str, str):
        return base64.b64encode(bz2.compress(str.encode(in_str)))
    else:
        return base64.b64encode(bz2.compress(in_str))


def decompress(in_str, **kwargs):
    ret_struct = bz2.decompress(base64.b64decode(in_str))
    if kwargs.get("marshal", False):
        ret_struct = marshal.loads(ret_struct)
    elif kwargs.get("pickle", False):
        ret_struct = pickle.loads(ret_struct)
    elif kwargs.get("json", False):
        ret_struct = json.loads(ret_struct)
    return ret_struct


def add_namespace(in_str):
    # add namespace info to all elements, hacky code
    # mostly needed to add NS info to C-Code generated XML
    def _transform(sub_str):
        return sub_str.replace("<", "<ns:").replace("<ns:/", "</ns:")
    _parts = _transform(in_str).split(">", 1)
    in_str = "{} xmlns:ns=\"{}\">{}".format(
        _parts[0],
        XML_NS,
        _parts[1],
    )
    return srv_command(source=in_str)


class srv_command(object):
    # __slots__ = ("__builder", "__tree", "srvc_open", "ignore_unicode_errors")
    srvc_open = 0

    def __init__(self, **kwargs):
        # init tree with None so that __del__ always succeeds
        self.__tree = None
        srv_command.srvc_open += 1
        self.__builder = ElementMaker(namespace=XML_NS)
        self.ignore_unicode_errors = False
        if "source" in kwargs:
            if isinstance(kwargs["source"], str):
                self.__tree = etree.fromstring(kwargs["source"])
            elif isinstance(kwargs["source"], bytes):
                self.__tree = etree.fromstring(kwargs["source"].decode("utf-8"))
            else:
                self.__tree = kwargs["source"]
        else:
            self.__tree = self.__builder.ics_batch(
                self.__builder.source(
                    host=os.uname()[1],
                    pid="{:d}".format(os.getpid())),
                self.__builder.command(kwargs.pop("command", "not set")),
                self.__builder.identity(kwargs.pop("identity", "not set")),
                # set srv_command version
                srvc_version="{:d}".format(kwargs.pop("srvc_version", 1)))
            for key, value in kwargs.items():
                self[key] = value

    def xpath(self, *args, **kwargs):
        if "namespace" not in kwargs:
            kwargs["namespaces"] = {"ns": XML_NS}
        start_el = kwargs.pop("start_el", self.__tree)
        return start_el.xpath(*args, smart_strings=kwargs.pop("smart_strings", False), **kwargs)

    def set_result(self, ret_str, level=SRV_REPLY_STATE_OK):
        if "result" not in self:
            self["result"] = None
        if level not in [SRV_REPLY_STATE_ERROR, SRV_REPLY_STATE_WARN, SRV_REPLY_STATE_OK, SRV_REPLY_STATE_CRITICAL, SRV_REPLY_STATE_UNSET]:
            raise ValueError("srv_com_level '{}' not valid".format(level))
        self["result"].attrib.update(
            {
                "reply": str(ret_str),
                "state": "{:d}".format(level)
            }
        )

    def get_result(self):
        if "result" not in self:
            return ("no result node found", SRV_REPLY_STATE_CRITICAL)
        else:
            _attrib = self["result"].attrib
            return (_attrib.get("reply", "no reply-string set"), int(_attrib.get("state", "{:d}".format(SRV_REPLY_STATE_OK))))

    def builder(self, tag_name=None, *args, **kwargs):
        if tag_name is None:
            return self.__builder
        elif tag_name == "":
            tag_name = "__empty__"
        if isinstance(tag_name, int):
            tag_name = "__int__{:d}".format(tag_name)
        elif tag_name is None:
            tag_name = "__none__"
        if tag_name.count("/"):
            tag_name = tag_name.replace("/", "__slash__")
            kwargs["escape_slash"] = "1"
        if tag_name.count("@"):
            tag_name = tag_name.replace("@", "__atsign__")
            kwargs["escape_atsign"] = "1"
        if tag_name.count("&"):
            tag_name = tag_name.replace("&", "__amp__")
            kwargs["escape_ampersand"] = "1"
        if tag_name.count(";"):
            tag_name = tag_name.replace(";", "__semicolon__")
            kwargs["escape_semicolon"] = "1"
        if tag_name[0].isdigit():
            tag_name = "__fdigit__{}".format(tag_name)
            kwargs["first_digit"] = "1"
        if tag_name.count(":"):
            tag_name = tag_name.replace(":", "__colon__")
            kwargs["escape_colon"] = "1"
        # escape special chars
        for s_char in "[] ":
            tag_name = tag_name.replace(s_char, "_0x0{:x}_".format(ord(s_char)))
        return getattr(self.__builder, tag_name)(*args, **kwargs)

    def _interpret_tag(self, el, tag_name):
        iso_re = re.compile("^(?P<pre>.*)_0x0(?P<code>[^_]\S+)_(?P<post>.*)")
        if tag_name.startswith("{http"):
            tag_name = tag_name.split("}", 1)[1]
        if "escape_slash" in el.attrib:
            tag_name = tag_name.replace("__slash__", "/")
        if "escape_atsign" in el.attrib:
            tag_name = tag_name.replace("__atsign__", "@")
        if "first_digit" in el.attrib:
            tag_name = tag_name.replace("__fdigit__", "")
        if "escape_colon" in el.attrib:
            tag_name = tag_name.replace("__colon__", ":")
        if "escape_ampersand" in el.attrib:
            tag_name = tag_name.replace("__amp__", "&")
        if "escape_semicolon" in el.attrib:
            tag_name = tag_name.replace("__semicolon__", ";")
        if tag_name.startswith("__int__"):
            tag_name = int(tag_name[7:])
        elif tag_name == "__empty__":
            tag_name = ""
        elif tag_name == "__none__":
            tag_name = None
        else:
            while True:
                cur_match = iso_re.match(tag_name)
                if cur_match:
                    tag_name = "{}{}{}".format(
                        cur_match.group("pre"),
                        chr(int(cur_match.group("code"), 16)),
                        cur_match.group("post"))
                else:
                    break
        return tag_name

    @property
    def tree(self):
        return self.__tree

    def get_int(self, key, default=0):
        if key in self:
            return int(self[key].text)
        else:
            return default

    def __contains__(self, key):
        xpath_str = "/ns:ics_batch/{}".format("/".join(["ns:{}".format(sub_arg) for sub_arg in key.split(":")]))
        xpath_res = self.__tree.xpath(xpath_str, smart_strings=False, namespaces={"ns": XML_NS})
        return True if len(xpath_res) else False

    def get_element(self, key):
        if key:
            xpath_str = "/ns:ics_batch/{}".format(
                "/".join(
                    [
                        "ns:{}".format(sub_arg) for sub_arg in key.split(":")
                    ]
                )
            )
        else:
            xpath_str = "/ns:ics_batch"
        return self.__tree.xpath(xpath_str, smart_strings=False, namespaces={"ns": XML_NS})

    def __delitem__(self, key):
        xpath_res = self.get_element(key)
        for _res in xpath_res:
            _res.getparent().remove(_res)

    def __getitem__(self, key):
        if key.startswith("*"):
            interpret = True
            key = key[1:]
        else:
            interpret = False
        xpath_res = self.get_element(key)
        if len(xpath_res) == 1:
            xpath_res = xpath_res[0]
            if xpath_res.attrib.get("type") == "dict":
                return self._interpret_el(xpath_res)
            else:
                if interpret:
                    return self._interpret_el(xpath_res)
                else:
                    return xpath_res
        elif len(xpath_res) > 1:
            if interpret:
                return [self._interpret_el(cur_res) for cur_res in xpath_res]
            else:
                return [cur_res for cur_res in xpath_res]
        else:
            raise KeyError("key {} not found in srv_command".format(key))

    def _to_unicode(self, value):
        if isinstance(value, bool):
            return "True" if value else "False", "bool"
        elif isinstance(value, int):
            return ("{:d}".format(value), "int")
        else:
            return (value, "str")

    def __setitem__(self, key, value):
        if key:
            cur_element = self._create_element(key)
        else:
            cur_element = self.__tree
        if etree.iselement(value):
            cur_element.append(value)
        else:
            self._element(value, cur_element)

    def delete_subtree(self, key):
        xpath_str = "/ns:ics_batch/{}".format("/".join(["ns:{}".format(sub_arg) for sub_arg in key.split(":")]))
        for result in self.__tree.xpath(xpath_str, smart_strings=False, namespaces={"ns": XML_NS}):
            result.getparent().remove(result)

    def _element(self, value, cur_element=None):
        if cur_element is None:
            cur_element = self.builder("value")
        if isinstance(value, str):
            try:
                cur_element.text = value
            except ValueError:
                try:
                    cur_element.text = value.decode("utf8")
                except ValueError:
                    if self.ignore_unicode_errors:
                        cur_element.text = ""
                    else:
                        raise
            cur_element.attrib["type"] = "str"
        elif isinstance(value, int):
            cur_element.text = "{:d}".format(value)
            cur_element.attrib["type"] = "int"
        elif isinstance(value, float):
            cur_element.text = "{:f}".format(value)
            cur_element.attrib["type"] = "float"
        elif value is None:
            cur_element.text = None
            cur_element.attrib["type"] = "none"
        elif isinstance(value, datetime.date):
            cur_element.text = value.isoformat()
            cur_element.attrib["type"] = "date"
        elif isinstance(value, datetime.datetime):
            cur_element.text = value.isoformat()
            cur_element.attrib["type"] = "datetime"
        elif isinstance(value, bool):
            cur_element.text = str(value)
            cur_element.attrib["type"] = "bool"
        elif isinstance(value, dict) or isinstance(value, collections.OrderedDict):
            cur_element.attrib["type"] = "dict"
            for sub_key, sub_value in value.items():
                sub_el = self._element(sub_value, self.builder(sub_key))
                if isinstance(sub_key, int):
                    sub_el.attrib["dict_key"] = "__int__{:d}".format(sub_key)
                elif sub_key is None:
                    sub_el.attrib["dict_key"] = "__none__"
                else:
                    sub_el.attrib["dict_key"] = sub_key
                cur_element.append(sub_el)
        elif isinstance(value, list):
            cur_element.attrib["type"] = "list"
            for sub_value in value:
                sub_el = self._element(sub_value)
                cur_element.append(sub_el)
        elif isinstance(value, tuple):
            cur_element.attrib["type"] = "tuple"
            for sub_value in value:
                sub_el = self._element(sub_value)
                cur_element.append(sub_el)
        elif isinstance(value, bytes):
            cur_element.attrib["type"] = "bytes"
            cur_element.text = value.decode("utf-8")
        elif etree.iselement(value):
            cur_element = value
        else:
            raise ValueError("_element: unknown value type '{}'".format(type(value)))
        return cur_element
# #    def _escape_key(self, key_str):
# #        return key_str.replace("/", "r")

    def _escape_key(self, key_str):
        return key_str.replace("/", "__slash__").replace("@", "__atsign__")

    def _create_element(self, key):
        """ creates all element(s) down to key.split(":") """
        xpath_str = "/ns:ics_batch"
        cur_element = self.__tree.xpath(xpath_str, smart_strings=False, namespaces={"ns": XML_NS})
        if len(cur_element):
            _with_ns = True
        else:
            # check for XML without namespace (from tell_mother for instance)
            xpath_str = "/ics_batch"
            cur_element = self.__tree.xpath(xpath_str, smart_strings=False)
            _with_ns = False
        cur_element = cur_element[0]
        for cur_key in key.split(":"):
            if _with_ns:
                xpath_str = "{}/ns:{}".format(xpath_str, self._escape_key(cur_key))
            else:
                xpath_str = "{}/{}".format(xpath_str, self._escape_key(cur_key))
            full_key = "{{{}}}{}".format(XML_NS, self._escape_key(cur_key))
            sub_el = cur_element.find("./{}".format(full_key))
            if sub_el is not None:
                cur_element = sub_el
            else:
                sub_el = self.builder(cur_key)  # getattr(self.__builder, cur_key)()
                cur_element.append(sub_el)
            cur_element = sub_el
        return cur_element

    def _interpret_el(self, top_el):
        value, el_type = (top_el.text, top_el.attrib.get("type", None))
        if el_type == "dict":
            result = {}
            for el in top_el:
                if "dict_key" in el.attrib:
                    key = self._interpret_tag(el, el.attrib["dict_key"])
                else:
                    key = self._interpret_tag(el, el.tag.split("}", 1)[1])
                result[key] = self._interpret_el(el)
        elif el_type == "list":
            result = []
            for el in top_el:
                result.append(self._interpret_el(el))
        elif el_type == "tuple":
            result = []
            for el in top_el:
                result.append(self._interpret_el(el))
            result = tuple(result)
        else:
            if el_type == "int":
                value = int(value)
            elif el_type == "bool":
                if isinstance(value, str):
                    value = True if len(value) and value[0].lower() in ["t", "1", "y"] else False
                else:
                    value = bool(value)
            elif el_type == "date":
                value_dt = datetime.datetime.strptime(value, "%Y-%m-%d")
                value = datetime.date(value_dt.year, value_dt.month, value_dt.day)
            elif el_type == "datetime":
                value = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            elif el_type == "float":
                value = float(value)
            elif el_type == "str":
                value = value or ""
            return value
        return result

    def get(self, key, def_value=None):
        # get does NOT support the automatic interpretation of elements via the "*{key}" snytax (and never will ...)
        xpath_str = ".//{}".format("/".join(["ns:{}".format(sub_arg) for sub_arg in key.split(":")]))
        xpath_res = self.__tree.xpath(xpath_str, smart_strings=False, namespaces={"ns": XML_NS})
        if len(xpath_res) == 1:
            return xpath_res[0].text
        elif len(xpath_res) > 1:
            return [cur_res.text for cur_res in xpath_res]
        else:
            return def_value

    def update_source(self):
        _source = self.__tree.xpath(".//ns:source", smart_strings=False, namespaces={"ns": XML_NS})
        if len(_source):
            _source[0].attrib.update(
                {
                    "host": os.uname()[1],
                    "pid": "{:d}".format(os.getpid()),
                    "sendcounter": "{:d}".format(
                        1 + self.sendcounter
                    ),
                }
            )

    @property
    def sendcounter(self):
        _source = self.__tree.xpath(".//ns:source", smart_strings=False, namespaces={"ns": XML_NS})
        if len(_source):
            return int(_source[0].attrib.get("sendcounter", 0))

    def pretty_print(self):
        return etree.tostring(self.__tree, encoding="unicode", pretty_print=True)

    def __str__(self):
        return etree.tostring(self.__tree, encoding="unicode")

    def tostring(self, **kwargs):
        return etree.tostring(self.__tree, **kwargs)

    def get_log_tuple(self, swap=False, map_to_log_level=True):
        # returns the reply / state attribute, mapped to logging_tool levels
        res_node = self.xpath(".//ns:result", smart_strings=False)
        if len(res_node):
            res_node = res_node[0]
            ret_str, ret_state = res_node.attrib["reply"], int(res_node.attrib["state"])
        else:
            ret_str, ret_state = ("no result element found", SRV_REPLY_STATE_CRITICAL)
        if map_to_log_level:
            ret_state = srv_reply_to_log_level(ret_state)
        if swap:
            return ret_state, ret_str
        else:
            return ret_str, ret_state

    def __del__(self):
        del self.__tree
        del self.__builder
        srv_command.srvc_open -= 1
        # print "del", srv_command.srvc_open

    def __len__(self):
        return len(etree.tostring(self.tree))
