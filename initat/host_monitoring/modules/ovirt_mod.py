# Copyright (C) 2015 Andreas Lang-Nevyjel init.at
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
""" monitor ovirt instances """

from lxml import etree
from lxml.builder import E
import copy

import requests
from requests_futures.sessions import FuturesSession
from initat.host_monitoring import limits, hm_classes
from initat.tools import process_tools, server_command, logging_tools
from initat.host_monitoring.long_running_checks import LongRunningCheck
from initat.host_monitoring.host_monitoring_struct import ExtReturn


class _general(hm_classes.hm_module):
    def init_module(self):
        requests.packages.urllib3.disable_warnings()


class FilterList(list):
    """ A list class that adds support for basic filtering. Currently only
    AND and equality are supported. """
    def filter(self, **kwargs):
        for i in self:
            for name, given_value in kwargs.items():
                actual_value = getattr(i, name)
                if actual_value == given_value:
                    yield i


class XpathPropertyMeta(type):
    """ Create properties based on xpath expressions provided in the
    xpath_properties attribute of the class. """
    def __new__(cls, cls_name, bases, attrs):
        for name, (xpath, post_func) in attrs["xpath_properties"].items():
            # This forces a new environment for the closure
            def outer(xpath, post_func):
                return lambda x: post_func(x.xml.xpath(xpath))
            attrs[name] = property(outer(xpath, post_func))
        return super(XpathPropertyMeta, cls).__new__(cls, cls_name, bases, attrs)


class APIClient(object):
    def __init__(self, url, ignore_ssl_warnings, cacert, username, password):
        self.url = url
        self.ignore_ssl_warnings = ignore_ssl_warnings
        self.cacert = cacert
        self.username = username
        self.password = password
        self._fus = None

    def get_delayed(self, url, cb_func=None):
        full_url = self.url + url
        if not self._fus:
            self._fus = FuturesSession(max_workers=10)
        return self._fus.get(full_url, background_callback=cb_func, **self._get_kwargs())

    def _get_kwargs(self):
        _kwargs = {
            "auth": (self.username, self.password),
        }
        if self.ignore_ssl_warnings:
            _kwargs["verify"] = False
        else:
            _kwargs["verify"] = self.cacert
        return _kwargs

    def get(self, url):
        full_url = self.url + url
        _result = requests.get(
            full_url,
            **self._get_kwargs()
        )

        if _result.status_code != 200:
            raise requests.HTTPError(
                "status code is not OK: {} ({})".format(
                    str(_result),
                    _result.reason,
                )
            )
        return _result


class APIObject(object):
    """ A basic ovirt API object """
    def __init__(self, xml, client):
        self.xml = copy.deepcopy(xml)
        self.client = client

    @staticmethod
    def zero_text_strip(x):
        return x[0].text.strip()

    def get_elements(self, url_xpath):
        return self.client.get_delayed(
            self.xml.xpath(url_xpath)[0].strip(),
            cb_func=self._cb_func
        )

    def _cb_func(self, sess, resp):
        resp.xml = etree.fromstring(resp.content)

    def elements_to_list(self, url_xpath, xpath, klass):
        # todo: handle this in the background
        elements_xml = self.get_elements(url_xpath).result().xml
        elements = FilterList()
        for element in elements_xml.xpath(xpath):
            elements.append(klass(element, self.client))
        return elements


class Statistic(APIObject):
    xpath_properties = {
        "name": ("/statistic/name", APIObject.zero_text_strip),
        "value": ("/statistic/values/value/datum", APIObject.zero_text_strip),
        "unit": ("/statistic/unit", APIObject.zero_text_strip),
    }
    __metaclass__ = XpathPropertyMeta


class Disk(APIObject):
    xpath_properties = {
        "name": ("/disk/name", APIObject.zero_text_strip),
    }
    __metaclass__ = XpathPropertyMeta

    @property
    def statistics(self):
        return self.elements_to_list(
            "/disk/link[@rel='statistics']/@href",
            "/statistics/statistic",
            Statistic
        )


class NIC(APIObject):
    xpath_properties = {
        "name": ("/nic/name", APIObject.zero_text_strip),
    }
    __metaclass__ = XpathPropertyMeta

    @property
    def statistics(self):
        return self.elements_to_list(
            "/nic/link[@rel='statistics']/@href",
            "/statistics/statistic",
            Statistic
        )


class VM(APIObject):
    xpath_properties = {
        "name": ("/vm/name", APIObject.zero_text_strip),
        "status": ("/vm/status/state", APIObject.zero_text_strip),
    }
    __metaclass__ = XpathPropertyMeta

    def __init__(self, xml, client):
        super(VM, self).__init__(xml, client)
        self.url = self.xml.xpath("/vm/@href")[0].strip()

    def __unicode__(self):
        return self.name

    @property
    def send_data(self):
        return process_tools.compress_struct(etree.tostring(self.xml))

    @property
    def is_up(self):
        return self.status == "up"

    @property
    def disks(self):
        return self.elements_to_list(
            "/vm/link[@rel='disks']/@href", "/disks/disk", Disk
        )

    @property
    def nics(self):
        return self.elements_to_list(
            "/vm/link[@rel='nics']/@href", "/nics/nic", NIC
        )


