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
from dateutil import relativedelta

from django.db.models import signals, Q
from django.db import models, transaction, IntegrityError
from django.dispatch import receiver
import enum
import operator
from initat.cluster.backbone.available_licenses import get_available_licenses, LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.functions import memoize_with_expiry
from initat.cluster.backbone.models.rms import ext_license

__all__ = [
    "LicenseState",
    "License",
    "LicenseEnum",
    "LicenseParameterTypeEnum",
    "LicenseUsage",
    "LicenseUsageDeviceService",
    "LicenseUsageUser",
    "LicenseUsageExtLicense",
    "LicenseLockListDeviceService",
    "LicenseLockListUser",
    "LicenseLockListExtLicense",
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
    not_needed = -1       # license not needed

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
            # decision by AL, BM, SR (20150519): if the product is not decided, it can become anything, so it's a CORVUS
            return InitProduct.CORVUS

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

    _license_readers_cache = {}

    @property
    @memoize_with_expiry(10, _cache=_license_readers_cache)
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


@receiver(signals.post_save, sender=License)
@receiver(signals.post_delete, sender=License)
def license_save(sender, **kwargs):
    _LicenseManager._license_readers_cache.clear()


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
        unique_together = (("license", "device", "service"),)


class _LicenseUsageUser(models.Model):
    user = models.ForeignKey("backbone.user", db_index=True)

    class Meta:
        abstract = True
        unique_together = (("license", "user"),)


class _LicenseUsageExtLicense(models.Model):
    ext_license = models.ForeignKey(ext_license, db_index=True)

    class Meta:
        abstract = True
        unique_together = (("license", "ext_license"),)


class LicenseUsageDeviceService(_LicenseUsageBase, _LicenseUsageDeviceService):
    pass


class LicenseUsageUser(_LicenseUsageBase, _LicenseUsageUser):
    pass


class LicenseUsageExtLicense(_LicenseUsageBase, _LicenseUsageExtLicense):
    pass


class LicenseUsage(object):
    # utility

    @staticmethod
    def device_to_pk(dev):
        from initat.cluster.backbone.models import device
        # assume obj is pk if it isn't the obj
        return dev.pk if isinstance(dev, device) else int(dev)

    @staticmethod
    def service_to_pk(serv):
        from initat.cluster.backbone.models.monitoring import mon_check_command
        return serv.pk if isinstance(serv, mon_check_command) else int(serv)

    @staticmethod
    def user_to_pk(u):
        from initat.cluster.backbone.models.user import user
        return u.pk if isinstance(u, user) else int(u)

    @staticmethod
    def _ext_license_to_pk(lic):
        from initat.cluster.backbone.models import ext_license
        return lic.pk if isinstance(lic, ext_license) else int(lic)

    # NOTE: keep in sync with js
    GRACE_PERIOD = relativedelta.relativedelta(weeks=2)

    @staticmethod
    def log_usage(license, param_type, value):
        """
        Can currently handle missing device ids, all other data must be valid
        Sometimes we expect iterables and sometimes single objects
        :type license: LicenseEnum
        :type param_type: LicenseParameterTypeEnum
        """
        from initat.cluster.backbone.models import device, mon_check_command

        # this produces queries for all objects
        # if that's too slow, we need a manual bulk get_or_create (check with one query, then create missing entries)
        common_params = {"license": license.name}
        with transaction.atomic():
            if param_type == LicenseParameterTypeEnum.device:
                if not isinstance(value, collections.Iterable):
                    value = (value, )

                # TODO: generalize this bulk create_if_nonexistent to all tables
                dev_pks = frozenset(LicenseUsage.device_to_pk(dev) for dev in value)
                present_keys = frozenset(
                    LicenseUsageDeviceService.objects.filter(
                        device_id__in=dev_pks, service=None, **common_params
                    ).values_list("device_id", flat=True)
                )
                dev_pks_missing = dev_pks.difference(present_keys)
                # check if devices are still present
                dev_pks_missing_dev_present = device.objects.filter(pk__in=dev_pks_missing).values_list("pk", flat=True)
                entries_to_add = [
                    LicenseUsageDeviceService(device_id=dev_pk, service=None, **common_params)
                    for dev_pk in dev_pks_missing_dev_present
                ]
                LicenseUsageDeviceService.objects.bulk_create(entries_to_add)

            elif param_type == LicenseParameterTypeEnum.service:
                if value and any(value.itervalues()):  # not empty
                    dev_serv_filter = reduce(
                        operator.ior,
                        (Q(device_id=LicenseUsage.device_to_pk(dev), service_id=LicenseUsage.service_to_pk(serv))
                         for dev, serv_list in value.iteritems()
                         for serv in serv_list
                         )
                    ) & Q(**common_params)

                    present_entries =\
                        frozenset(LicenseUsageDeviceService.objects.filter(dev_serv_filter).values_list("device_id",
                                                                                                        "service_id"))
                    existing_dev_pks = frozenset(device.objects.all().values_list("pk", flat=True))
                    existing_serv_pks = frozenset(mon_check_command.objects.all().values_list("pk", flat=True))
                    entries_to_add = []
                    for dev, serv_list in value.iteritems():
                        dev_id = LicenseUsage.device_to_pk(dev)
                        if dev_id in existing_dev_pks:
                            for serv in serv_list:
                                serv_id = LicenseUsage.service_to_pk(serv)
                                if serv_id in existing_serv_pks:
                                    if (dev_id, serv_id) not in present_entries:
                                        entries_to_add.append(
                                            LicenseUsageDeviceService(device_id=dev_id, service_id=serv_id,
                                                                      **common_params)
                                        )

                    LicenseUsageDeviceService.objects.bulk_create(entries_to_add)
            elif param_type == LicenseParameterTypeEnum.ext_license:
                try:
                    LicenseUsageExtLicense.objects.get_or_create(ext_license_id=LicenseUsage._ext_license_to_pk(value),
                                                                 **common_params)
                except IntegrityError:
                    pass
            elif param_type == LicenseParameterTypeEnum.user:
                try:
                    LicenseUsageUser.objects.get_or_create(user_id=LicenseUsage.user_to_pk(value), **common_params)
                except IntegrityError:
                    pass
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


class _LicenseLockListDeviceServiceManager(models.Manager):

    def is_device_locked(self, license, dev):
        return LicenseUsage.device_to_pk(dev) in self._get_lock_list_device(license)

    def is_service_locked(self, license, service):
        return LicenseUsage.service_to_pk(service) in self._get_lock_list_service(license)

    def is_device_service_locked(self, license, device, service, check_device_locks=True):
        if check_device_locks and self.is_device_locked(license, device):
            return True

        return (LicenseUsage.device_to_pk(device), LicenseUsage.service_to_pk(service)) in \
            self._get_lock_list_device_service(license)

    @memoize_with_expiry(20)
    def _get_lock_list_device(self, license):
        return frozenset(self.filter(license=license.name, service=None).values_list("device_id", flat=True))

    @memoize_with_expiry(20)
    def _get_lock_list_service(self, license):
        return frozenset(self.filter(license=license.name, device=None).values_list("service_id", flat=True))

    @memoize_with_expiry(20)
    def _get_lock_list_device_service(self, license):
        return frozenset(self.filter(license=license.name).values_list("device_id", "service_id"))


class _LicenseLockListUserManager(models.Manager):
    def is_user_locked(self, license, user):
        return LicenseUsage.user_to_pk(user) in self._get_lock_list_user(license)

    @memoize_with_expiry(20)
    def _get_lock_list_user(self, license):
        return frozenset(self.filter(license=license.name).values_list("user_id", flat=True))


class _LicenseLockListExtLicenseManager(models.Manager):
    def is_ext_license_locked(self, license, ext_lic):
        return LicenseUsage._ext_license_to_pk(ext_lic) in self._get_lock_list_ext_license(license)

    @memoize_with_expiry(20)
    def _get_lock_list_ext_license(self, license):
        return frozenset(self.filter(license=license.name).values_list("ext_license_id", flat=True))


class LicenseLockListDeviceService(_LicenseUsageBase, _LicenseUsageDeviceService):
    objects = _LicenseLockListDeviceServiceManager()


class LicenseLockListUser(_LicenseUsageBase, _LicenseUsageUser):
    objects = _LicenseLockListUserManager()


class LicenseLockListExtLicense(_LicenseUsageBase, _LicenseUsageExtLicense):
    objects = _LicenseLockListExtLicenseManager()


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
