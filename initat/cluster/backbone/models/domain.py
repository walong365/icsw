# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" Model definitions for domain related objects """



import io
import os
import re
import uuid

from PIL import Image, ImageEnhance, ImageFilter
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import check_empty_string, check_non_empty_string, \
    check_float, get_related_models
from initat.tools import process_tools

__all__ = [
    b"domain_name_tree",
    b"valid_domain_re",
    b"domain_tree_node",
    b"category_tree",
    b"category",
    b"TREE_SUBTYPES",
    b"TOP_MONITORING_CATEGORY",
    b"location_gfx",
    b"device_mon_location",
    b"DomainTypeEnum",
]

# top monitoring category
TOP_MONITORING_CATEGORY = "mon"
TOP_LOCATION_CATEGORY = "location"
TOP_CONFIG_CATEGORY = "config"
TOP_DEVICE_CATEGORY = "device"

TREE_SUBTYPES = {
    TOP_MONITORING_CATEGORY,
    TOP_LOCATION_CATEGORY,
    TOP_CONFIG_CATEGORY,
    TOP_DEVICE_CATEGORY,
}

# validation regexps
valid_domain_re = re.compile("^[a-zA-Z0-9-_]+$")
valid_category_re = re.compile("^[a-zA-Z0-9-_\.]+$")


class domain_name_tree(object):
    # helper structure
    def __init__(self):
        self.__node_dict = {}
        self.__domain_lut = {}
        for cur_node in domain_tree_node.objects.all().order_by("depth"):
            self.__node_dict[cur_node.pk] = cur_node
            # self.__domain_lut.setdefault(cur_node.full_name, []).append(cur_node)
            self.__domain_lut[cur_node.full_name] = cur_node
            cur_node._sub_tree = {}
            if cur_node.parent_id is None:
                self._root_node = cur_node
            else:
                if cur_node.depth - 1 != self.__node_dict[cur_node.parent_id].depth:
                    # fix depth
                    cur_node.depth = self.__node_dict[cur_node.parent_id].depth + 1
                    cur_node.save()
                self.__node_dict[cur_node.parent_id]._sub_tree.setdefault(cur_node.name, []).append(cur_node)

    def check_intermediate(self):
        device = apps.get_model("backbone", "device")
        net_ip = apps.get_model("backbone", "net_ip")
        used_pks = set(device.objects.all().values_list("domain_tree_node", flat=True)) | set(net_ip.objects.all().values_list("domain_tree_node", flat=True))
        for cur_tn in self.__node_dict.values():
            is_im = cur_tn.pk not in used_pks
            if cur_tn.intermediate != is_im:
                cur_tn.intermediate = is_im
                cur_tn.save()

    def add_device_references(self):
        device = apps.get_model("backbone", "device")
        used_dtn_pks = list(device.objects.filter(Q(enabled=True) & Q(device_group__enabled=True)).values_list("domain_tree_node_id", flat=True))
        used_dict = {key: used_dtn_pks.count(key) for key in set(used_dtn_pks)}
        for value in self.__node_dict.values():
            value.local_refcount = used_dict.get(value.pk, 0)
        for value in self.__node_dict.values():
            value.total_refcount = self._get_sub_refcounts(value)

    def _get_sub_refcounts(self, s_node):
        return self.__node_dict[s_node.pk].local_refcount + sum([self._get_sub_refcounts(sub_node) for sub_node in sum(iter(s_node._sub_tree.values()), [])])

    def add_domain(self, new_domain_name):
        dom_parts = list(reversed(new_domain_name.split(".")))
        cur_node = self._root_node
        for _part_num, dom_part in enumerate(dom_parts):
            # part_num == len(dom_parts) - 1
            if dom_part not in cur_node._sub_tree:
                new_node = domain_tree_node(
                    name=dom_part,
                    parent=cur_node,
                    node_postfix="",
                    full_name="{}.{}".format(dom_part, cur_node.full_name),
                    intermediate=False,
                    depth=cur_node.depth + 1
                )
                new_node.save()
                self.__node_dict[new_node.pk] = new_node
                cur_node._sub_tree.setdefault(dom_part, []).append(new_node)
                new_node._sub_tree = {}
            # add to the first entry in sub_tree
            cur_node = cur_node._sub_tree[dom_part][0]
        return cur_node

    def get_domain_tree_node(self, dom_name):
        return self.__domain_lut[dom_name]

    def get_sorted_pks(self):
        return self._root_node.get_sorted_pks()

    def __getitem__(self, key):
        if type(key) in [int, int]:
            return self.__node_dict[key]

    def keys(self):
        return list(self.__node_dict.keys())

    def __iter__(self):
        return self.all()

    def all(self):
        # emulate queryset
        for pk in self.get_sorted_pks():
            yield self[pk]


