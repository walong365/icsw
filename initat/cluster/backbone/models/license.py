
# Copyright (C) 2015-2016 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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

""" database definitions for license / ova management """

import collections
import datetime
import logging
import operator

import django.utils.timezone
import enum
from dateutil import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction, IntegrityError
from django.db.models import signals, Q, Count
from django.dispatch import receiver

from initat.cluster.backbone.available_licenses import get_available_licenses, LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.functions import memoize_with_expiry
from initat.cluster.backbone.models.rms import ext_license
from initat.tools import logging_tools
from .license_xml import ICSW_XML_NS, ICSW_XML_NS_NAME, ICSW_XML_NS_MAP, LIC_FILE_RELAX_NG_DEFINITION

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
    "ICSW_XML_NS",
    "ICSW_XML_NS_MAP",
    "ICSW_XML_NS_NAME",
    "LIC_FILE_RELAX_NG_DEFINITION",
    "icswEggCradle",
    "icswEggEvaluationDef",
    "icswEggBasket",
    "icswEggConsumer",
    "icswEggRequest",
]

logger = logging.getLogger("cluster.icsw_license")


class InitProduct(enum.Enum):
    CORVUS = 1
    NOCTUA = 2
    NESTOR = 3

    def get_version_family(self, version):
        if version == "0.0":
            version = _PRODUCT_FAMILY_MATRIX.keys()[-1]

        return _PRODUCT_FAMILY_MATRIX.get(version, {}).get(self, "")

_PRODUCT_FAMILY_MATRIX = collections.OrderedDict(  # ordered dict so we know which is last
    [
        (
            "2.5",
            {
                InitProduct.CORVUS: u"Corvus hawaiiensis",  # Hawaiikraehe
                InitProduct.NOCTUA: u"Strigidae occidentalis",  # Fleckenkauz
                InitProduct.NESTOR: u"Nestor notabilis",  # Kea
            }
        ),
        (
            "3.0",
            {
                InitProduct.CORVUS: u"Corvus splendens",  # Glanzkraehe
                InitProduct.NOCTUA: u"Strigidae rufipes",  # Rostfusskauz
                InitProduct.NESTOR: u"Nestor meridionalis",  # Kaka (Waldpapagei)
            }
        )
    ]
)


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
    ip_mismatch = 200     # IP mismatch, should not run
    fp_mismatch = 300     # fingerprint mismatch, should not run

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

    def fingerprint_ok(self, license):
        # return false even when no licenses are present, ToDo, FIXME
        return any([r.fingerprint_ok for r in self._license_readers if r.has_license(license)])

    def license_exists(self, lic_content):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        _pure_content = LicenseFileReader.get_pure_data(lic_content)
        _present = False
        for value in self.values_list("license_file", flat=True):
            _loc_pc = LicenseFileReader.get_pure_data(value)
            if _loc_pc == _pure_content:
                _present = True
                break
        return _present

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

    def get_license_info(self):
        return sum([_reader.license_info(raw=True) for _reader in self._license_readers], [])

    def get_valid_licenses(self):
        """Returns all licenses which are active (and should be displayed to the user)"""
        return [
            lic for lic in set().union(
                *[
                    r.get_valid_licenses() for r in self._license_readers
                ]
            ) if not LicenseViolation.objects.is_hard_violated(lic)
        ]

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
                logger.error(
                    "Invalid license file in database {}: {}".format(
                        file_name,
                        e
                    )
                )

        return readers


########################################
# actual license documents:


