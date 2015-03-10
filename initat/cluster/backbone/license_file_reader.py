# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of licadmin
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

import base64
import bz2
from lxml import etree
import M2Crypto
import datetime
from dateutil import relativedelta
import logging_tools
import process_tools
import logging

from initat.cluster.backbone.models.license import LicenseState, LIC_FILE_RELAX_NG_DEFINITION, ICSW_XML_NS_MAP


logger = logging.getLogger("cluster.licadmin")

CERT_FILE = "/home/mallinger/cert.pem"
# CERT_FILE = "/home/mallinger/ca3_cert1"


class LicenseFileReader(object):

    class InvalidLicenseFile(RuntimeError):
        def __init__(self, msg=None):
            super(LicenseFileReader.InvalidLicenseFile, self).__init__(
                msg if msg is not None else "Invalid license file format"
            )

    def __init__(self, file_content):
        # contains the license-file tag, i.e. information relevant for program without signature
        self.content_xml = self._read(file_content)

    def _read(self, file_content):
        try:
            signed_content_str = bz2.decompress(base64.b64decode(file_content))
        except:
            logger.error("Error reading uploaded license file: {}".format(process_tools.get_except_info()))
            raise LicenseFileReader.InvalidLicenseFile()

        signed_content_xml = etree.fromstring(signed_content_str)

        ng = etree.RelaxNG(etree.fromstring(LIC_FILE_RELAX_NG_DEFINITION))
        if not ng.validate(signed_content_xml):
            raise LicenseFileReader.InvalidLicenseFile("Invalid license file structure")

        content_xml = signed_content_xml.find('icsw:license-file', ICSW_XML_NS_MAP)
        signature_xml = signed_content_xml.find('icsw:signature', ICSW_XML_NS_MAP)

        signature_ok = self.verify_signature(content_xml, signature_xml)

        if not signature_ok:
            raise LicenseFileReader.InvalidLicenseFile("Invalid signature")

        return content_xml

        # print etree.tostring(content_xml, pretty_print=True)

        # TODO: move this to cluster-backbone-sql including schema

    def get_license_state(self, license):
        """Returns a LicenseState for the local cluster_id and the given license combination
        for the current point in time, or None if no license exists"""

        parse_date = lambda date_str: datetime.date(*(int(i) for i in date_str.split(u"-")))

        def get_state_from_license_xml(lic_xml):

            grace_period = relativedelta.relativedelta(months=1)

            valid_from = parse_date(lic_xml.find("icsw:valid-from", ICSW_XML_NS_MAP).text)
            valid_to = parse_date(lic_xml.find("icsw:valid-to", ICSW_XML_NS_MAP).text)
            valid_to_plus_grace = valid_to + grace_period
            today = datetime.date.today()

            # semantics: valid_from is from 00:00 of that day, valid to is till 23:59 of that day

            if today < valid_from:
                return LicenseState.valid_in_future
            elif today > valid_to_plus_grace:
                return LicenseState.expired
            elif today > valid_to:
                return LicenseState.grace
            else:
                return LicenseState.valid

        state = None

        from initat.cluster.backbone.models import device_variable

        q = "//icsw:package-list/icsw:package/icsw:cluster-id[@id='{}']".format(
            device_variable.objects.get_cluster_id()
        )
        q += "/icsw:license[icsw:id/text()='{}']".format(license)

        for lic_xml in self.content_xml.xpath(q, namespaces=ICSW_XML_NS_MAP):
            s = get_state_from_license_xml(lic_xml)
            if state is None or s > state:
                state = s

        return state

    @staticmethod
    def verify_signature(lic_file_xml, signature_xml):
        """

        :return: True if signature is fine
        :rtype : bool
        """
        signed_string = LicenseFileReader._extract_string_for_signature(lic_file_xml)
        signature = base64.b64decode(signature_xml.text)

        cert = M2Crypto.X509.load_cert(CERT_FILE)

        evp_verify_pkey = M2Crypto.EVP.PKey()
        evp_verify_pkey.assign_rsa(cert.get_pubkey().get_rsa())
        evp_verify_pkey.verify_init()
        evp_verify_pkey.verify_update(signed_string)
        result = evp_verify_pkey.verify_final(signature)
        # Result of verification: 1 for success, 0 for failure, -1 on other error.

        return (result == 1)

    @staticmethod
    def _extract_string_for_signature(content):
        def dict_to_str(d):
            return u";".join(u"{}:{}".format(k, v) for k, v in d.iteritems())
        return u"_".join(
            (u"{}/{}/{}".format(el.tag,
                                dict_to_str(el.attrib),
                                el.text.strip() if el.text is not None else u"")
             for el in content.iter())
        )
