
# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
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
import enum

import django.utils.timezone
from dateutil import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals, Q
from django.dispatch import receiver

from initat.cluster.backbone.available_licenses import get_available_licenses, LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.functions import memoize_with_expiry, cluster_timezone
from initat.tools import logging_tools
from initat.tools.bgnotify.create import propagate_channel_object
from .license_xml import ICSW_XML_NS, ICSW_XML_NS_NAME, ICSW_XML_NS_MAP, LIC_FILE_RELAX_NG_DEFINITION

__all__ = [
    "LicenseState",
    "License",
    "LicenseEnum",
    "LicenseParameterTypeEnum",
    "ICSW_XML_NS",
    "ICSW_XML_NS_MAP",
    "ICSW_XML_NS_NAME",
    "LIC_FILE_RELAX_NG_DEFINITION",
    "icswEggCradle",
    "icswEggEvaluationDef",
    "icswEggBasket",
    "icswEggConsumer",
    "icswEggRequest",
    "LICENSE_USAGE_GRACE_PERIOD",
]

LICENSE_USAGE_GRACE_PERIOD = relativedelta.relativedelta(weeks=2)


class InitProduct(enum.Enum):
    CORVUS = 1
    NOCTUA = 2
    NESTOR = 3

    def get_version_family(self, version):
        if version == "0.0":
            version = list(_PRODUCT_FAMILY_MATRIX.keys())[-1]

        return _PRODUCT_FAMILY_MATRIX.get(version, {}).get(self, "")

_PRODUCT_FAMILY_MATRIX = collections.OrderedDict(  # ordered dict so we know which is last
    [
        (
            "2.5",
            {
                InitProduct.CORVUS: "Corvus hawaiiensis",  # Hawaiikraehe
                InitProduct.NOCTUA: "Strigidae occidentalis",  # Fleckenkauz
                InitProduct.NESTOR: "Nestor notabilis",  # Kea
            }
        ),
        (
            "3.0",
            {
                InitProduct.CORVUS: "CORVUS Corax",  # Kolkrabe
                InitProduct.NOCTUA: "NOCTUA Athene",  # Steinkauz
                InitProduct.NESTOR: "NESTOR Notabilis",  # Kea
            }
        ),
        (
            "3.1",
            {
                InitProduct.CORVUS: "Corvus splendens",  # Glanzkraehe
                InitProduct.NOCTUA: "Strigidae rufipes",  # Rostfusskauz
                InitProduct.NESTOR: "Nestor meridionalis",  # Kaka (Waldpapagei)
            }
        )
    ]
)


from initat.icsw.service import constants


