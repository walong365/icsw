#!/usr/bin/python-init


from PIL import Image, ImageEnhance, ImageFilter
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
import StringIO
import os
from initat.tools import process_tools
import re
import uuid

__all__ = [
    "domain_tree_node",
    "category",
    "location_gfx",
    "device_mon_location",
]


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

    class Meta:
        app_label = "backbone"


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
    # for location fields: physical or structural (for overview location maps)
    # a device can be used on a structural (non-physical) loction map even if
    # this location map is not attached to the location node the devices is attached to
    physical = models.BooleanField(default=True)
    # location field for location nodes, defaults to Vienna (approx)
    latitude = models.FloatField(default=48.1)
    longitude = models.FloatField(default=16.3)
    # locked field, only valid (right now) for locations
    locked = models.BooleanField(default=False)
    # comment
    comment = models.CharField(max_length=256, default="", blank=True)

    class Meta:
        app_label = "backbone"


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
    comment = models.CharField(max_length=1024, default="", blank=True)

    class Meta:
        app_label = "backbone"


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
    comment = models.CharField(max_length=1024, default="", blank=True)
    # creation date
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
        verbose_name = "Monitoring location"
