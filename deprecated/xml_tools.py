#!/usr/bin/python-init -Ot
#
# Copyright (c) 2001,2002,2003,2004,2005,2007,2008,2009 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" simple xml frontend, no longer in package python-modules-base """

import sys
import xml
import xml.dom.expatbuilder
import xml.dom.minidom
import xml.parsers.expat
import bz2

def get_attribute_dict(node):
    return dict([(str(v.nodeName), str(v.nodeValue)) for v in node.attributes.values()])

def build_var_dict(top_node):
    f_dict = {}
    for el_name, el in [(str(x.nodeName), x) for x in top_node.childNodes if x.attributes]:
        loc_dict = dict([(str(x.nodeName), str(x.nodeValue)) for x in el.attributes.values()])
        loc_value, loc_type = (loc_dict.get("value", ""),
                               loc_dict.get("type", "str"))
        if loc_type == "str":
            f_dict[el_name] = str(loc_value)
        elif loc_type == "int":
            f_dict[el_name] = int(loc_value)
        elif loc_type == "bool":
            if loc_value.lower() == "true":
                f_dict[el_name] = True
            else:
                f_dict[el_name] = False
        elif loc_type == "float":
            f_dict[el_name] = float(loc_value)
        elif loc_type == "None":
            f_dict[el_name] = None
        else:
            f_dict[el_name] = str(loc_value)
    return f_dict

def build_var_dict_fast(node_list):
    f_dict = {}
    for ent in node_list:
        el_name, loc_type, loc_value = (ent["name"], ent["type"], ent["value"])
        if loc_type == "str":
            f_dict[el_name] = str(loc_value)
        elif loc_type == "int":
            f_dict[el_name] = int(loc_value)
        elif loc_type == "bool":
            f_dict[el_name] = bool(loc_value)
        elif loc_type == "float":
            f_dict[el_name] = float(loc_value)
        elif loc_type == "None":
            f_dict[el_name] = None
        else:
            f_dict[el_name] = str(loc_value)
    return f_dict

TOP_ELEMENT_NAME = "content"

class xml_command(xml.dom.minidom.Document):
    def __init__(self, src_type="", src_name=""):
        xml.dom.minidom.Document.__init__(self)
        # parse src string
        if src_type:
            in_bytes = None
            if src_type.lower() == "file":
                in_bytes = file(src_name, "rb").read()
            elif src_type.lower() == "string":
                in_bytes = src_name
            else:
                raise ValueError, "unknown src_type %s" % (src_type)
            if in_bytes:
                if in_bytes.startswith("BZh"):
                    try:
                        in_bytes = bz2.decompress(in_bytes)
                    except:
                        raise ValueError, "Cannot decompress bz2 input: %s (%s)" % (str(sys.exc_info()[0]),
                                                                                    str(sys.exc_info()[1]))
                eb_ns = xml.dom.expatbuilder.ExpatBuilderNS()
                eb_ns.document = self
                eb_ns.curNode = eb_ns.document
                eb_ns._elem_info = eb_ns.document._elem_info
                eb_ns._cdata = False
                eb_ns.parseString(in_bytes)
                # delete parser
                del eb_ns
        self._top_element = self.getElementsByTagName(TOP_ELEMENT_NAME)
        if not self._top_element:
            self._top_element = self.appendChild(self.createElement(TOP_ELEMENT_NAME))
        else:
            self._top_element = self._top_element.item(0)
        for needed in ["flags"]:
            n_struct = self.constrain_nodes_parent_node_name(self._top_element.getElementsByTagName(needed), TOP_ELEMENT_NAME)
            if not n_struct:
                n_struct = self._top_element.appendChild(self.createElement(needed))
            else:
                if len(n_struct) > 1:
                    raise xml.dom.HierarchyRequestErr, "%d '%s'-elements found below '%s'" % (len(n_struct),
                                                                                              needed,
                                                                                              TOP_ELEMENT_NAME)
                n_struct = n_struct[0]
            setattr(self, needed, n_struct)
    def set_command(self, command):
        return self._top_element.appendChild(self.create_var_node("command", command, set_type_info=0))
    def add_flag(self, flag_name, flag_value):
        return self.flags.appendChild(self.create_var_node(flag_name, flag_value))
    def get_command(self):
        c_el = self.constrain_nodes_parent_node_name(self._top_element.getElementsByTagName("command"), TOP_ELEMENT_NAME)
        if c_el:
            c_el = str(c_el[0].attributes["value"].nodeValue)
        else:
            c_el = ""
        return c_el
    def top_element(self):
        return self._top_element
    def constrain_nodes_parent_node_name(self, in_list, parent_name):
        return [node for node in [in_list.item(idx) for idx in range(in_list.length)] if node.parentNode.nodeName == parent_name]
    def create_var_node(self, name, var, set_type_info=1):
        node = self.createElement(name)
        node.setAttribute("value", str(var))
        if set_type_info:
            if type(var) == type(""):
                node.setAttribute("type", "str")
            elif type(var) == type(0):
                node.setAttribute("type", "int")
            elif type(var) == type(0.0):
                node.setAttribute("type", "float")
            elif type(var) == type(False):
                node.setAttribute("type", "bool")
            elif type(var) == type(None):
                node.setAttribute("type", "None")
            else:
                node.setAttribute("type", "unknown")
        return node
    def get_flag_dict(self):
        return build_var_dict(self.flags)
    def __repr__(self):
        return self.toprettyxml("    ")