class License(models.Model):
    objects = _LicenseManager()

    idx = models.AutoField(primary_key=True)

    date = models.DateTimeField(auto_now_add=True)

    file_name = models.CharField(max_length=512)
    license_file = models.TextField()  # contains the exact file content of the respective license files

    def __unicode__(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        _reader = LicenseFileReader(self.license_file, self.file_name)
        return _reader.license_info()

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

    # NOTE: keep in sync with js, see system/license.coffee line 222
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
                    LicenseUsageDeviceService(device_id=dev_pk, service=None, **common_params) for dev_pk in dev_pks_missing_dev_present
                ]
                LicenseUsageDeviceService.objects.bulk_create(entries_to_add)

            elif param_type == LicenseParameterTypeEnum.service:
                if value and any(value.itervalues()):  # not empty
                    dev_serv_filter = reduce(
                        operator.ior,
                        (
                            Q(
                                device_id=LicenseUsage.device_to_pk(dev),
                                service_id=LicenseUsage.service_to_pk(serv)
                            )
                            for dev, serv_list in value.iteritems()
                            for serv in serv_list
                        )
                    ) & Q(**common_params)

                    present_entries = frozenset(
                        LicenseUsageDeviceService.objects.filter(dev_serv_filter).values_list(
                            "device_id",
                            "service_id"
                        )
                    )
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
                                            LicenseUsageDeviceService(
                                                device_id=dev_id,
                                                service_id=serv_id,
                                                **common_params
                                            )
                                        )

                    LicenseUsageDeviceService.objects.bulk_create(entries_to_add)
            elif param_type == LicenseParameterTypeEnum.ext_license:
                try:
                    LicenseUsageExtLicense.objects.get_or_create(
                        ext_license_id=LicenseUsage._ext_license_to_pk(value),
                        **common_params
                    )
                except IntegrityError:
                    pass
            elif param_type == LicenseParameterTypeEnum.user:
                try:
                    LicenseUsageUser.objects.get_or_create(user_id=LicenseUsage.user_to_pk(value), **common_params)
                except IntegrityError:
                    pass
            else:
                raise RuntimeError("Invalid license parameter type id: {}".format(param_type))

    @classmethod
    def get_license_usage(cls, license):
        return {k: v for k, v in cls._get_license_usage_cache()[license].iteritems() if v > 0}

    @staticmethod
    @memoize_with_expiry(1)
    def _get_license_usage_cache():
        """
        :return: {lic_enum: {param_type_enum: <usage>}}
        """

        usage_by_lic = {}
        for lic in LicenseEnum:
            usage_by_lic[lic] = {param_type: 0 for param_type in LicenseParameterTypeEnum}

        def _add(lic_str, param_type_enum, usage):
            try:
                lic_enum = LicenseEnum[lic_str]
            except KeyError:
                # old license type
                pass
            else:
                usage_by_lic[lic_enum][param_type_enum] = usage

        for dev_usage in LicenseUsageDeviceService.objects.filter(
            service__isnull=True
        ).values('license').annotate(usage=Count('pk')):
            _add(dev_usage['license'], LicenseParameterTypeEnum.device, dev_usage['usage'])

        for serv_usage in LicenseUsageDeviceService.objects.filter(
            service__isnull=False
        ).values('license').annotate(usage=Count('pk')):
            _add(serv_usage['license'], LicenseParameterTypeEnum.service, serv_usage['usage'])

        for user_usage in LicenseUsageUser.objects.values('license').annotate(usage=Count('pk')):
            _add(user_usage['license'], LicenseParameterTypeEnum.user, user_usage['usage'])

        for ext_lic_usage in LicenseUsageExtLicense.objects.values('license').annotate(usage=Count('pk')):
            _add(ext_lic_usage['license'], LicenseParameterTypeEnum.ext_license, ext_lic_usage['usage'])

        return usage_by_lic


class _LicenseViolationManager(models.Manager):
    def is_hard_violated(self, license):
        """
        :type license: LicenseEnum
        """
        # only hard violations are actual violations, else it's a warning (grace)
        return license.name in self._get_hard_violated_licenses_names()

    @memoize_with_expiry(1)
    def _get_hard_violated_licenses_names(self):
        return frozenset(LicenseViolation.objects.filter(hard=True).values_list('license', flat=True))


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


class icswEggCradleManager(models.Manager):
    def create_system_cradle(self):
        _sc = self.create(
            system_cradle=True
        )
        return _sc

    def get_system_cradle(self):
        try:
            _sc = self.get(Q(system_cradle=True))
        except icswEggCradle.DoesNotExist:
            return None
        else:
            return _sc


class icswEggCradle(models.Model):
    """
    container for all baskets, more than one cradle may be defined
    but only one is a system cradle

    grace handling: when the system requires more eggs then available, the grace_period
    starts to run. During this time up to limit_grace eggs can be consumed, if this
    limit is reached the system will no longer accept new egg requests
    """
    objects = icswEggCradleManager()
    idx = models.AutoField(primary_key=True)
    # is a sytem basket, only one allowed (and no user baskets defined)
    system_cradle = models.BooleanField(default=True)
    # how many eggs are currently installed (and covered by licenses)
    installed = models.IntegerField(default=0)
    # how many eggs are currently available (must be smaller or equal to the installed eggs)
    available = models.IntegerField(default=0)
    # grace days, defaults to 14 days
    grace_days = models.IntegerField(default=14)
    # start of grace period
    grace_start = models.DateTimeField(null=True)
    # limit of eggs when in grace, defaults to 110% of installed
    limit_grace = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def calc(self):
        _avail = 0
        _installed = 0
        for _basket in icswEggBasket.objects.get_valid_baskets():
            if _basket:
                _avail += _basket.eggs
                _installed += _basket.eggs
        for _cons in self.icsweggconsumer_set.all():
            _avail -= _cons.get_all_consumed()
        self.available = _avail
        self.installed = _installed
        self.save(update_fields=["available", "installed"])

    def __unicode__(self):
        return "EggCradle, {:d} installed, {:d} available".format(
            self.installed,
            self.available,
        )