class OvirtAPI(object):
    """ The ovirt API entry point """
    def __init__(self, schema, address, port, ignore_ssl_warnings, ca_cert, username, password):
        self.base_url = "{}://{}:{:d}/".format(
            schema,
            address,
            port,
        )
        self.client = APIClient(
            self.base_url,
            ignore_ssl_warnings,
            ca_cert,
            username,
            password
        )
        self._xml = None

    @property
    def vms(self):
        if self._xml is None:
            self.response = self.client.get("/api/vms")
            self._xml = etree.fromstring(self.response.content)
        vms = FilterList()
        for vm in self._xml.xpath("/vms/vm"):
            # print etree.tostring(vm, pretty_print=True)
            vms.append(VM(vm, self.client))
        return vms


class OvirtCheck(LongRunningCheck):
    def __init__(self, api, srv_com):
        self.api = api
        self.srv_com = srv_com

    def perform_check(self, queue):
        try:
            _vms = self.api.vms
        except:
            self.srv_com.set_result(
                "error getting VMs: {}".format(
                    process_tools.get_except_info(),
                ),
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:

            for _idx, _vm in enumerate(_vms):
                self.srv_com["vms:vm{:d}".format(_idx)] = _vm.send_data
            # print len(unicode(self.srv_com))
            self.srv_com.set_result("found {}".format(logging_tools.get_plural("VM", len(_vms))))
        queue.put(unicode(self.srv_com))


class ovirt_overview_command(hm_classes.hm_command):
    def __init__(self, name):
        super(ovirt_overview_command, self).__init__(
            name,
            positional_arguments=True
        )
        self.parser.add_argument(
            "--schema",
            default="https",
            help="default schema [%(default)s]",
        )
        self.parser.add_argument(
            "--port",
            default=443,
            type=int,
            help="connection port [%(default)s]",
        )
        self.parser.add_argument(
            "--address",
            help="The address the ovirt installation [%(default)s]",
            default="localhost",
        )
        self.parser.add_argument(
            "--username",
            help="The username [%(default)s]",
            default="admin@internal",
        )
        self.parser.add_argument(
            "--password",
            help="The password [%(default)s]",
            default="not_set",
        )
        self.parser.add_argument(
            "--ignore-ssl-warnings",
            default=False,
            action="store_true",
            help="ignore SSL connection warnings [%(default)s]",
        )
        self.parser.add_argument(
            "--ca-cert",
            help="The CA of the ovirt installation [%(default)s]",
            default="",
        )
        self.parser.add_argument(
            "--passive-check-prefix",
            help="prefix for passive checks [%(default)s]",
            default="-",
        )
        self.parser.add_argument(
            "--reference",
            help="reference binary chunk [%(default)s], only for automated checks",
            default="-",
        )

    def __call__(self, srv_command_obj, arguments):
        api = OvirtAPI(
            arguments.schema,
            arguments.address,
            arguments.port,
            arguments.ignore_ssl_warnings,
            arguments.ca_cert,
            arguments.username,
            arguments.password
        )
        return OvirtCheck(api, srv_command_obj)

    def interpret(self, srv_com, ns, *args, **kwargs):
        if ns.reference not in ["", "-"]:
            _ref = process_tools.decompress_struct(ns.reference)
            _passive_dict = {
                "source": "ovirt_overview",
                "prefix": ns.passive_check_prefix,
                "list": [],
            }
        else:
            _ref = None
            _passive_dict = {}
        _vms = E.vms()
        for _entry in srv_com.xpath(".//ns:vms")[0]:
            _vms.append(etree.fromstring(process_tools.decompress_struct(_entry.text)))
        _num_vms = len(_vms)
        _states = _vms.xpath(".//vm/status/state/text()", smart_strings=False)
        _state_dict = {_state: _states.count(_state) for _state in set(_states)}
        if _ref:
            for run_name in _ref["run_names"]:
                _vm = _vms.xpath(".//vm[name[text()='{}']]".format(run_name))
                _prefix = "ovirt Domain {}".format(run_name)
                if len(_vm):
                    _vm = _vm[0]
                    _memory = int(_vm.findtext("memory"))
                    _sockets = int(_vm.find("cpu/topology").get("sockets"))
                    _cores = int(_vm.find("cpu/topology").get("cores"))
                    _state = _vm.findtext("status/state")
                    _ret_f = [
                        "state is {}".format(_state),
                        "memory {}".format(logging_tools.get_size_str(_memory, long_format=True)),
                        "CPU info: {}, {}".format(
                            logging_tools.get_plural("socket", _sockets),
                            logging_tools.get_plural("core", _cores),
                        )
                    ]
                    if _state in ["up"]:
                        _nag_state = limits.nag_STATE_OK
                    else:
                        _nag_state = limits.nag_STATE_CRITICAL
                    _passive_dict["list"].append(
                        (
                            _prefix,
                            _nag_state,
                            ", ".join(_ret_f),
                        )
                    )
                else:
                    _passive_dict["list"].append(
                        (
                            _prefix,
                            limits.nag_STATE_CRITICAL,
                            "domain not found",
                        )
                    )
        if _ref:
            if _state_dict.get("up", 0) == _ref["up"] and _state_dict.get("down", 0) == _ref["down"]:
                ret_state = limits.nag_STATE_OK
            else:
                ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        if _ref is None:
            ascii_chunk = ""
        else:
            ascii_chunk = process_tools.compress_struct(_passive_dict)
        return ExtReturn(
            ret_state,
            "{}, {}".format(
                logging_tools.get_plural("VM", _num_vms),
                ", ".join(
                    ["{:d} {}".format(_state_dict[_key], _key) for _key in sorted(_state_dict)]
                ),
            ),
            ascii_chunk=ascii_chunk,
        )