# domain name models
class domain_tree_node(models.Model):
    idx = models.AutoField(primary_key=True)
    # the top node has no name
    name = models.CharField(max_length=64, default="")
    # full_name, gets computed on structure change
    full_name = models.CharField(max_length=256, default="", blank=True)
    # the top node has no parent
    parent = models.ForeignKey("self", null=True)
    # postfix to add to device name
    node_postfix = models.CharField(max_length=16, default="", blank=True)
    # depth information, top_node has idx=0
    depth = models.IntegerField(default=0)
    # intermediate node (no IPs allowed)
    intermediate = models.BooleanField(default=False)
    # creation timestamp
    created = models.DateTimeField(auto_now_add=True)
    # create short_names entry for /etc/hosts
    create_short_names = models.BooleanField(default=True)
    # create entry for clusternodes even when network not in list
    always_create_ip = models.BooleanField(default=False)
    # use for nameserver config
    write_nameserver_config = models.BooleanField(default=False)
    # comment
    comment = models.CharField(max_length=256, default="", blank=True)

    def get_sorted_pks(self):
        return [self.pk] + sum(
            [
                pk_list for _sub_name, pk_list in sorted(
                    [
                        (
                            key,
                            sum(
                                [
                                    sub_value.get_sorted_pks() for sub_value in value
                                ],
                                []
                            )
                        ) for key, value in self._sub_tree.items()
                    ]
                )
            ],
            []
        )

    def __unicode__(self):
        if self.depth:
            return self.full_name
            # if self.depth > 2:
            #    return u"%s%s%s (%s)" % (r"| " * (self.depth - 1), r"+-", self.name, self.full_name)
            # else:
            #    return u"%s%s (%s)" % (r"+-" * (self.depth), self.name, self.full_name)
        else:
            return "[TLN]"


