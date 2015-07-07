# -*- coding: utf-8 -*-
import copy

import requests
from lxml import etree

from .. import limits
from ..hm_classes import hm_module, hm_command
from ..long_running_checks import (
    LongRunningCheck, LONG_RUNNING_CHECK_RESULT_KEY
)

class _general(hm_module):
    pass


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
    def __init__(self, url, cacert, username, password):
        self.url = url
        self.cacert = cacert
        self.username = username
        self.password = password

    def get(self, url):
        full_url = self.url + url
        return requests.get(
            full_url, verify=self.cacert, auth=(self.username, self.password)
        )


class APIObject(object):
    """ A basic ovirt API object """
    def __init__(self, xml, client):
        self.xml = copy.deepcopy(xml)
        self.client = client

    @staticmethod
    def zero_text_strip(x):
        return x[0].text.strip()

    def elements_to_list(self, url_xpath, xpath, klass):
        response = self.client.get(
            self.xml.xpath(url_xpath)[0].strip()
        )
        elements_xml = etree.fromstring(response.content)
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
            "/disk/link[@rel='statistics']/@href", "/statistics/statistic",
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
            "/nic/link[@rel='statistics']/@href", "/statistics/statistic",
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
    def __init__(self, base_url, ca_cert, username, password):
        self.client = APIClient(
            base_url, ca_cert, username, password
        )

    @property
    def vms(self):
        response = self.client.get("/api/vms")
        xml = etree.fromstring(response.content)
        vms = FilterList()
        for vm in xml.xpath("/vms/vm"):
            vms.append(VM(vm, self.client))
        return vms


class OvirtCheck(LongRunningCheck):
    def __init__(self, api):
        self.api = api

    def perform_check(self, queue):
        up = [i.name for i in self.api.vms.filter(is_up=True)]
        down = [i.name for i in self.api.vms.filter(is_up=False)]
        queue.put({"up": up, "down": down})


class ovirt_command(hm_command):
    def __init__(self, name):
        super(ovirt_command, self).__init__(
            name, positional_arguments=True
        )
        self.parser.add_argument(
            "base_url", help="The base URL of the ovirt installation"
        )
        self.parser.add_argument(
            "username", help="The username"
        )
        self.parser.add_argument(
            "password", help="The password"
        )
        self.parser.add_argument(
            "ca_cert", help="The CA of the ovirt installation"
        )

    def __call__(self, srv_command_obj, arguments):
        api = OvirtAPI(
            arguments.base_url, arguments.ca_cert, arguments.username,
            arguments.password
        )
        return OvirtCheck(api)

    def interpret(self, srv_com, *args, **kwargs):
        result = srv_com[LONG_RUNNING_CHECK_RESULT_KEY]
        up, down = result["up"], result["down"]

        result_status = limits.nag_STATE_OK
        if down:
            result_status = limits.nag_STATE_CRITICAL
        return result_status, "up: {}, down: {}".format(len(up), len(down))