class xml_entity(object):
    def __init__(self, name, **attrs):
        self.__name = str(name)
        self.__top_node = False
        self.__text = None
        self.__sub_entities = []
        self.__sub_entities_dict = {}
        self.__attributes = {}
        for key, value in attrs.iteritems():
            if key == "top_node":
                self.__top_node = True
            elif key == "text":
                self.__text = str(value)
            else:
                self.__attributes[str(key)] = str(value)
    def get_command(self):
        if self.__top_node:
            if "command" in self.__sub_entities_dict.keys():
                return self.__sub_entities_dict["command"][0]["value"]
            else:
                raise KeyError, "command not defined in entity_list"
        else:
            raise LookupError, "searching for command in non-top node"
    def set_command(self, com):
        if self.__top_node:
            self.add_entity(xml_entity("command", value=com))
        else:
            raise LookupError, "searching for command in non-top node"
    def add_flag(self, f_name, f_value):
        if self.__top_node:
            if not "flags" in self.__sub_entities_dict:
                self.add_entity(xml_entity("flags"))
            self["flags"][0].add_entity(xml_entity_var(f_name, f_value))
        else:
            raise LookupError, "searching for command in non-top node"
    def get_flag_dict(self):
        if self.__top_node:
            if "flags" in self.__sub_entities_dict.keys():
                return build_var_dict_fast(self.__sub_entities_dict["flags"][0].get_entity_list())
            else:
                raise KeyError, "command not defined in entity_list"
        else:
            raise LookupError, "searching for command in non-top node"
    def get_entity_list(self):
        return self.__sub_entities
    def add_entity(self, ent):
        self.__sub_entities.append(ent)
        self.__sub_entities_dict.setdefault(ent["name"], []).append(ent)
        return ent
    def __getitem__(self, k):
        if k == "name":
            return self.__name
        elif k in self.__attributes:
            return self.__attributes[k]
        elif k in self.__sub_entities_dict.keys():
            return self.__sub_entities_dict[k]
        else:
            raise KeyError, "key %s not defined for xml_entity %s" % (k, self.__name)
    def has_sub_entity(self, k):
        return k in self.__sub_entities_dict
    def toxml(self):
        # flat xml output
        if self.__sub_entities:
            return "%s<%s%s>%s%s</%s>" % (self.__top_node and "<?xml version=\"1.0\" ?>" or "",
                                          self.__name,
                                          self.__attributes and " %s" % (" ".join(["%s=\"%s\"" % (k, v) for k, v in self.__attributes.iteritems()])) or "",
                                          "".join(["".join([y for y in x.toxml().split("\n")]) for x in self.__sub_entities]),
                                          self.__text or "",
                                          self.__name)
        else:
            if self.__text:
                return "%s<%s%s>%s</%s>" % (self.__top_node and "<?xml version=\"1.0\" ?>" or "",
                                            self.__name,
                                            self.__attributes and " %s" % (" ".join(["%s=\"%s\"" % (k, v) for k, v in self.__attributes.iteritems()])) or "",
                                            self.__text,
                                            self.__name)
            else:
                return "%s<%s%s/>" % (self.__top_node and "<?xml version=\"1.0\" ?>" or "",
                                      self.__name,
                                      self.__attributes and " %s" % (" ".join(["%s=\"%s\"" % (k, v) for k, v in self.__attributes.iteritems()])) or "")
    def __repr__(self):
        # beautified xml output
        if self.__sub_entities:
            return "%s<%s%s>\n%s\n%s</%s>" % (self.__top_node and "<?xml version=\"1.0\" ?>\n" or "",
                                              self.__name,
                                              self.__attributes and " %s" % (" ".join(["%s=\"%s\"" % (k, v) for k, v in self.__attributes.iteritems()])) or "",
                                              "\n".join(["\n".join(["    %s" % (y) for y in str(x).split("\n")]) for x in self.__sub_entities]),
                                              "%s\n" % (self.__text) if self.__text else "",
                                              self.__name)
        else:
            if self.__text:
                return "%s<%s%s>%s</%s>" % (self.__top_node and "<?xml version=\"1.0\" ?>\n" or "",
                                            self.__name,
                                            self.__attributes and " %s" % (" ".join(["%s=\"%s\"" % (k, v) for k, v in self.__attributes.iteritems()])) or "",
                                            self.__text,
                                            self.__name)
            else:
                return "%s<%s%s/>" % (self.__top_node and "<?xml version=\"1.0\" ?>\n" or "",
                                      self.__name,
                                      self.__attributes and " %s" % (" ".join(["%s=\"%s\"" % (k, v) for k, v in self.__attributes.iteritems()])) or "")