@receiver(signals.pre_save, sender=domain_tree_node)
def domain_tree_node_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        device = apps.get_model("backbone", "device")
        net_ip = apps.get_model("backbone", "net_ip")
        cur_inst = kwargs["instance"]
        cur_inst.name = cur_inst.name.strip()
        if cur_inst.name and cur_inst.name.count("."):
            parts = list(reversed(cur_inst.name.split(".")))
            cur_parent = cur_inst.parent
            for cur_part in parts[:-1]:
                try:
                    _parent = domain_tree_node.objects.get(Q(name=cur_part) & Q(parent=cur_parent))
                except domain_tree_node.DoesNotExist:
                    try:
                        _parent = domain_tree_node(
                            name=cur_part,
                            parent=cur_parent,
                            create_short_names=cur_inst.create_short_names,
                            always_create_ip=cur_inst.always_create_ip,
                            write_nameserver_config=cur_inst.write_nameserver_config,
                            comment="autocreated intermediate",
                            node_postfix="",
                        )
                        _parent.save()
                    except:
                        raise ValidationError("cannot create parent: {}".format(process_tools.get_except_info()))
                cur_parent = _parent
            cur_inst.parent = cur_parent
            cur_inst.name = parts[-1]
        if cur_inst.parent_id:
            if cur_inst.pk:
                # check for valid parent
                all_parents = {_v[0]: _v[1] for _v in domain_tree_node.objects.all().values_list("idx", "parent")}
                cur_p_id = cur_inst.parent_id
                while cur_p_id:
                    if cur_p_id == cur_inst.pk:
                        raise ValidationError("parent node is child of node")
                    cur_p_id = all_parents[cur_p_id]
            cur_inst.depth = cur_inst.parent.depth + 1
        if cur_inst.depth and not valid_domain_re.match(cur_inst.name):
            raise ValidationError("illegal characters in name '{}'".format(cur_inst.name))
        if cur_inst.intermediate:
            if net_ip.objects.filter(Q(domain_tree_node=cur_inst)).count() + device.objects.filter(Q(domain_tree_node=cur_inst)).count():
                cur_inst.intermediate = False
                # raise ValidationError("cannot set used domain_tree_node as intermediate")
        cur_inst.node_postfix = cur_inst.node_postfix.strip()
        if not cur_inst.node_postfix and valid_domain_re.match(cur_inst.node_postfix):
            raise ValidationError("illegal characters in node postfix '{}'".format(cur_inst.node_postfix))
        if cur_inst.depth:
            check_empty_string(cur_inst, "name")
            parent_node = cur_inst.parent
            new_full_name = "{}{}".format(
                cur_inst.name,
                ".{}".format(parent_node.full_name) if parent_node.full_name else "",
            )
            cur_inst.depth = parent_node.depth + 1
            if new_full_name != cur_inst.full_name:
                cur_inst.full_name = new_full_name
                cur_inst.full_name_changed = True
            used_names = domain_tree_node.objects.exclude(
                Q(pk=cur_inst.pk)
            ).filter(
                Q(depth=cur_inst.depth) & Q(parent=cur_inst.parent)
            ).values_list("name", flat=True)
            if cur_inst.name in used_names:
                raise ValidationError("DTN-name '{}' already used here".format(cur_inst.name))
        else:
            check_non_empty_string(cur_inst, "name")
            check_non_empty_string(cur_inst, "node_postfix")


@receiver(signals.post_save, sender=domain_tree_node)
def domain_tree_node_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if getattr(cur_inst, "full_name_changed", False):
            for sub_node in domain_tree_node.objects.filter(Q(parent=cur_inst)):
                sub_node.save()


def _migrate_location_type(cat_tree):
    try:
        device_location = apps.get_model("backbone", "device_location")
    except LookupError:
        pass
    else:
        device = apps.get_model("backbone", "device")
        # just to be sure ...
        if device_location and device:
            # read all monitoring_config_types
            all_loc_ct = {
                pk: "/{}/{}".format(
                    TOP_LOCATION_CATEGORY,
                    cur_name
                ) for pk, cur_name in device_location.objects.all().values_list("pk", "location")
            }
            mig_dict = {
                key: cat_tree.add_category(value) for key, value in all_loc_ct.items()
            }
            for cur_dev in device.objects.all():
                if cur_dev.device_location_id:
                    cur_dev.categories.add(mig_dict[cur_dev.device_location_id])
                    cur_dev.device_location = None
                    cur_dev.save()


