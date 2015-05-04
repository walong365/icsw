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
import collections
import logging

# noinspection PyUnresolvedReferences
from lxml import etree
import datetime
import django.utils.timezone
from dateutil import relativedelta
import django

from django.db import models, transaction
from django.db.models import signals, BooleanField
from django.dispatch import receiver
from django.utils.functional import cached_property
import enum
from initat.cluster.backbone.available_licenses import get_available_licenses, LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.monitoring import mon_check_command
from initat.cluster.backbone.models.rms import ext_license

__all__ = [
    "LicenseState",
    "License",
]

logger = logging.getLogger("cluster.icsw_license")


class LicenseState(enum.IntEnum):
    # NOTE: this is ordered in the sense that if multiple licenses are
    # present, the higher one is actually used
    violated = 120        # license parameters have been violated
    valid = 100           # license is valid now
    grace = 80            # license has expired but we still let the software run
    new_install = 60      # to be defined
    expired = 40          # license used to be valid but is not valid anymore
    valid_in_future = 20  # license will be valid in the future
    none = 0              # license not present


class _LicenseManager(models.Manager):

    def get_license_state(self, license, parameters=None):
        """Returns the license state for this license
        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: int} of required parameters
        """
        # TODO: new_install?
        if not self._license_readers:
            return LicenseState.none
        return max([r.get_license_state(license, parameters) for r in self._license_readers])

    def has_valid_license(self, license, parameters=None):
        """Returns whether we currently have this license in some valid state.

        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: int} of required parameters

        :return: bool
        """
        return self.get_license_state(license, parameters) in (LicenseState.valid, LicenseState.grace,
                                                               LicenseState.new_install)

    def get_valid_licenses(self):
        pass
        # LICTODO

    def get_all_licenses(self):
        return get_available_licenses()

    def get_license_packages(self):
        """Returns license packages in custom format."""
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return LicenseFileReader.get_license_packages(self._license_readers)

    # @cached_property
    @property
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

    # def _update_license_readers(self):
    #     try:
    #         del self._license_readers
    #     except AttributeError:
    #         pass


########################################
# actual license documents:

class License(models.Model):
    objects = _LicenseManager()

    idx = models.AutoField(primary_key=True)

    file_name = models.CharField(max_length=512)
    license_file = models.TextField()  # contains the exact file content of the respective license files

    class Meta:
        app_label = "backbone"
        verbose_name = "License"

# @receiver(signals.post_save, sender=License)
# @receiver(signals.post_delete, sender=License)
# def license_save(sender, **kwargs):
#     License.objects._update_license_readers()


########################################
# license usage management:

class _LicenseUsageBase(models.Model):
    idx = models.AutoField(primary_key=True)

    date = models.DateTimeField(auto_now_add=True)

    feature = models.CharField(max_length=30, db_index=True)

    class Meta:
        abstract = True
        app_label = "backbone"


class _LicenseUsageDeviceService(models.Model):
    device = models.ForeignKey("backbone.device", db_index=True)
    service = models.ForeignKey(mon_check_command, db_index=True, null=True, blank=True)

    class Meta:
        abstract = True


class _LicenseUsageUser(models.Model):
    user = models.ForeignKey("backbone.user", db_index=True)

    class Meta:
        abstract = True


class _LicenseUsageExtLicense(models.Model):
    user = models.ForeignKey(ext_license, db_index=True)

    class Meta:
        abstract = True


class LicenseUsage(object):

    # NOTE: keep in sync with js
    GRACE_PERIOD = relativedelta.relativedelta(weeks=2)

    @staticmethod
    def log_usage(license, param_type, value):
        """
        :type license: LicenseEnum
        :type param_type: LicenseParameterTypeEnum
        :type devices: Iterable[device] | device | dict[device, Iterable[mon_check_command]] | dict[device, dict[mon_check_command, object]]
        """
        # LICTODO

        """
        any entry for device may also be an int

        current input:
        list[device]
        dict[device, list[mon_check_command]]
        dict[device, dict[mon_check_command, object]]
        """

        """
        if isinstance(devices, collections.Mapping):

        if not isinstance(devices, collections.Iterable):
            devices = (devices, )

        if services and not isinstance(services, collections.Iterable):
            services = (services, )
        """

        """
        with transaction.atomic():
            for dev in devices:
                LicenseUsageDeviceService.objects.get_or_create(
                    feature=license.name,
                    device=dev,
                )

                if services:
                    for service in services:
                        LicenseUsageDeviceService.objects.get_or_create(
                            feature=license.name,
                            device=device,
                            service=service,
                        )
        """


    @staticmethod
    def get_license_usage(license):
        return {
            LicenseParameterTypeEnum.device:
                LicenseUsageDeviceService.filter(license=license.name, service=None).count(),
            LicenseParameterTypeEnum.service:
                LicenseUsageDeviceService.filter(license=license.name, service__isnull=False).count(),
            LicenseParameterTypeEnum.user:
                LicenseUsageUser.filter(license=license.name).count(),
            LicenseParameterTypeEnum.ext_license:
                LicenseUsageExtLicense.filter(license=license.name).count(),
        }

    @staticmethod
    def check_for_violations():
        for license in LicenseEnum:
            usage = LicenseUsage.get_license_usage(license)
            violated = License.objects.has_valid_license(license, usage)

            try:
                violation = LicenseViolation.objects.get(feature=license.name)
                if not violated:
                    violation.delete()
                else:
                    # still violate, check if now grace period is violated too
                    if not violation.hard and violation.date > django.utils.timezone.now() + License.GRACE_PERIOD:
                        violation.hard = True
                        violation.save()
            except LicenseViolation.DoesNotExist:
                if violated:
                    LicenseViolation(feature=license.name).save()


class LicenseViolation(_LicenseUsageBase):
    hard = models.BooleanField(default=False)


class LicenseUsageDeviceService(_LicenseUsageBase, _LicenseUsageDeviceService):
    pass


class LicenseUsageUser(_LicenseUsageBase, _LicenseUsageUser):
    pass


class LicenseUsageExtLicense(_LicenseUsageBase, _LicenseUsageExtLicense):
    pass


class LicenseLockListDeviceService(_LicenseUsageBase, _LicenseUsageDeviceService):
    pass


class LicenseLockListUser(_LicenseUsageBase, _LicenseUsageUser):
    pass


class LicenseLockListExtLicense(_LicenseUsageBase, _LicenseUsageExtLicense):
    pass


########################################
# XML

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