class icswEggBasketManager(models.Manager):
    def get_valid_baskets(self):
        _now = django.utils.timezone.now()
        return self.filter(
            Q(egg_cradle__system_cradle=True) &
            Q(is_valid=True) &
            Q(valid_from__lte=_now) &
            Q(valid_to__gte=_now)
        )

    def num_valid_baskets(self):
        return self.get_valid_baskets().count()

    def create_dummy_basket(self, eggs=10, validity=20):
        _now = django.utils.timezone.now()
        _sys_c = icswEggCradle.objects.get(Q(system_cradle=True))
        _new_b = self.create(
            egg_cradle=_sys_c,
            dummy=True,
            is_valid=True,
            valid_from=_now - datetime.timedelta(days=1),
            valid_to=_now.replace(year=_now.year + validity),
            eggs=eggs,
        )
        return _new_b


class icswEggBasket(models.Model):
    objects = icswEggBasketManager()
    # basket definition, from ovum global parameters
    idx = models.AutoField(primary_key=True)
    # basket
    egg_cradle = models.ForeignKey(icswEggCradle)
    # dummy entry
    dummy = models.BooleanField(default=False)
    # valid from / to
    valid_from = models.DateField()
    valid_to = models.DateField()
    # valid flag
    is_valid = models.BooleanField(default=True)
    # link to license, null for default basket
    license = models.ForeignKey(License, null=True)
    # eggs defined
    eggs = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = False

    def __unicode__(self):
        return "EggBasket (valid={})".format(self.is_valid)


@receiver(signals.post_save, sender=icswEggBasket)
def icsw_egg_basket_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        _inst.egg_cradle.calc()


class icswEggEvaluationDefManager(models.Manager):
    def get_active_def(self):
        try:
            _cd = self.get(Q(active=True))
        except icswEggEvaluationDef.DoesNotExist:
            _cd = None
        return _cd

    def create_dummy_def(self):
        _sys_c = icswEggCradle.objects.get(Q(system_cradle=True))
        _new_b = self.create(
            egg_cradle=_sys_c,
            content="",
            dummy=True,
            active=True,
        )
        return _new_b


class icswEggEvaluationDef(models.Model):
    """
    Egg evaluation definition
    """
    objects = icswEggEvaluationDefManager()
    # defining files for eggbasketconsumers
    idx = models.AutoField(primary_key=True)
    # cradle
    egg_cradle = models.ForeignKey(icswEggCradle)
    # content
    content = models.TextField(default="")
    # dummy entry
    dummy = models.BooleanField(default=False)
    # active flag, at least one Def must be active
    active = models.BooleanField(default=False)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def create_consumers(self):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        from initat.cluster.backbone.models import ConfigServiceEnum
        if not self.active:
            raise StandardError("Cannot create consumers from inactive EggEvaluationDef")
        # create or update all consumers
        # build list of required consumers
        _c_list = []
        for _name, _server in icswServiceEnum.get_server_enums().iteritems():
            _cs_enum = ConfigServiceEnum.objects.get(Q(enum_name=_name))
            if _server.egg_actions:
                for _action in _server.egg_actions:
                    _c_list.append(
                        {
                            "action": _action,
                            "service": _server,
                            "db_enum": _cs_enum,
                        }
                    )
        for _entry in _c_list:
            try:
                _cur_consum = icswEggConsumer.objects.get(
                    Q(action=_entry["action"].action) &
                    Q(content_type=_entry["action"].content_type) &
                    Q(config_service_enum=_entry["db_enum"]) &
                    Q(egg_cradle=self.egg_cradle)
                )
            except icswEggConsumer.DoesNotExist:
                # create new
                _cur_consum = icswEggConsumer.objects.create(
                    egg_evaluation_def=self,
                    xml_node_reference="",
                    egg_cradle=self.egg_cradle,
                    # multiplier=_entry["action"].weight,
                    content_type=_entry["action"].content_type,
                    action=_entry["action"].action,
                    config_service_enum=_entry["db_enum"],
                    valid=False,
                )
            else:
                if _cur_consum.egg_evaluation_def.idx != self.idx:
                    _cur_consum.valid = False
            _cur_consum.valid = False
            if _entry["action"].weight != _cur_consum.multiplier:
                _cur_consum.multiplier = _entry["action"].weight
                _cur_consum.valid = False
            _cur_consum.save()

    class Meta:
        abstract = False

    def __unicode__(self):
        return "EggEvaluationDef (dummy={}, active={})".format(
            self.dummy,
            self.active,
        )