class category_tree(object):
    # helper structure
    def __init__(self, **kwargs):
        self.with_ref_count = kwargs.get("with_ref_count", False)
        self.with_refs = kwargs.get("with_res", False)
        self.__node_dict = {}
        self.__category_lut = {}
        if not category.objects.all().count():
            category(name="", full_name="", comment="top node").save()
        if self.with_ref_count or self.with_refs:
            _sql = category.objects.all().prefetch_related(
                "device_set",
                "config_set",
                "mon_check_command_set",
                "deviceselection_set"
            )
        else:
            _sql = category.objects.all()

        for cur_node in _sql.order_by("depth"):
            # if self.with_device_count or self.with_devices:
            #    cur_node.device_count = cur_node.device_set.count() + cur_node.config_set.count() + cur_node.mon_check_command_set.count()
            self.__node_dict[cur_node.pk] = cur_node
            self.__category_lut.setdefault(cur_node.full_name, []).append(cur_node)
            cur_node._sub_tree = {}
            if cur_node.parent_id is None:
                self._root_node = cur_node
            else:
                if cur_node.parent_id not in self.__node_dict:
                    # should not happen, damaged tree
                    del self.__node_dict[cur_node.pk]
                    try:
                        cur_node.delete()
                    except:
                        pass
                else:
                    if cur_node.parent_id == cur_node.pk:
                        # self reference, damaged tree, delete node
                        del self.__node_dict[cur_node.pk]
                        try:
                            cur_node.delete()
                        except:
                            pass
                    else:
                        if cur_node.depth - 1 != self.__node_dict[cur_node.parent_id].depth:
                            # fix depth
                            cur_node.depth = self.__node_dict[cur_node.parent_id].depth + 1
                            cur_node.save()
                        self.__node_dict[cur_node.parent_id]._sub_tree.setdefault(cur_node.name, []).append(cur_node)
        if TOP_LOCATION_CATEGORY not in self.__category_lut:
            _migrate_location_type(self)
        for check_name in TREE_SUBTYPES:
            _tree_name = "/{}".format(check_name)
            if _tree_name not in self.__category_lut:
                self.add_category(_tree_name)
        for cur_node in self.__node_dict.values():
            is_immutable = cur_node.full_name in [
                "",
            ] + ["/{}".format(_entry) for _entry in TREE_SUBTYPES]
            if cur_node.immutable != is_immutable:
                cur_node.immutable = is_immutable
                cur_node.save()

    def add_category(self, new_category_name):
        while new_category_name.startswith("/"):
            new_category_name = new_category_name[1:]
        while new_category_name.endswith("/"):
            new_category_name = new_category_name[:-1]
        while new_category_name.count("//"):
            new_category_name = new_category_name.replace("//", "/")
        cat_parts = list(new_category_name.split("/"))
        cur_node = self._root_node
        for _part_num, cat_part in enumerate(cat_parts):
            # part_num == len(cat_parts) - 1
            if cat_part not in cur_node._sub_tree:
                new_node = category(
                    name=cat_part,
                    parent=cur_node,
                    full_name="{}/{}".format(cur_node.full_name, cat_part),
                    depth=cur_node.depth + 1
                )
                new_node.save()
                self.__node_dict[new_node.pk] = new_node
                cur_node._sub_tree.setdefault(cat_part, []).append(new_node)
                new_node._sub_tree = {}
            # add to the first entry in sub_tree
            cur_node = cur_node._sub_tree[cat_part][0]
        return cur_node

    def get_category(self, cat_name):
        return self.__category_lut[cat_name]

    def get_sorted_pks(self):
        return self._root_node.get_sorted_pks()

    def __contains__(self, key):
        if type(key) in [int, int]:
            return key in self.__node_dict
        else:
            return key in self.__category_lut

    def __getitem__(self, key):
        if type(key) in [int, int]:
            return self.__node_dict[key]

    def keys(self):
        return list(self.__node_dict.keys())

    def prune(self, mode=None, doit=False):
        # removes all unreferenced nodes
        assert mode in [None, 'mon', 'device', 'location', 'config']

        removed = True
        # set of already deleted leafs
        _deleted = set()
        while removed:
            removed = False
            del_nodes = []
            for cur_leaf in self.__node_dict.values():
                if cur_leaf not in _deleted:
                    if mode is None or cur_leaf.full_name.startswith("/{}".format(mode)):
                        if not cur_leaf.immutable:
                            # count related models (with m2m)
                            if not get_related_models(cur_leaf, m2m=True, ignore_objs=_deleted):
                                del_nodes.append(cur_leaf)
            for del_node in del_nodes:
                # store idx in an extra field
                del_node.saved_pk = del_node.idx
                _deleted.add(del_node)
                if doit:
                    del self[del_node.parent_id]._sub_tree[del_node.name]
                    del self.__node_dict[del_node.pk]
                    del_node.delete()
            removed = len(del_nodes) > 0
        return _deleted

    def __iter__(self):
        return self.all()

    def all(self):
        # emulate queryset
        for pk in self.get_sorted_pks():
            yield self[pk]