class LicenseState(enum.IntEnum):
    # NOTE: this is ordered in the sense that if multiple licenses are
    # present, the higher one is actually used
    violated = constants.LIC_STATE_VIOLATED        # license parameters have been violated
    valid = constants.LIC_STATE_VALID              # license is valid now
    grace = constants.LIC_STATE_GRACE              # license has expired but we still let the software run
    new_install = constants.LIC_STATE_NEW_INSTALL  # to be defined
    expired = constants.LIC_STATE_EXPIRED          # license used to be valid but is not valid anymore
    valid_in_future = constants.LIC_STATE_VALID_IN_FUTURE  # license will be valid in the future
    none = constants.LIC_STATE_NONE                # license not present
    not_needed = constants.LIC_STATE_NOT_NEEDED    # license not needed
    ip_mismatch = constants.LIC_STATE_IP_MISMATCH  # IP mismatch, should not run
    fp_mismatch = constants.LIC_STATE_FP_MISMATCH  # fingerprint mismatch, should not run

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
        # TODO: new_install?
        if not self._license_readers:
            return LicenseState.none
        _states = [r.get_license_state(license, parameters) for r in self._license_readers]
        _valid_states = [_state for _state in _states if _state not in [LicenseState.fp_mismatch]]
        if len(_valid_states):
            return max(_valid_states)
        else:
            return LicenseState.fp_mismatch

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
        # only compare with the latest version ? ToDo, Fixme
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
        # all available licenses
        for available_lic in get_available_licenses():
            if available_lic.enum_value in valid_lics:
                if available_lic.product is not None:
                    # print("   ", available_lic.product)
                    product_licenses.add(available_lic.product)

        # print("+", product_licenses)
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
        """
        Returns all licenses which are active (and should be displayed to the user)
        Problem: if you upload multiple license files (== license-packs) with the
        same name / UUID the system will return the any valid licenses and not the one
        from the latest files
        Quick fix: delete previous license files
        """
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        # fix for above problem: build a map dict where only the latest license files
        # are referenced
        merged_maps = LicenseFileReader.merge_license_maps(self._license_readers)
        # import pprint
        # pprint.pprint(merged_maps)
        return [
            lic for lic in set().union(
                *[
                    _struct["reader"].get_valid_licenses() for _struct in merged_maps.values()
                ]
            )
        ]

    def get_valid_parameters(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        # fix for above problem: build a map dict where only the latest license files
        # are referenced
        merged_maps = LicenseFileReader.merge_license_maps(self._license_readers)
        # import pprint
        # pprint.pprint(merged_maps)
        res = {}
        for _struct in merged_maps.values():
            # pprint.pprint(_struct)
            res.update(_struct["reader"].get_valid_parameters())
        return res

    def get_license_packages(self):
        """Returns license packages in custom format for the client."""
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return LicenseFileReader.get_license_packages(self._license_readers)

    @property
    def raw_license_info(self):
        # just for info
        return sum([_reader.raw_license_info for _reader in self._license_readers], [])

    _license_readers_cache = {}

    def cached_log(self, what, log_level=logging_tools.LOG_LEVEL_ERROR):
        if not hasattr(self, "_log_cache"):
            self._log_cache = []
        self._log_cache.append((what, log_level))

    @property
    def cached_logs(self):
        for what, log_level in self._log_cache:
            yield ("[CLL] {}".format(what), log_level)
        self._log_cache = []

    @property
    @memoize_with_expiry(10, _cache=_license_readers_cache)
    def _license_readers(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        from initat.cluster.backbone.models import device_variable
        from initat.tools import hfp_tools

        if not hasattr(self, "_log_cache"):
            self._log_cache = []
        cluster_id = device_variable.objects.get_cluster_id()
        cur_fp = hfp_tools.get_server_fp(serialize=True)

        readers = []
        for lic in self.filter(Q(valid=True)):
            try:
                readers.append(
                    LicenseFileReader(
                        lic,
                        cluster_id=cluster_id,
                        current_fingerprint=cur_fp,
                        log_com=self.cached_log,
                    )
                )
            except LicenseFileReader.InvalidLicenseFile as e:
                self.cached_log(
                    "Invalid license file in database {}: {}".format(
                        lic.file_name,
                        e,
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )

        return readers

    def check_ova_baskets(self):
        from initat.cluster.backbone.models import device_variable
        # cluster id
        c_id = device_variable.objects.get_cluster_id()
        if c_id:
            valid_params = self.get_valid_parameters()
            # import pprint
            # pprint.pprint(valid_params)
            # rewrite params to use only the license_id_name (or None) as partial key
            valid_params = {
                (_idx, _lic.id if _lic else None): _value for (_idx, _lic), _value in valid_params.items()
            }
            # print(valid_params)
            _present_lics = valid_params.keys()
            # read all baskets
            bk_dict = {
                (_basket.license_id, _basket.license_id_name or None): _basket for _basket in icswEggBasket.objects.exclude(Q(license=None))
            }
            # delete baskets where the license has vanished
            for _del_bk in set(bk_dict.keys()) - _present_lics:
                _basket = bk_dict[_del_bk]
                for _request in _basket.icsweggrequest_set.all():
                    _request.egg_basket = None
                    _request.save(update_fields=["egg_basket"])
                _basket.delete()
            # update matching pks
            for _ok_bk in set(bk_dict.keys()) & _present_lics:
                _basket = bk_dict[_ok_bk]
                _basket.update(valid_params[_ok_bk])
                # if _basket.eggs != valid_params[_ok_bk]:
                #     _basket.eggs = valid_params[_ok_bk]
                #    _basket.save()
            # new pks
            for _new_bk, _new_lic_name in _present_lics - set(bk_dict.keys()):
                _data = valid_params[(_new_bk, _new_lic_name)]
                # print("add", _data)
                new_basket = icswEggBasket.objects.create_basket(
                    installed=_data[0],
                    valid_from=cluster_timezone.localize(_data[1]),
                    valid_to=cluster_timezone.localize(_data[2]),
                    license=License.objects.get(Q(pk=_new_bk)),
                    license_id_name=_new_lic_name or "",
                )
            # check dummy baskets
            for _dummy in icswEggBasket.objects.filter(Q(dummy=True) | Q(is_valid=False)):
                # trigger recalc of available
                _dummy.save()

    def get_license_info(self, lic_obj):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return LicenseFileReader(lic_obj).license_info

    def get_raw_license_info(self, lic_obj):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return LicenseFileReader(lic_obj).raw_license_info


########################################
# actual license documents:

class License(models.Model):
    objects = _LicenseManager()
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)
    valid = models.BooleanField(default=True)
    file_name = models.CharField(max_length=512)
    license_file = models.TextField()  # contains the exact file content of the respective license files

    def __str__(self):
        if self.idx:
            return "License {} ({:d})".format(
                self.file_name,
                self.idx,
            )
        else:
            return "License {} (non-DB)".format(
                self.file_name,
            )

    class Meta:
        app_label = "backbone"
        verbose_name = "License"
        ordering = ("idx",)


@receiver(signals.post_save, sender=License)
@receiver(signals.post_delete, sender=License)
def license_post_save_delete(sender, **kwargs):
    _LicenseManager._license_readers_cache.clear()
    License.objects.check_ova_baskets()


@receiver(signals.post_save, sender=License)
def license_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]


########################################
# license usage management:

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

    Dependencies / Relationships

    Cradle -> Basket ->
           -> EvaluationDef [Creates Consumers]
                -> Consumer {links to EvaluationDef and Cradle}
                     -> Request {links to Consumer and Basket}

    The Consumers are not bound to a basket because a given consumer
    can distribute its requests among different baskets
    """
    objects = icswEggCradleManager()
    idx = models.AutoField(primary_key=True)
    # is a sytem basket, only one allowed (and no user baskets defined)
    system_cradle = models.BooleanField(default=True)
    # how many eggs are currently installed (sum of all cradles)
    installed = models.IntegerField(default=0)
    # how many eggs are currently available (sum of all cradles)
    available = models.IntegerField(default=0)
    # how many eggs are currently available when ghosted ova are also taken into account
    # (sum of all cradles)
    available_ghost = models.IntegerField(default=0)
    # grace days, defaults to 14 days
    grace_days = models.IntegerField(default=14)
    # start of grace period
    grace_start = models.DateTimeField(null=True)
    # limit of eggs when in grace, defaults to 110% of installed
    limit_grace = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def consume(self, consumer, to_consume, save=True):
        self.available_ghost -= to_consume
        if not consumer.ghost:
            self.available -= to_consume
        if save:
            self.save(update_fields=["available", "available_ghost"])

    def reset(self):
        self.available = 0
        self.installed = 0
        self.available_ghost = 0
        self.save(update_fields=["available", "installed", "available_ghost"])

    def recalc(self):
        self.reset()
        # recalc ova values for all baskets and consumers
        for _basket in icswEggBasket.objects.get_valid_baskets():
            _basket.reset(self)
        basket_dict = {
            _basket.idx: _basket for _basket in icswEggBasket.objects.all()
        }
        for _cons in self.icsweggconsumer_set.all():
            _cons.recalc(self, basket_dict)
        [_basket.save() for _basket in basket_dict.values()]
        self.save()
        # to debug the database connections
        # from initat.cluster.backbone.middleware import show_database_calls
        # show_database_calls()

    def __str__(self):
        return "EggCradle, {:d} installed, {:d} available ({:d} ghost)".format(
            self.installed,
            self.available,
            self.available_ghost,
        )


@receiver(signals.pre_save, sender=icswEggCradle)
def icsw_egg_cradle_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        if _inst.system_cradle:
            _found = icswEggCradle.objects.filter(Q(system_cradle=True)).exclude(Q(pk=_inst.pk)).count()
            if _found:
                raise ValidationError("only one system cradle allowed")


@receiver(signals.post_save, sender=icswEggCradle)
def icsw_egg_cradle_post_save(sender, **kwargs):
    if "instance" in kwargs:
        from initat.cluster.backbone.serializers import icswEggCradleSerializer
        from ..websockets.constants import WSStreamEnum
        _inst = kwargs["instance"]
        propagate_channel_object(
            WSStreamEnum.ova_counter,
            icswEggCradleSerializer(_inst).data,
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

    def create_basket(self, **kwargs):
        _sys_c = icswEggCradle.objects.get(Q(system_cradle=True))
        _new_b = self.create(
            egg_cradle=_sys_c,
            dummy=kwargs.pop("dummy", False),
            is_valid=True,
            **kwargs
        )
        return _new_b

    def create_dummy_basket(self, installed=10, validity=1):
        # validity is in years
        _now = django.utils.timezone.now()
        return self.create_basket(
            dummy=True,
            valid_from=_now - datetime.timedelta(days=1),
            valid_to=_now.replace(year=_now.year + validity),
            installed=installed,
        )

    def get_values_per_license_name(self):
        ova_per_lic = {}
        for _basket in self.filter(Q(is_valid=True)):
            ova_per_lic.setdefault(_basket.license_id_name, {}).update(_basket.values())
        return ova_per_lic


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
    # link to license file, null for default basket
    license = models.ForeignKey(License, null=True)
    # license id name, used for license-bound ova
    license_id_name = models.CharField(default="", max_length=63)
    # how many eggs are currently installed (and covered by licenses)
    installed = models.IntegerField(default=0)
    # how many eggs are currently available (must be smaller or equal to the installed eggs)
    available = models.IntegerField(default=0)
    # how many eggs are currently available when ghosted ova or also taken into account
    available_ghost = models.IntegerField(default=0)
    # grace days, defaults to 14 days
    grace_days = models.IntegerField(default=14)
    # start of grace period
    grace_start = models.DateTimeField(null=True)
    # limit of eggs when in grace, defaults to 110% of installed
    limit_grace = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def get_license_data(self):
        if self.license_id_name:
            _lic = getattr(LicenseEnum, self.license_id_name)
            simple_dict = {
                key: getattr(_lic.value, key) for key in dir(_lic.value) if not key.startswith("_")
            }
        else:
            simple_dict = {
                "lic_id": "global",
                "name": "Global",
                "description": "Global ova basket",
                "warn_percentage": 85,
                "crit_percentage": 95,
                "ova_repr": "Ova",
            }
        return simple_dict

    def values(self):
        return {
            _key: getattr(self, _key) for _key in {"installed", "available", "available_ghost"}
        }

    def reset(self, cradle=None):
        self.available = self.installed
        self.available_ghost = self.installed
        if not cradle:
            self.egg_cradle.available += self.available
            self.egg_cradle.available_ghost += self.available_ghost
            self.egg_cradle.installed += self.installed
            self.egg_cradle.save(update_fields=["available", "available_ghost", "installed"])
        else:
            cradle.installed += self.installed
            cradle.available += self.available
            cradle.available_ghost += self.available_ghost
        self.save(update_fields=["available", "available_ghost"])

    def consume(self, consumer, to_consume, cradle=None, save=True):
        self.available_ghost -= to_consume
        if not consumer.ghost:
            self.available -= to_consume
        if save:
            self.save(update_fields=["available_ghost", "available"])
        if cradle is None:
            self.egg_cradle.consume(consumer, to_consume)
        else:
            cradle.consume(consumer, to_consume, save=save)

    def update(self, data):
        _eggs, _from, _to = data
        self.installed = _eggs
        self.valid_from = cluster_timezone.localize(_from)
        self.valid_to = cluster_timezone.localize(_to)
        self.save()

    class Meta:
        abstract = False
        ordering = ("dummy", "is_valid", "license", "license_id_name")
        unique_together = (("license", "license_id_name"), )

    def get_info_line(self):
        return [
            logging_tools.form_entry_center("yes" if self.dummy else "no", header="Dummy"),
            logging_tools.form_entry(str(self.valid_from), header="valid from"),
            logging_tools.form_entry(str(self.valid_to), header="valid to"),
            logging_tools.form_entry(self.license_id_name or "global", header="License"),
            logging_tools.form_entry_center("yes" if self.is_valid else "no", header="valid"),
            logging_tools.form_entry_right(self.installed, header="installed"),
            logging_tools.form_entry_right(self.available, header="available"),
            logging_tools.form_entry_right(self.available_ghost, header="ghost"),
        ]

    def __str__(self):
        return "EggBasket (valid={})".format(self.is_valid)


@receiver(signals.pre_save, sender=icswEggBasket)
def icsw_egg_basket_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        if not _inst.license_id and not _inst.dummy:
            raise ValidationError("EggBasket without license needs the dummy flag set")
        _now = django.utils.timezone.now()
        if isinstance(_inst.valid_from, datetime.date) and not isinstance(_inst.valid_from, datetime.datetime):
            _now = _now.date()
        _inst.is_valid = _inst.valid_from <= _now and _now <= _inst.valid_to
        if not _inst.is_valid:
            _inst.available = 0


@receiver(signals.post_save, sender=icswEggBasket)
def icsw_egg_basket_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        # _inst.egg_cradle.calc()


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
            raise Exception("Cannot create consumers from inactive EggEvaluationDef")
        icswEggConsumer.objects.filter(Q(content_type=None)).delete()
        # create or update all consumers
        # build list of required consumers
        _c_list = []
        for _name, _server in icswServiceEnum.get_server_enums().items():
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
                    Q(egg_cradle=self.egg_cradle),
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
                    ghost=_entry["action"].ghost,
                    valid=False,
                )
            else:
                # update
                if _cur_consum.ghost != _entry["action"].ghost:
                    _cur_consum.ghost = _entry["action"].ghost
                    _cur_consum.valid = False
                # print(_entry["action"].content_type)
                if _cur_consum.egg_evaluation_def.idx != self.idx:
                    _cur_consum.valid = False
            if _entry["action"].license_id_name != _cur_consum.license_id_name:
                # license_id_name changed, consumer is now invalid
                _cur_consum.license_id_name = _entry["action"].license_id_name
                _cur_consum.valid = False
            if _entry["action"].weight != _cur_consum.multiplier:
                _cur_consum.multiplier = _entry["action"].weight
                _cur_consum.valid = False
            if _entry["action"].timeframe_secs != _cur_consum.timeframe_secs:
                _cur_consum.timeframe_secs = _entry["action"].timeframe_secs
                _cur_consum.valid = False
            _cur_consum.save()

    class Meta:
        abstract = False

    def __str__(self):
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
    # ghost (will be counted but not taken for usage)
    ghost = models.BooleanField(default=False)
    # valid, parameters have not changed (after installing a new XML file)
    # valid == False means a forced recalculation of all related baskets and requests
    valid = models.BooleanField(default=False)
    # bound to a given license
    license_id_name = models.CharField(default="", max_length=63)
    # timeframe in seconds
    timeframe_secs = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = False
        ordering = ("content_type__model", "config_service_enum__enum_name", "action")

    def recalc(self, cradle, basket_dict):
        self.consumed = 0
        # touched baskets
        # basket_dict = {}
        # handle all requestes without a valid basket
        for _req in self.icsweggrequest_set.exclude(
            Q(is_lock=True)
        ).select_related(
            "egg_basket"
        ):
            if not _req.egg_basket_id:
                # print("-")
                self.consume(_req, cradle=cradle, basket_dict=basket_dict)
            else:
                # print("+")
                self.consumed += _req.weight
                # _req.egg_basket.consume(self, _req.weight, cradle=cradle)
                basket_dict[_req.egg_basket_id].consume(
                    self,
                    _req.weight,
                    cradle=cradle,
                    save=False,
                )
        self.save(update_fields=["consumed"])
        # print("*", self.consumed)

    def get_num_consumers(self):
        return self.icsweggrequest_set.filter(
            Q(is_lock=False) & (Q(valid=True))
        ).count()

    def consume(self, request, cradle=None, basket_dict=None):
        _update_fields = []
        _pre_valid = request.valid
        if request.is_lock:
            # is a lock, we dont consume anything
            _update_fields.append("weight")
            request.weight = 0
            request.valid = False
        else:
            # consum from egg_consumer
            # if request.valid is False, try to consume it
            # if request.valid is True, check the target weight
            _target_weight = self.multiplier * request.mult
            if not request.valid:
                # request was not valid, consume the target weight
                _to_consume = _target_weight
            else:
                # request was valid, consume the target weight minus the current allocated weight
                _to_consume = _target_weight - request.weight
            if _to_consume or not request.egg_basket_id:
                _request_ok = True
                if not request.egg_basket_id:
                    # consume from basket
                    _to_consume = _target_weight
                    _baskets = icswEggBasket.objects.filter(
                        Q(license_id_name=self.license_id_name)
                    ).order_by(
                        "-available"
                    )
                    if not len(_baskets):
                        # no baskets found
                        # if self.ghost:
                        #    # ghost request, is ok
                        #    _request_ok = True
                        # else:
                        _request_ok = False
                    else:
                        request.egg_basket = _baskets[0]
                # something to consume, resolve egg_cradle
                if _request_ok:
                    _avail = request.egg_basket.available
                    if _avail > _to_consume:
                        if _to_consume:
                            # nothing to consume (request was already fullfilled)
                            if basket_dict is None:
                                # explicit update, store consumed
                                request.egg_basket.consume(self, _to_consume, cradle=cradle)
                            else:
                                basket_dict[request.egg_basket_id].consume(
                                    self,
                                    _to_consume,
                                    cradle=cradle,
                                    save=False,
                                )
                            self.consumed += _to_consume
                            if cradle is None:
                                # explicit update, store consumed
                                self.save(update_fields=["consumed"])
                        if self.timeframe_secs:
                            request.valid_until = cluster_timezone.localize(
                                datetime.datetime.now() + datetime.timedelta(seconds=self.timeframe_secs)
                            )
                        else:
                            request.valid_until = None
                        request.valid = True
                    else:
                        request.valid = False
                else:
                    request.valid = False
            else:
                # nothing to consume, request is valid
                request.valid = True
            if request.weight != _target_weight:
                request.weight = _target_weight
                _update_fields.append("weight")
            if _pre_valid != request.valid:
                _update_fields.append("valid")
            # todo, improve save via dynamic update_fields, handle valid_until via
            # kwarg flag ?
        request.save(
            update_fields=[
                "weight", "valid", "valid_until", "egg_basket",
            ]
        )
        return request.valid

    def get_info_line(self):
        _consumers = self.get_num_consumers()
        return [
            logging_tools.form_entry(self.action, header="action"),
            logging_tools.form_entry(str(self.config_service_enum), header="ConfigService"),
            logging_tools.form_entry_right(self.multiplier, header="Weight"),
            logging_tools.form_entry_center("yes" if self.ghost else "no", header="Ghost"),
            logging_tools.form_entry_center(str(self.content_type), header="ContentType"),
            logging_tools.form_entry_center(self.license_id_name or "global", header="License"),
            logging_tools.form_entry_right(
                logging_tools.get_diff_time_str(self.timeframe_secs) if self.timeframe_secs else "---",
                header="timeframe",
            ),
            logging_tools.form_entry_right(_consumers, header="entries"),
            logging_tools.form_entry_right(self.consumed, header="consumed"),
            logging_tools.form_entry_right(
                "{:.2f}".format(
                    float(self.consumed) / float(_consumers)
                ) if _consumers else "-",
                header="mean"
            ),
        ]

    def __str__(self):
        return "EggConsumer {}@{} -> {} per {}".format(
            self.action,
            self.config_service_enum.name,
            logging_tools.get_plural("egg", self.multiplier),
            self.content_type.model if self.content_type else "N/A model",
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
    # egg consumer (which has produced / emitted this request)
    egg_consumer = models.ForeignKey(icswEggConsumer)
    # egg basket, may be null for transition / grace eggs
    egg_basket = models.ForeignKey(icswEggBasket, null=True)
    # object id, may be None
    object_id = models.IntegerField(null=True)
    # local multiplicator
    mult = models.IntegerField(default=1)
    # effective number of eggs
    weight = models.IntegerField(default=0)
    # lock, is a lock (no eggs should be consumed, always returns false)
    is_lock = models.BooleanField(default=False)
    # valid, enough eggs present
    # generate an request even when not enough eggs are present, set valid=False
    valid = models.BooleanField(default=False)
    # valid until, used for locks with a limited validity
    valid_until = models.DateTimeField(default=None, null=True)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def consume(self):
        return self.egg_consumer.consume(self)

    class Meta:
        abstract = False
