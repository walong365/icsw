# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of cluster-backbone-sql
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
# -*- coding: utf-8 -*-
#
""" database definitions for licenses """

from lxml import etree

from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.functional import cached_property
import enum

__all__ = [
    "Features",
    "LicenseState",
    "License",
]

# features are only relevant to the code, so we store them here
# licenses are only relevant to the user, so we store them in the db
# the mapping is done in a signed xml file which we ship

# in code, licenses are usually passed by their identifying string and features as their enum

Features = enum.Enum("Features",
                     ['webfrontend', 'md-config-server', 'peering', 'monitoring-overview',
                      'graphing', 'discovery-server'])


class LicenseState(enum.IntEnum):
    # NOTE: this is ordered in the sense that if multiple licenses are
    # present, the higher one is actually used
    valid = 100
    grace = 80
    new_install = 60
    expired = 40
    valid_in_future = 20


class _LicenseManager(models.Manager):

    LICENSE_FEATURE_MAP_FILE = "/tmp/map"

    def get_license_state(self, license):
        """Returns the license state for this license"""
        return max([r.get_license_state(license) for r in self._license_readers])

    def has_valid_license(self, license):
        """Returns whether we currently have this license"""
        return self.get_license_state(license) in (LicenseState.full, LicenseState.grace, LicenseState.new_install)

    def has_license_for(self, feature):
        """Returns whether we can currently access the feature"""
        licenses = self.get_licenses_providing_feature(feature)
        return any(self.has_valid_license(lic) for lic in licenses)

    def get_licenses_providing_feature(self, feature):
        """Returns list of license id strings which provide the feature"""
        signed_map_file_xml = etree.fromstring(open(self.LICENSE_FEATURE_MAP_FILE, "r").read())
        map_xml = signed_map_file_xml.find("license-feature-map")
        signature_xml = signed_map_file_xml.find("signature")

        from initat.cluster.backbone.license_file_reader import LicenseFileReader

        if not LicenseFileReader.verify_signature(map_xml, signature_xml):
            raise Exception("Invalid license feature map signature")

        features_xml = map_xml.xpath("//icsw:license[icsw:feature/text() = '?'".format(feature.name),
                                     namespaces=ICSW_XML_NS_MAP)
        return [feat.get('id') for feat in features_xml]

    @cached_property
    def _license_readers(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return [LicenseFileReader(file_content) for file_content in self.values_list('license_file', flat=True)]

    def _update_license_readers(self):
        try:
            del self._license_readers
        except AttributeError:
            pass


class License(models.Model):

    objects = _LicenseManager()

    idx = models.AutoField(primary_key=True)
    license_file = models.TextField()  # contains the exact file content of the respective license files


@receiver(signals.post_save, sender=License)
@receiver(signals.post_delete, sender=License)
def license_save(sender, **kwargs):
    License.objects._update_license_readers()


ICSW_XML_NS = "http://www.initat.org/lxml/ns"
ICSW_XML_NS_NAME = "icsw"

ICSW_XML_NS_MAP = {ICSW_XML_NS_NAME: ICSW_XML_NS}


LIC_FILE_RELAX_NG_DEFINITION = """
<element name="signed-license-file" ns=""" + "\"" + ICSW_XML_NS + "\"" + """ xmlns="http://relaxng.org/ns/structure/1.0">

    <element name="license-file">

        <element name="license-file-meta">
            <element name="created-by">
                <text/>
            </element>
            <element name="creation-datetime">
                <text/> <!-- date validation supported? -->
            </element>
        </element>

        <element name="customer">
            <element name="name">
                <text/>
            </element>
            <element name="repository_login">
                <text/>
            </element>
            <element name="repository_password">
                <text/>
            </element>
        </element>

        <element name="package-list">

            <oneOrMore>
                <element name="package">

                    <element name="package-meta">
                        <element name="package-name">
                            <text/>
                        </element>
                        <element name="package-uuid">
                            <text/>
                        </element>
                        <element name="package-type-id">
                            <text/>
                        </element>
                        <element name="package-type-name">
                            <text/>
                        </element>
                    </element>

                    <oneOrMore>
                        <element name="cluster-id">
                            <attribute name="id"/>

                            <oneOrMore>
                                 <element name="license">
                                     <element name="id">
                                         <text/>
                                     </element>
                                     <element name="name">
                                         <text/>
                                     </element>
                                     <element name="uuid">
                                         <text/>
                                     </element>
                                     <element name="valid-from">
                                         <text/>
                                     </element>
                                     <element name="valid-to">
                                         <text/>
                                     </element>
                                 </element>
                             </oneOrMore>

                         </element>
                     </oneOrMore>

                 </element>
            </oneOrMore>
         </element>
    </element>

    <element name="signature">
        <text/>
    </element>

</element>
"""