class CategoryManager(models.Manager):

    def get_device_categories(self):
        return self.filter(full_name__startswith="/device/")

    def get_monitoring_categories(self):
        return self.filter(full_name__startswith="/mon/")


class category(models.Model):

    objects = CategoryManager()

    idx = models.AutoField(primary_key=True)
    # the top node has no name
    name = models.CharField(max_length=64, default="")
    # full_name, gets computed on structure change
    full_name = models.TextField(default="", blank=True)
    # the top node has no parent
    parent = models.ForeignKey("self", null=True)
    # depth information, top_node has idx=0
    depth = models.IntegerField(default=0)
    # creation timestamp
    created = models.DateTimeField(auto_now_add=True)
    # immutable
    immutable = models.BooleanField(default=False)
    # useable flag, False for intermediate entries
    useable = models.BooleanField(default=True)
    # for location fields: physical or structural (for overview location maps)
    # a device can be used on a structural (non-physical) loction map even if
    # this location map is not attached to the location node the devices is attached to
    physical = models.BooleanField(default=True)
    # location field for location nodes, defaults to Vienna (approx)
    latitude = models.FloatField(default=48.1)
    longitude = models.FloatField(default=16.3)
    # locked field, only valid (right now) for locations
    locked = models.BooleanField(default=False)
    # used for asset categorisation
    asset = models.BooleanField(default=False)
    # comment
    comment = models.CharField(max_length=256, default="", blank=True)

    def get_sorted_pks(self):
        return [self.pk] + sum(
            [
                pk_list for _sub_name, pk_list in sorted(
                    [
                        (
                            key,
                            sum(
                                [
                                    sub_value.get_sorted_pks() for sub_value in value
                                ],
                                []
                            )
                        ) for key, value in self._sub_tree.items()
                    ]
                )
            ],
            []
        )

    def __unicode__(self):
        return "{}".format(self.full_name if self.depth else "[TLN]")

    @property
    def single_select(self):
        return True if (self.full_name.startswith("/location/") and self.physical) else False

    def get_ref_object(self):
        from initat.cluster.backbone.models import device, config, mon_check_command
        if self.depth:
            _tl = self.full_name.split("/")[1]
            return {
                "config": config,
                "device": device,
                "location": device,
                "mon": mon_check_command,
            }[_tl]
        else:
            return None

    def build_full_name(self):
        _list = [self.name]
        _p = self.parent
        while _p:
            _list.insert(0, _p.name)
            _p = _p.parent
        self.full_name = "/".join(_list)

    # no longer needed
    # def get_reference_dict(self):
    #    all_m2ms = [
    #        _f for _f in self._meta.get_fields(include_hidden=True) if _f.many_to_many and _f.auto_created
    #    ]
    #    _names = [_f.name for _f in all_m2ms]
    #    _required = {"config", "mon_check_command", "deviceselection", "device"}
    #    if set(_names) != _required:
    #        raise ValidationError("Related fields for category_tree changed")
    #    ref_dict = {}
    #    for rel in all_m2ms:
    #        if rel.name == "device":
    #            # print getattr(self, rel.get_accessor_name()).count()
    #            # print getattr(self, rel.get_accessor_name()).all()
    #            ref_dict[rel.name] = getattr(self, rel.get_accessor_name()).values_list("pk", flat=True)
    #        else:
    #            ref_dict[rel.name] = getattr(self, rel.get_accessor_name()).count()
    #    # print self.device.get_accessor_name().values_list("device")
    #    # print ref_dict
    #    return ref_dict

    class Meta:
        verbose_name = "Category"
        unique_together = [("name", "parent"), ]


