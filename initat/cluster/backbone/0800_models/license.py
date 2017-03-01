# Copyright (C) 2015,2017 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of icsw-server
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
""" database definitions for licenses """
import logging

from lxml import etree

from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.functional import cached_property
import enum

__all__ = [
    "Feature",
    "LicenseState",
    "License",
]

# features are only relevant to the code, so we store them here
# licenses are only relevant to the user, so we store them in the db
# the mapping is done in a signed xml file which we ship

# in code, licenses are usually passed by their identifying string and features as their enum

Feature = enum.Enum("Features",
                    ['webfrontend', 'md-config-server', 'peering', 'monitoring-overview',
                     'graphing', 'discovery-server'])

logger = logging.getLogger("cluster.icsw_license")


class LicenseState(enum.IntEnum):
    # NOTE: this is ordered in the sense that if multiple licenses are
    # present, the higher one is actually used
    valid = 100           # license is valid now
    grace = 80            # license has expired but we still let the software run
    new_install = 60      # to be defined
    expired = 40          # license used to be valid but is not valid anymore
    valid_in_future = 20  # license will be valid in the future


class _LicenseManager(models.Manager):

    def get_license_state(self, license):
        """Returns the license state for this license"""
        # TODO: new_install?
        if not self._license_readers:
            return LicenseState.expired
        return max([r.get_license_state(license) for r in self._license_readers])

    def has_valid_license(self, license):
        """Returns whether we currently have this license"""
        return self.get_license_state(license) in (LicenseState.valid, LicenseState.grace, LicenseState.new_install)

    def has_license_for(self, feature):
        """Returns whether we can currently access the feature"""
        licenses = self.get_licenses_providing_feature(feature)
        return any(self.has_valid_license(lic) for lic in licenses)

    def get_licenses_providing_feature(self, feature):
        """Returns list of license id strings which provide the feature"""
        return self._license_feature_map_reader.get_licenses_providing_feature(feature)

    def get_activated_features(self):
        return [feature for feature in self._license_feature_map_reader.get_all_features()
                if self.has_license_for(feature)]

    def get_all_licenses(self):
        """Returns list of dicts containing 'id', 'name' and 'description' of all available licenses."""
        return self._license_feature_map_reader.get_all_licenses()

    def get_license_packages(self):
        """Returns license packages in custom format."""
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return LicenseFileReader.get_license_packages(self._license_readers)

    @cached_property
    def _license_readers(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        readers = []
        for file_content, file_name in self.values_list('license_file', 'file_name'):
            try:
                readers.append(
                    LicenseFileReader(file_content, file_name)
                )
            except LicenseFileReader.InvalidLicenseFile as e:
                logger.info("Invalid license file in database {}: {}".format(file_name, e))

        return readers

    def _update_license_readers(self):
        try:
            del self._license_readers
        except AttributeError:
            pass

    @cached_property
    def _license_feature_map_reader(self):
        from initat.cluster.backbone.license_file_reader import LicenseFeatureMapReader
        return LicenseFeatureMapReader()


class License(models.Model):
    objects = _LicenseManager()

    idx = models.AutoField(primary_key=True)

    file_name = models.CharField(max_length=512)
    license_file = models.TextField()  # contains the exact file content of the respective license files
