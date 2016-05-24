# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" creates fixtures for static assets """


from initat.cluster.backbone import factories
from initat.cluster.backbone.models import StaticAssetType, StaticAssetTemplateFieldType


def add_fixtures(**kwargs):
    _dummy_hardware = factories.StaticAssetTemplateFactory(
        type=StaticAssetType.HARDWARE,
        name="sysHardware",
        system_template=True,
    )
    factories.StaticAssetTemplateField(
        static_asset_template=_dummy_hardware,
        name="Type",
        field_description="Type of Hardware",
        field_type=StaticAssetTemplateFieldType.STRING,
        optional=False,
    )
    factories.StaticAssetTemplateField(
        static_asset_template=_dummy_hardware,
        name="Name",
        field_description="Name of Hardware",
        field_type=StaticAssetTemplateFieldType.STRING,
        optional=False,
    )
    factories.StaticAssetTemplateField(
        static_asset_template=_dummy_hardware,
        name="Vendor",
        field_description="Vendor Name",
        field_type=StaticAssetTemplateFieldType.STRING,
        optional=True,
    )
    _dummy_contract = factories.StaticAssetTemplateFactory(
        type=StaticAssetType.CONTRACT,
        name="sysContract",
        system_template=True,
    )
    factories.StaticAssetTemplateFieldFactory(
        static_asset_template=_dummy_contract,
        name="Name",
        field_description="Contract Name",
        field_type=StaticAssetTemplateFieldType.STRING,
        optional=False,
    )
    factories.StaticAssetTemplateField(
        static_asset_template=_dummy_contract,
        name="Vendor",
        field_description="Vendor Name",
        field_type=StaticAssetTemplateFieldType.STRING,
        optional=True,
    )
    factories.StaticAssetTemplateField(
        static_asset_template=_dummy_contract,
        name="StartDate",
        field_description="Start of Contract",
        field_type=StaticAssetTemplateFieldType.DATE,
        optional=False,
    )
    factories.StaticAssetTemplateField(
        static_asset_template=_dummy_contract,
        name="EndDate",
        field_description="End of Contract",
        field_type=StaticAssetTemplateFieldType.DATE,
        optional=False,
    )
