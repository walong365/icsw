
# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" XML constants for database definitions for license management """



import logging

from lxml import etree

from initat.tools.server_command import XML_NS

logger = logging.getLogger("cluster.icsw_license_xml")

__all__ = [
    b"ICSW_XML_NS",
    b"ICSW_XLM_NS_NAME",
    b"ICSW_XML_NS_MAP",
    b"LIC_FILE_RELAX_NG_DEFINITION",
]

ICSW_XML_NS = XML_NS
ICSW_XML_NS_NAME = "icsw"

ICSW_XML_NS_MAP = {
    ICSW_XML_NS_NAME: ICSW_XML_NS
}


LIC_FILE_RELAX_NG_DEFINITION = etree.fromstring("""
<element name="signed-license-file" ns="{}" xmlns="http://relaxng.org/ns/structure/1.0">

    <element name="license-file">

        <element name="license-file-meta">
            <element name="created-by">
                <text/>
            </element>
            <element name="creation-datetime">
                <text/> <!-- date validation supported? -->
            </element>
            <element name="file-format-version">
                <text/>
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
                        <element name="package-date">
                            <text/>
                        </element>
                        <element name="package-version">
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
                            <optional>
                                <element name="hardware-finger-print">
                                    <text/>
                                </element>
                            </optional>
                            <oneOrMore>
                                <element name="license">
                                    <element name="id">
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
                                    <element name="parameters">

                                        <zeroOrMore>
                                            <element name="parameter">
                                                <attribute name="id"/>
                                                <attribute name="name"/>
                                                <text/>
                                            </element>
                                        </zeroOrMore>

                                    </element>
                                </element>
                            </oneOrMore>
                            <zeroOrMore>
                                <element name="package-parameter">
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
                                    <element name="value">
                                       <text/>
                                    </element>
                                </element>
                            </zeroOrMore>
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
""".format(XML_NS))
