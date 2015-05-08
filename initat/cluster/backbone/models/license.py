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

from django.db import models, transaction, IntegrityError
from django.db.models import signals, BooleanField
from django.dispatch import receiver
from django.utils.functional import cached_property
import enum
from initat.cluster.backbone.available_licenses import get_available_licenses, LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.rms import ext_license

__all__ = [
    "LicenseState",
    "License",
    "LicenseEnum",
    "LicenseParameterTypeEnum",
]

logger = logging.getLogger("cluster.icsw_license")


class InitProduct(enum.Enum):
    CORVUS = 1
    NOCTUA = 2
    NESTOR = 3


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

    def is_valid(self):
        # states where we consider the license to be valid, i.e. the user may access the feature
        return self in (LicenseState.valid, LicenseState.grace, LicenseState.new_install)


class _LicenseManager(models.Manager):
    """
    Interface to licenses in db.
    """

    def _get_license_state(self, license, parameters=None, ignore_violations=False):
        """Returns the license state for this license
        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: int} of required parameters
        """
        if not ignore_violations and LicenseViolation.objects.is_hard_violated(license):
            return LicenseState.violated
        # TODO: new_install?
        if not self._license_readers:
            return LicenseState.none
        return max([r.get_license_state(license, parameters) for r in self._license_readers])

    ########################################
    # Accessors for actual program logic

    def has_valid_license(self, license, parameters=None, ignore_violations=False):
        """Returns whether we currently have this license in some valid state.
        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: int} of required parameters
        :rtype: bool
        """
        return self._get_license_state(license, parameters, ignore_violations=ignore_violations).is_valid()

    ########################################
    # Accessors for views for client

    def get_init_product(self):
        valid_lics = set(self.get_valid_licenses())
        product_licenses = set()
        for available_lic in get_available_licenses():
            if available_lic.enum_value in valid_lics:
                if available_lic.product is not None:
                    product_licenses.add(available_lic.product)

        # this does currently not happen:
        if InitProduct.CORVUS in product_licenses:
            return InitProduct.CORVUS

        # unlicensed version
        if not product_licenses:
            return InitProduct.NESTOR

        if InitProduct.NESTOR in product_licenses and InitProduct.NOCTUA in product_licenses:
            return InitProduct.CORVUS
        else:
            # can only contain one
            return next(iter(product_licenses))

    def get_valid_licenses(self):
        """Returns all licenses which are active (and should be displayed to the user)"""
        return [lic for lic in set().union(*[r.get_valid_licenses() for r in self._license_readers])
                if not LicenseViolation.objects.is_hard_violated(lic)]

    def get_license_packages(self):
        """Returns license packages in custom format for the client."""
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

    date = models.DateTimeField(auto_now_add=True)

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

    license = models.CharField(max_length=30, db_index=True)

    class Meta:
        abstract = True
        app_label = "backbone"


class _LicenseUsageDeviceService(models.Model):
    device = models.ForeignKey("backbone.device", db_index=True)
    service = models.ForeignKey("backbone.mon_check_command", db_index=True, null=True, blank=True)

    class Meta:
        abstract = True


class _LicenseUsageUser(models.Model):
    user = models.ForeignKey("backbone.user", db_index=True)

    class Meta:
        abstract = True


class _LicenseUsageExtLicense(models.Model):
    ext_license = models.ForeignKey(ext_license, db_index=True)

    class Meta:
        abstract = True


class LicenseUsage(object):
    # utility

    # NOTE: keep in sync with js
    GRACE_PERIOD = relativedelta.relativedelta(weeks=2)

    @staticmethod
    def log_usage(license, param_type, value):
        """
        :type license: LicenseEnum
        :type param_type: LicenseParameterTypeEnum
        """
        # assume obj is pk if it isn't the obj
        to_pk = lambda obj, klass: obj.pk if isinstance(obj, klass) else obj

        from initat.cluster.backbone.models import device, user, mon_check_command

        # this produces queries for all objects
        # if that's too slow, we need a manual bulk get_or_create (check with one query, then create missing entries)
        common_params = {"license": license.name}
        with transaction.atomic():
            if param_type == LicenseParameterTypeEnum.device:
                if not isinstance(value, collections.Iterable):
                    value = (value, )
                for dev in value:
                    LicenseUsageDeviceService.objects.get_or_create(device_id=to_pk(dev, device),
                                                                    service=None,
                                                                    **common_params)
            elif param_type == LicenseParameterTypeEnum.service:
                for dev, serv_list in value.iteritems():
                    for serv in serv_list:
                        LicenseUsageDeviceService.objects.get_or_create(device_id=to_pk(dev, device),
                                                                        service_id=to_pk(serv, mon_check_command),
                                                                        **common_params)
            elif param_type == LicenseParameterTypeEnum.ext_license:
                LicenseUsageExtLicense.objects.get_or_create(ext_license_id=to_pk(value, ext_license), **common_params)
            elif param_type == LicenseParameterTypeEnum.user:
                LicenseUsageUser.objects.get_or_create(user_id=to_pk(value, user), **common_params)
            else:
                raise RuntimeError("Invalid license parameter type id: {}".format(param_type))

    @staticmethod
    def get_license_usage(license):
        usage = {
            LicenseParameterTypeEnum.device:
                LicenseUsageDeviceService.objects.filter(license=license.name, service=None).count(),
            LicenseParameterTypeEnum.service:
                LicenseUsageDeviceService.objects.filter(license=license.name, service__isnull=False).count(),
            LicenseParameterTypeEnum.user:
                LicenseUsageUser.objects.filter(license=license.name).count(),
            LicenseParameterTypeEnum.ext_license:
                LicenseUsageExtLicense.objects.filter(license=license.name).count(),
        }
        return {k: v for k, v in usage.iteritems() if v > 0}


class _LicenseViolationManager(models.Manager):
    def is_hard_violated(self, license):
        """
        :type license: LicenseEnum
        """
        # only hard violations are actual violations, else it's a warning (grace)
        return LicenseViolation.objects.filter(license=license.name, hard=True).exists()


class LicenseViolation(_LicenseUsageBase):
    objects = _LicenseViolationManager()

    hard = models.BooleanField(default=False)

    def __unicode__(self):
        return u"LicenseViolation(license={})".format(self.license)

    __repr__ = __unicode__


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