class xml_entity_var(xml_entity):
    def __init__(self, name, value):
        if type(value) == type(""):
            loc_type = "str"
        elif type(value) == type(0):
            loc_type = "int"
        elif type(value) == type(0.0):
            loc_type = "float"
        elif type(value) == type(False):
            loc_type = "bool"
        elif type(value) == type(None):
            loc_type = "None"
        else:
            loc_type = "unknown"
        xml_entity.__init__(self, name, type=loc_type, value=value)
    
class fast_xml_parser(object):
    def __init__(self):
        pass
    def start_element(self, name, attrs):
        attrs = dict([(str(k), str(v)) for k, v in attrs.iteritems()])
        if not self.__top_entity:
            self.__top_entity = xml_entity(name, top_node=True, **attrs)
            self.__e_list = [self.__top_entity]
        else:
            new_entity = xml_entity(name, **attrs)
            self.__e_list[-1].add_entity(new_entity)
            self.__e_list.append(new_entity)
    def end_element(self, name):
        self.__e_list.pop(-1)
    def char_data(self, data):
        pass
    def parse_it(self, in_bytes):
        self.parser = xml.parsers.expat.ParserCreate()
        self.parser.StartElementHandler = self.start_element
        self.parser.EndElementHandler = self.end_element
        self.parser.CharacterDataHandler = self.char_data
        self.__top_entity = None
        self.parser.Parse(in_bytes, True)
        return self.__top_entity
    
if __name__ == "__main__":
#     import time
#     import pprint
#     my_p = fast_xml_parser()
#     in_str = file("test.xml", "r").read()
#     s_time = time.time()
#     xml_s = my_p.parse_it(in_str)
#     e_time = time.time()
#     print "%.3f" % (e_time - s_time)
#     pprint.pprint(xml_s)
#     print xml_s.get_command()
#     print xml_s.get_flag_dict()
#     pprint.pprint([build_var_dict_fast(x.get_entity_list()) for x in xml_s["packages"][0]["package"]])
#     print "-" * 50
#     my_el = xml_entity("content", top_node=True)
#     my_el.set_command("bla")
#     my_el.add_flag("bz2compression", True)
#     print my_el
#     print my_el.toxml()
    print "Loadable module, exiting ..."
    sys.exit(-1)