@receiver(signals.post_init, sender=category)
def category_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.depth:
            _tl = cur_inst.full_name.split("/")[1]
            if _tl not in TREE_SUBTYPES:
                cur_inst.build_full_name()
                cur_inst.save()


@receiver(signals.pre_save, sender=category)
def category_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.name = cur_inst.name.strip()
        check_float(cur_inst, "latitude")
        check_float(cur_inst, "longitude")
        if cur_inst.name and cur_inst.name.count("/"):
            parts = [entry for entry in cur_inst.name.split("/") if entry.strip()]
            cur_parent = cur_inst.parent
            for cur_part in parts[:-1]:
                try:
                    _parent = category.objects.get(Q(name=cur_part) & Q(parent=cur_parent))
                except category.DoesNotExist:
                    try:
                        _parent = category(
                            name=cur_part,
                            parent=cur_parent,
                            useable=False,
                            comment="autocreated intermediate",
                        )
                        _parent.save()
                    except:
                        raise ValidationError("cannot create parent: {}".format(process_tools.get_except_info()))
                cur_parent = _parent
            cur_inst.parent = cur_parent
            cur_inst.name = parts[-1]
        if cur_inst.parent_id:
            if cur_inst.pk:
                # check for valid parent
                all_parents = {
                    _v[0]: _v[1] for _v in category.objects.all().values_list("idx", "parent")
                }
                cur_p_id = cur_inst.parent_id
                while cur_p_id:
                    if cur_p_id == cur_inst.pk:
                        raise ValidationError("parent node is child of node")
                    cur_p_id = all_parents[cur_p_id]
            cur_inst.depth = cur_inst.parent.depth + 1
        if cur_inst.depth and not valid_category_re.match(cur_inst.name):
            raise ValidationError("illegal characters in name '{}'".format(cur_inst.name))
        if cur_inst.depth:
            if cur_inst.depth == 1:
                if cur_inst.name not in TREE_SUBTYPES:
                    raise ValidationError("illegal top-level category name '{}'".format(cur_inst.name))
            check_empty_string(cur_inst, "name")
            parent_node = cur_inst.parent
            new_full_name = "{}/{}".format(
                parent_node.full_name,
                cur_inst.name,
            )
            cur_inst.depth = parent_node.depth + 1
            if new_full_name != cur_inst.full_name:
                cur_inst.full_name = new_full_name
                cur_inst.full_name_changed = True
            # get top level cat
            top_level_cat = cur_inst.full_name.split("/")[1]
            if cur_inst.asset and top_level_cat != TOP_DEVICE_CATEGORY:
                raise ValidationError("Asset flag only allowed for devicecategory '{}'".format(cur_inst.full_name))
            # check for used named
            used_names = category.objects.exclude(
                Q(pk=cur_inst.pk)
            ).filter(
                Q(depth=cur_inst.depth) & Q(parent=cur_inst.parent)
            ).values_list("name", flat=True)
            if cur_inst.name in used_names:
                raise ValidationError("category name '{}' already used here".format(cur_inst.name))
        else:
            check_non_empty_string(cur_inst, "name")


@receiver(signals.post_save, sender=category)
def category_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if getattr(cur_inst, "full_name_changed", False):
            for sub_node in category.objects.filter(Q(parent=cur_inst)):
                sub_node.save()