class icswEggConsumer(models.Model):
    """
    a consumers gets created by request from a steering XML control file
    it links a licensed service with an database element with a fixed or dynamic
    multiplier to calculate how many eggs are being consumd by a given funtion
    """
    # defines how eggs are consumed
    idx = models.AutoField(primary_key=True)
    # evaluation reference
    egg_evaluation_def = models.ForeignKey(icswEggEvaluationDef)
    # cradle
    egg_cradle = models.ForeignKey(icswEggCradle)
    # xml reference, points to an UUID
    xml_node_reference = models.TextField(default="")
    # content type
    content_type = models.ForeignKey(ContentType, null=True)
    # name for reference, used in icswServiceEnumBase
    action = models.CharField(max_length=63, default="")
    # total consumed by all fullfilled (valid=True) requests
    consumed = models.IntegerField(default=0)
    # config service enum
    config_service_enum = models.ForeignKey("backbone.ConfigServiceEnum")
    # multiplier
    multiplier = models.IntegerField(default=1)
    # dynamic multiplier ?
    dynamic_multiplier = models.BooleanField(default=False)
    # valid, parameters have not changed (after installing a new XML file)
    valid = models.BooleanField(default=False)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = False
        ordering = ("content_type__model", "config_service_enum__enum_name", "action")

    def get_all_consumed(self):
        _ws = self.icsweggrequest_set.filter(Q(is_lock=False) & (Q(valid=True))).values_list("weight", flat=True)
        if _ws.count():
            _sum = sum(_ws)
            if _sum != self.consumed:
                self.consumed = _sum
                self.save(update_fields=["consumed"])
            return _sum
        else:
            return 0

    def consume(self, request):
        # if request.valid is False, try to consume it
        # if request.valid is True, check the target weight
        _target_weight = self.multiplier
        if not request.valid:
            _to_consume = _target_weight
        else:
            _to_consume = _target_weight - request.weight
        _avail = self.egg_cradle.available
        if _avail > _to_consume:
            self.egg_cradle.available -= _to_consume
            self.consumed += _to_consume
            self.save(update_fields=["consumed"])
            self.egg_cradle.save(update_fields=["available"])
            request.valid = True
        else:
            request.valid = False
        request.weight = _target_weight

    def get_info_line(self):
        return [
            logging_tools.form_entry(self.action, header="action"),
            logging_tools.form_entry(unicode(self.config_service_enum), header="ConfigService"),
            logging_tools.form_entry_right(self.multiplier, header="Weight"),
            logging_tools.form_entry_center(unicode(self.content_type), header="ContentType"),
            logging_tools.form_entry_right(self.get_all_consumed(), header="consumed"),
        ]

    def __unicode__(self):
        return u"EggConsumer {}@{} -> {} per {}".format(
            self.action,
            self.config_service_enum.name,
            logging_tools.get_plural("egg", self.multiplier),
            self.content_type.model,
        )


@receiver(signals.post_save, sender=icswEggConsumer)
def icsw_egg_consumer_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        if not _inst.valid:
            pass
            # print(
            #    "Recalc {}, {}".format(
            #        unicode(_inst),
            #        logging_tools.get_plural("request", _inst.icsweggrequest_set.all().count()),
            #    )
            # )


class icswEggRequest(models.Model):
    """
    Egg request, are stored to be reevaluated at any time
    """
    idx = models.AutoField(primary_key=True)
    # egg consumer
    egg_consumer = models.ForeignKey(icswEggConsumer)
    # object id, may be None
    object_id = models.IntegerField(null=True)
    # effective number of eggs
    weight = models.IntegerField(default=0)
    # lock, is a lock (no eggs should be consumed, always returns false)
    is_lock = models.BooleanField(default=False)
    # valid, enough eggs present
    # generate an request even when not enough eggs are present, set valid=False
    valid = models.BooleanField(default=False)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def consume(self):
        if self.is_lock:
            # is a lock, we dont consume anything
            self.weight = 0
            self.valid = False
        else:
            # consum from egg_consumer
            self.egg_consumer.consume(self)
        self.save(update_fields=["weight", "valid"])
        return self.valid

    class Meta:
        abstract = False


@receiver(signals.pre_save, sender=icswEggCradle)
def icsw_egg_cradle_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        if _inst.system_cradle:
            _found = icswEggCradle.objects.filter(Q(system_cradle=True)).exclude(Q(pk=_inst.pk)).count()
            if _found:
                raise ValidationError("only one system cradle allowed")
