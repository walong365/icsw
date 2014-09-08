#!/usr/bin/python-init

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, _check_non_empty_string, \
    _check_float, get_related_models
import process_tools
import re
import uuid

__all__ = [
    "domain_name_tree", "valid_domain_re",
    "domain_tree_node",
    "category_tree",
    "category",
    "TOP_LOCATIONS",
    "TOP_MONITORING_CATEGORY",
    "location_gfx",
]

# top monitoring category
TOP_MONITORING_CATEGORY = "/mon"
TOP_LOCATION_CATEGORY = "/location"
TOP_CONFIG_CATEGORY = "/config"
TOP_DEVICE_CATEGORY = "/device"

TOP_LOCATIONS = set([
    TOP_MONITORING_CATEGORY,
    TOP_LOCATION_CATEGORY,
    TOP_CONFIG_CATEGORY,
    TOP_DEVICE_CATEGORY,
])

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
        for cur_tn in self.__node_dict.itervalues():
            is_im = cur_tn.pk not in used_pks
            if cur_tn.intermediate != is_im:
                cur_tn.intermediate = is_im
                cur_tn.save()

    def add_device_references(self):
        device = apps.get_model("backbone", "device")
        used_dtn_pks = list(device.objects.filter(Q(enabled=True) & Q(device_group__enabled=True)).values_list("domain_tree_node_id", flat=True))
        used_dict = {key: used_dtn_pks.count(key) for key in set(used_dtn_pks)}
        for value in self.__node_dict.itervalues():
            value.local_refcount = used_dict.get(value.pk, 0)
        for value in self.__node_dict.itervalues():
            value.total_refcount = self._get_sub_refcounts(value)

    def _get_sub_refcounts(self, s_node):
        return self.__node_dict[s_node.pk].local_refcount + sum([self._get_sub_refcounts(sub_node) for sub_node in sum(s_node._sub_tree.itervalues(), [])])

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
                    depth=cur_node.depth + 1)
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
        if type(key) in [int, long]:
            return self.__node_dict[key]

    def keys(self):
        return self.__node_dict.keys()

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
                        ) for key, value in self._sub_tree.iteritems()
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
            return u"[TLN]"

    class Meta:
        app_label = "backbone"


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
                # print "***", unicode(cur_inst)
                raise ValidationError("cannot set used domain_tree_node as intermediate")
        cur_inst.node_postfix = cur_inst.node_postfix.strip()
        if not cur_inst.node_postfix and valid_domain_re.match(cur_inst.node_postfix):
            raise ValidationError("illegal characters in node postfix '{}'".format(cur_inst.node_postfix))
        if cur_inst.depth:
            _check_empty_string(cur_inst, "name")
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
                raise ValidationError("name '{}' already used here".format(cur_inst.name))
        else:
            _check_non_empty_string(cur_inst, "name")
            _check_non_empty_string(cur_inst, "node_postfix")


@receiver(signals.post_save, sender=domain_tree_node)
def domain_tree_node_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if getattr(cur_inst, "full_name_changed", False):
            for sub_node in domain_tree_node.objects.filter(Q(parent=cur_inst)):
                sub_node.save()


def _migrate_mon_type(cat_tree):
    # read all monitoring_config_types
    mon_check_command = apps.get_model("backbone", "mon_check_command")
    mon_check_command_type = apps.get_model("backbone", "mon_check_command_type")
    cur_cats = set(mon_check_command.objects.all().values_list("categories", flat=True))
    if cur_cats == set([None]):
        all_mon_ct = {
            pk: "{}/{}".format(
                TOP_MONITORING_CATEGORY,
                cur_name
            ) for pk, cur_name in mon_check_command_type.objects.all().values_list("pk", "name")}
        mig_dict = {
            key: cat_tree.add_category(value) for key, value in all_mon_ct.iteritems()
        }
        for cur_mon_cc in mon_check_command.objects.all().prefetch_related("categories"):
            if cur_mon_cc.mon_check_command_type_id:
                cur_mon_cc.categories.add(mig_dict[cur_mon_cc.mon_check_command_type_id])
                cur_mon_cc.mon_check_command_type = None
                cur_mon_cc.save()


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
                pk: "{}/{}".format(
                    TOP_LOCATION_CATEGORY,
                    cur_name
                ) for pk, cur_name in device_location.objects.all().values_list("pk", "location")
            }
            mig_dict = {
                key: cat_tree.add_category(value) for key, value in all_loc_ct.iteritems()
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
            _sql = category.objects.all().prefetch_related("device_set", "config_set", "mon_check_command_set")
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
        if TOP_MONITORING_CATEGORY not in self.__category_lut:
            _migrate_mon_type(self)
        if TOP_LOCATION_CATEGORY not in self.__category_lut:
            _migrate_location_type(self)
        for check_name in [TOP_CONFIG_CATEGORY, TOP_DEVICE_CATEGORY, TOP_MONITORING_CATEGORY, TOP_LOCATION_CATEGORY]:
            if check_name not in self.__category_lut:
                self.add_category(check_name)
        for cur_node in self.__node_dict.itervalues():
            is_immutable = cur_node.full_name in ["", TOP_CONFIG_CATEGORY, TOP_MONITORING_CATEGORY, TOP_DEVICE_CATEGORY, TOP_LOCATION_CATEGORY]
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
                    depth=cur_node.depth + 1)
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
        if type(key) in [int, long]:
            return key in self.__node_dict
        else:
            return key in self.__category_lut

    def __getitem__(self, key):
        if type(key) in [int, long]:
            return self.__node_dict[key]

    def keys(self):
        return self.__node_dict.keys()

    def prune(self):
        # removes all unreferenced nodes
        removed = True
        while removed:
            removed = False
            del_nodes = []
            for cur_leaf in self.__node_dict.itervalues():
                if not cur_leaf._sub_tree and not cur_leaf.immutable:
                    # count related models (with m2m)
                    if not get_related_models(cur_leaf, m2m=True):
                        del_nodes.append(cur_leaf)
            for del_node in del_nodes:
                del self[del_node.parent_id]._sub_tree[del_node.name]
                del self.__node_dict[del_node.pk]
                del_node.delete()
            removed = len(del_nodes) > 0

    def __iter__(self):
        return self.all()

    def all(self):
        # emulate queryset
        for pk in self.get_sorted_pks():
            yield self[pk]