# category
class location_gfx(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="", unique=True)
    image_name = models.CharField(max_length=64, default="", blank=True)
    # uuid of graph
    uuid = models.CharField(max_length=64, blank=True)
    # image stored ?
    image_stored = models.BooleanField(default=False)
    # image count, to make urls unique
    image_count = models.IntegerField(default=1)
    # size
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    # content type
    content_type = models.CharField(default="", max_length=128, blank=True)
    # creation date
    created = models.DateTimeField(auto_now_add=True)
    # location node
    location = models.ForeignKey("backbone.category")
    # locked (as soon as a graphic is set)
    locked = models.BooleanField(default=False)
    # changes
    changes = models.IntegerField(default=0)
    # comment
    comment = models.TextField(default="", blank=True)

    def get_icon_url(self):
        if self.image_stored:
            return reverse("base:location_gfx_icon", args=[self.idx, self.image_count])
        else:
            return ""

    def get_image_url(self):
        if self.image_stored:
            return reverse("base:location_gfx_image", args=[self.idx, self.image_count])
        else:
            return ""

    @property
    def icon_cache_key(self):
        return "lgfx_icon_{}".format(self.uuid)

    def get_icon(self):
        _content = cache.get(self.icon_cache_key)
        if _content is None:
            _entry = os.path.join(settings.ICSW_WEBCACHE, "lgfx", self.uuid)
            if os.path.isfile(_entry):
                _img = Image.open(file(_entry, "rb"))
                _img.thumbnail((24, 24))
                _content = io.StringIO()
                _img.save(_content, format="JPEG")
                _content = _content.getvalue()
                cache.set(self.icon_cache_key, _content)
                return _content
            else:
                return location_gfx.default_icon()
        else:
            return _content

    def get_image(self):
        _entry = self.image_file_name
        if os.path.isfile(_entry):
            return file(_entry, "rb").read()
        else:
            return location_gfx.default_image()

    @staticmethod
    def default_icon():
        _content = io.StringIO()
        Image.new("RGB", (24, 24), color="red").save(_content, format="JPEG")
        return _content.getvalue()

    @staticmethod
    def default_image():
        _content = io.StringIO()
        Image.new("RGB", (640, 400), color="red").save(_content, format="JPEG")
        return _content.getvalue()

    def _read_image(self):
        # returns an _img object and stores for undo
        _img = Image.open(file(self.image_file_name, "rb"))
        _img.save(file(self.image_file_name_last, "wb"), format="PNG")
        return _img

    def resize(self, factor):
        _img = self._read_image()
        _img = _img.resize((int(_img.size[0] * factor), int(_img.size[1] * factor)), Image.BICUBIC)
        self.store_graphic(_img, self.content_type, self.image_name)

    def rotate(self, degrees):
        _img = self._read_image().rotate(degrees)
        self.store_graphic(_img, self.content_type, self.image_name)

    def brightness(self, factor):
        _img = ImageEnhance.Brightness(self._read_image()).enhance(factor)
        self.store_graphic(_img, self.content_type, self.image_name)

    def sharpen(self, factor):
        _img = ImageEnhance.Sharpness(self._read_image()).enhance(factor)
        self.store_graphic(_img, self.content_type, self.image_name)

    def apply_filter(self, filter_name):
        try:
            _filter = getattr(ImageFilter, filter_name)
        except:
            pass
        else:
            _img = self._read_image().filter(_filter)
            self.store_graphic(_img, self.content_type, self.image_name)

    def restore_original_image(self):
        if os.path.exists(self.image_file_name_orig):
            _img = Image.open(file(self.image_file_name_orig, "rb"))
            self.store_graphic(_img, self.content_type, self.image_name)

    def undo_last_step(self):
        if os.path.exists(self.image_file_name_last):
            _img = Image.open(file(self.image_file_name_last, "rb"))
            self.store_graphic(_img, self.content_type, self.image_name)

    @property
    def image_file_name(self):
        return os.path.join(
            settings.ICSW_WEBCACHE,
            "lgfx",
            self.uuid,
        )

    @property
    def image_file_name_orig(self):
        return os.path.join(
            settings.ICSW_WEBCACHE,
            "lgfx",
            "{}.orig".format(self.uuid),
        )

    @property
    def image_file_name_last(self):
        return os.path.join(
            settings.ICSW_WEBCACHE,
            "lgfx",
            "{}.last".format(self.uuid),
        )

    def store_graphic(self, img, content_type, file_name):
        self.changes += 1
        _entry = self.image_file_name
        _gfx_dir = os.path.dirname(_entry)
        if not os.path.isdir(_gfx_dir):
            os.mkdir(_gfx_dir)
        img.save(file(_entry, "wb"), format="PNG")
        if self.changes == 1:
            # first change, store original image
            img.save(file(self.image_file_name_orig, "wb"), format="PNG")
        self.image_name = file_name
        self.width = img.size[0]
        self.height = img.size[1]
        self.image_count += 1
        self.content_type = content_type
        self.image_stored = True
        self.locked = True
        if cache.get(self.icon_cache_key):
            cache.delete(self.icon_cache_key)
        self.save(
            update_fields=[
                "changes", "width", "height",
                "content_type",
                "locked", "image_stored", "image_count", "image_name"
            ]
        )


