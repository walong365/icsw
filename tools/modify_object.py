#!/usr/bin/python-init -Otu
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" script to modify objects via the REST api """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from lxml import etree # @UnresolvedImport
import argparse
import requests

class rest_client(object):
    def __init__(self, options):
        self.options = options
        self.base_url = "http://%s:%d/%s/%s/" % (
            self.options.host,
            self.options.port,
            self.options.path,
            self.options.model)
        self._auth_obj = requests.auth.HTTPBasicAuth(self.options.user, self.options.password)
        # search cache
        self.__search_cache = {}
    @property
    def list_url(self):
        return "%s?format=%s" % (self.base_url, self.options.format)
    @property
    def detail_url(self):
        return "%s%d/?format=%s" % (self.base_url, self.options.pk, self.options.format)
    @property
    def create_url(self):
        return "%s?format=%s" % (self.base_url, self.options.format)
    @property
    def delete_url(self):
        return "%s%d/?format=%s" % (self.base_url, self.options.pk, self.options.format)
    def build_data_dict(self):
        return dict([(key, value) for key, value in [cur_part.split(":", 1) for cur_part in (self.options.data or [])]])
    def list(self, **kwargs):
        to_xml = kwargs.pop("xml", False)
        _resp = requests.get(self.list_url, auth=self._auth_obj, **kwargs)
        if to_xml:
            _resp = self.to_xml(_resp)
        return _resp
    def detail(self, **kwargs):
        return requests.get(self.detail_url, auth=self._auth_obj, **kwargs)
    def create(self, **kwargs):
        return requests.post(self.create_url, auth=self._auth_obj, data=self.build_data_dict(), **kwargs)
    def delete(self, **kwargs):
        return requests.delete(self.delete_url, auth=self._auth_obj, **kwargs)
    def to_xml(self, result):
        try:
            xml = etree.fromstring(result.text.split("?>", 1)[1])
        except:
            xml = None
        return xml
    def search(self):
        s_tuple = (self.options.model, self.options.search_field, self.options.search_value)
        if s_tuple not in self.__search_cache:
            res_nodes = self.list(xml=True).xpath(".//list-item[child::%s[text() = '%s']]" % (
                self.options.search_field,
                self.options.search_value), smart_strings=False)
            if len(res_nodes):
                self.__search_cache[s_tuple] = int(res_nodes[0].findtext("idx"))
            else:
                raise ValueError, "nothing found according to search_specs %s=%s" % (
                    self.options.search_field,
                    self.options.search_value)
        return self.__search_cache[s_tuple]
    def __call__(self):
        if self.options.search_field and self.options.search_value:
            self.options.pk = self.search()
        if self.options.mode == "create":
            response = self.create()
        elif self.options.mode == "delete":
            response = self.delete()
        elif self.options.mode == "detail":
            response = self.detail()
        elif self.options.mode == "list":
            response = self.list()
        else:
            raise ValueError, "Unknown mode '%s'" % (self.options.mode)
        ret_code = response.status_code
        if self.options.format == "xml":
            try:
                xml = etree.fromstring(response.text.split("?>", 1)[1])
            except:
                xml = None
        else:
            xml = None
        if self.options.mode in ["create", "detail"] and self.options.only_pk:
            if xml is not None:
                print xml.findtext(".//idx")
            else:
                print "-1"
        else:
            if xml is None:
                print response.text
            else:
                print etree.tostring(xml, pretty_print=True)
        return ret_code

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--host", help="target host [%(default)s]", default="localhost", type=str)
    my_parser.add_argument("--port", help="target port [%(default)d]", default=80, type=int)
    my_parser.add_argument("--path", help="path to create url [%(default)s]", default="cluster/rest", type=str)
    my_parser.add_argument("--model", help="model name [%(default)s]", default="group", type=str)
    my_parser.add_argument("--user", help="username for authentication [%(default)s]", default="notset", type=str)
    my_parser.add_argument("--password", help="password for authentication [%(default)s]", default="notset", type=str)
    my_parser.add_argument("--mode", help="operation mode [%(default)s]", default="list", choices=["list", "detail", "create", "delete"], type=str)
    my_parser.add_argument("--format", help="output format [%(default)s]", default="xml", choices=["xml", "json"], type=str)
    my_parser.add_argument("--pk", help="primary key for detail mode [%(default)d]", default=0, type=int)
    my_parser.add_argument("-v", "--verbose", default=False, action="store_true", help="be verbose [%(default)s]")
    my_parser.add_argument("--only-pk", default=False, action="store_true", help="only show pk for create statements [%(default)s]")
    my_parser.add_argument("--search-field", default="", type=str, help="specify field for search request [%(default)s]")
    my_parser.add_argument("--search-value", default="", type=str, help="specify field for search request [%(default)s]")
    my_parser.add_argument("--data", nargs="*", type=str, help="data for create / update requests (space separated key:value pairs)")
    options = my_parser.parse_args()
    client = rest_client(options)
    ret_code = client()
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
    