# category
class category(models.Model):
    idx = models.AutoField(primary_key=True)
    # the top node has no name
    name = models.CharField(max_length=64, default="")
    # full_name, gets computed on structure change
    full_name = models.CharField(max_length=1024, default="", blank=True)
    # the top node has no parent
    parent = models.ForeignKey("self", null=True)
    # depth information, top_node has idx=0
    depth = models.IntegerField(default=0)
    # creation timestamp
    created = models.DateTimeField(auto_now_add=True)
    # immutable
    immutable = models.BooleanField(default=False)
    # location field for location nodes, defaults to Vienna (approx)
    latitude = models.FloatField(default=48.1)
    longitude = models.FloatField(default=16.3)
    # locked field, only valid (right now) for locations
    locked = models.BooleanField(default=False)
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
                        ) for key, value in self._sub_tree.iteritems()
                    ]
                )
            ],
            []
        )

    def __unicode__(self):
        return u"{}".format(self.full_name if self.depth else "[TLN]")

    def single_select(self):
        return True if self.full_name.startswith("/location/") else False

    def get_references(self):
        # print "*", self, dir(self._meta)
        num_refs = 0
        for rel in self._meta.get_all_related_many_to_many_objects():
            # print dir(rel), rel.name
            # for entry in getattr(self, rel.get_accessor_name()).all():
            #    print entry
            num_refs += getattr(self, rel.get_accessor_name()).count()
        return num_refs

    class Meta:
        app_label = "backbone"


@receiver(signals.pre_save, sender=category)
def category_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.name = cur_inst.name.strip()
        _check_float(cur_inst, "latitude")
        _check_float(cur_inst, "longitude")
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
                all_parents = {_v[0]: _v[1] for _v in category.objects.all().values_list("idx", "parent")}
                cur_p_id = cur_inst.parent_id
                while cur_p_id:
                    if cur_p_id == cur_inst.pk:
                        raise ValidationError("parent node is child of node")
                    cur_p_id = all_parents[cur_p_id]
            cur_inst.depth = cur_inst.parent.depth + 1
        if cur_inst.depth and not valid_category_re.match(cur_inst.name):
            raise ValidationError("illegal characters in name '{}'".format(cur_inst.name))
        if cur_inst.depth:
            _check_empty_string(cur_inst, "name")
            parent_node = cur_inst.parent
            new_full_name = "{}/{}".format(
                parent_node.full_name,
                cur_inst.name,
            )
            cur_inst.depth = parent_node.depth + 1
            if new_full_name != cur_inst.full_name:
                cur_inst.full_name = new_full_name
                cur_inst.full_name_changed = True
            # check for used named
            used_names = category.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(depth=cur_inst.depth) & Q(parent=cur_inst.parent)).values_list("name", flat=True)
            if cur_inst.name in used_names:
                raise ValidationError("name '{}' already used here".format(cur_inst.name))
        else:
            _check_non_empty_string(cur_inst, "name")


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
    # the top node has no name
    name = models.CharField(max_length=64, default="", unique=True)
    # uuid of graph
    uuid = models.CharField(max_length=64, blank=True)
    # size
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    # content type
    content_type = models.CharField(default="", max_length=128)
    # creation date
    created = models.DateTimeField(auto_now_add=True)
    # location node
    location = models.ForeignKey("backbone.category")
    # comment
    comment = models.CharField(max_length=1024, default="", blank=True)

    class Meta:
        app_label = "backbone"


@receiver(signals.pre_save, sender=location_gfx)
def location_gfx_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.uuid:
            print "*", uuid.uuid4()
            cur_inst.uuid = uuid.uuid4()
