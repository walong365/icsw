#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012,2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of cluster-backbone-tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" kernel sync tools """

import base64
import logging
import sys
import os
import tempfile
from M2Crypto import RSA, EVP
from lxml import etree
from lxml.builder import E

logger = logging.getLogger(__name__)

LICENSE_FILE="/etc/sysconfig/cluster/cluster_license"

LICENSE_CAPS = [
    ("monitor", "Monitoring services"),
    ("monext" , "Extended monitoring services"),
    ("boot"   , "boot/config facility for nodes"),
    ("package", "Package installation"),
    ("rms"    , "Resource Management system"),
    ("ganglia", "Ganglia monitoring system"),
    ("rest"   , "REST server"),
    ("rrd"    , "RRD functionality"),
    ("docu"   , "show documentation"),
]

def check_license(lic_name):
    lic_xml = etree.fromstring(
        open(LICENSE_FILE, "r").read())
    cur_lic = lic_xml.xpath(".//license[@short='%s']" % (lic_name))
    if len(cur_lic):
        return True if cur_lic[0].get("enabled", "no").lower() in ["yes", "true", "1"] else False
    else:
        return False
    
def get_all_licenses():
    lic_xml = etree.fromstring(
        open(LICENSE_FILE, "r").read())
    return lic_xml.xpath(".//license/@short")

def create_default_license():
    if not os.path.isfile(LICENSE_FILE):
        lic_xml = E.cluster(
            E.license(
                E.devicecount(
                    E.data("10"),
                    E.signature(),
                ),
                short="parameter"
            ),
            E.licenses(
                *[E.license(name, short=name, info=info, enabled="no") for name, info in LICENSE_CAPS]
            )
        )
        file(LICENSE_FILE, "w").write(etree.tostring(lic_xml, pretty_print=True))
        os.chmod(LICENSE_FILE, 0o644)
        print("created license file '%s'" % (LICENSE_FILE))
    else:
        lic_xml = etree.fromstring(
            open(LICENSE_FILE, "r").read())
        changed = False
        for lic_name, info in LICENSE_CAPS:
            if not len(lic_xml.xpath(".//licenses/license[@short='%s']" % (lic_name))):
                changed = True
                lic_xml.find("licenses").append(
                    E.license(lic_name, short=lic_name, info=info, enabled="no")
                )
        if changed:
            print("license file '%s' already present and updated" % (LICENSE_FILE))
            file(LICENSE_FILE, "w").write(etree.tostring(lic_xml, pretty_print=True))
            os.chmod(LICENSE_FILE, 0o644)
        else:
            print("license file '%s' already present" % (LICENSE_FILE))


class License(object):
    public_key = \
"""
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4p6JXKFMDbUpe45HhGZs
/fBsQQki80YqQzgeRB42f0waKKqToia929RcMil1g4JRmpOu6IAWaKTthuueIKje
B1bnXYZhHKwod4Bmp6cooU3A1i+62F6AHqLJQvmaxK6UPMWyAvX6BPqJKdRcyH+X
tFXGXEDnokfxzI1Cxgm1hYtpRwvhinERFOl1BVNgKRJD3QoYcztHDpRf58eO7i/E
glk1qrAYb+COX14ighkhQrUZ8Q3WcOMuUvEjupUCOiBTVIU5XTMnaggmdBZETg7q
2V6hjXVdEVg7PBYpwcGFS2TQY8g82Di6nERR4LNEAsvUX/8tRzNokOBsjSfcSWSh
GwIDAQAB
-----END PUBLIC KEY-----
"""

    def __init__(self, filename=LICENSE_FILE):
        self.filename = filename
        with open(self.filename, "r") as f:
            self.xml = etree.fromstring(f.read())
        # Write the public key to a temporary file for loading. It seems that
        # the API does not support loading public keys from strings
        tmp = tempfile.mktemp(suffix="monit_key")
        with open(tmp, "w") as f:
            f.write(License.public_key)

        rsa_key = RSA.load_pub_key(tmp)
        self.key = EVP.PKey()
        self.key.assign_rsa(rsa_key)

        # Cleanup
        os.unlink(tmp)

    @property
    def _license_parameter(self):
        try:
            return self.xml.xpath("//license[@short='parameter']")[0]
        except:
            raise BadLicenseXML("no license for parameter found")
    def _check_signature(self, element):
        """ Expects the element to have a data and a signature
        child element.

        The signature must be base64 encoded.
        """
        data = element.xpath("./data/text()")[0]
        signature = base64.decodestring(element.xpath("./signature/text()")[0])
        logger.info("Checking signature for data: %s", data)

        self.key.verify_init()
        self.key.verify_update(data)
        # Only 1 means success
        if self.key.verify_final(signature) != 1:
            logger.error("Signature for data '%s' not correct", data)
            raise SignatureNotCorrect("%s has invalid signature" % element.tag)
        else:
            logger.info("Signature for data '%s' is correct")
            return data

    def get_device_count(self):
        """ Validate signature and return the device count.

        Might raise SignatureNotCorrect() or BadLicenseXML().
        """
        dev_count = self._license_parameter.xpath("./devicecount")
        if len(dev_count):
            dev_count = dev_count[0]
        else:
            raise BadLicenseXML("No devicecount found!")
        return int(self._check_signature(dev_count))


class BadLicenseXML(Exception):
    """ Raised if the license XML is misformed. """
    pass


class SignatureNotCorrect(Exception):
    """ Raised if the GPG signature is not correct. """
    pass


if __name__ == "__main__":
    create_default_license()