@receiver(signals.pre_save, sender=location_gfx)
def location_gfx_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.uuid:
            cur_inst.uuid = uuid.uuid4()


class device_mon_location(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to device
    device = models.ForeignKey("backbone.device")
    # link to location_gfx
    location_gfx = models.ForeignKey("backbone.location_gfx")
    # link to location node
    location = models.ForeignKey("backbone.category")

    # position in graph
    pos_x = models.IntegerField(default=0)
    pos_y = models.IntegerField(default=0)
    # locked (as soon as a graphic is set)
    locked = models.BooleanField(default=False)
    # comment
    comment = models.TextField(default="", blank=True)
    # creation date
    created = models.DateTimeField(auto_now_add=True)

    # def get_device_name(self):
    #    return self.device.full_name

    class Meta:
        verbose_name = "Monitoring location"


@receiver(signals.pre_save, sender=device_mon_location)
def device_mon_location_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.pk:
            try:
                _present = device_mon_location.objects.get(Q(device=cur_inst.device) & Q(location=cur_inst.location) & Q(location_gfx=cur_inst.location_gfx))
            except device_mon_location.DoesNotExist:
                pass
            else:
                raise ValidationError


class DomainTypeEnum(models.Model):
    # domain types (present: mother (for boot), monitor (for mon dist))
    idx = models.AutoField(primary_key=True)
    enum_name = models.CharField(max_length=255, default="", unique=True)
    name = models.CharField(max_length=255, default="", unique=True)
    info = models.TextField(default="", blank=True)
    # default enum (for all devices without a set domain, for instance monitoring [==monitor-server])
    default_enum = models.ForeignKey("backbone.configserviceenum", related_name="dte_default", null=True)
    # enum required for defined domains (== boot)
    domain_enum = models.ForeignKey("backbone.configserviceenum", related_name="dte_domain", null=True)
    # creation date
    created = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def create_db_entry(domain_enum):
        from initat.cluster.backbone.models import ConfigServiceEnum
        _dict = {}
        for _type in {"default", "domain"}:
            _val = getattr(domain_enum.value, "{}_enum".format(_type))
            if _val is not None:
                _dict[_type] = ConfigServiceEnum.objects.get(Q(enum_name=_val.name))
            else:
                _dict[_type] = None
        _new_entry = DomainTypeEnum.objects.create(
            enum_name=domain_enum.name,
            name=domain_enum.value.name,
            info=domain_enum.value.info,
            default_enum=_dict["default"],
            domain_enum=_dict["domain"],
        )
        return _new_entry


class DistributedService(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to enum
    domaintypeenum = models.OneToOneField("backbone.domaintypeenum")
    # name
    name = models.CharField(max_length=128, default="Default domain", unique=True)
    # creation date
    created = models.DateTimeField(auto_now_add=True)


class DistributedServiceNode(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to domaindefinition
    domaindefinition = models.ForeignKey("backbone.distributedservice")
    # domain config
    device_config = models.ForeignKey("backbone.device_config")
    # node type (default or domain, only one or none default allowed)
    is_domain_node = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
