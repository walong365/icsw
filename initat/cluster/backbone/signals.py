#!/usr/bin/python-init

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals
import django.dispatch

__all__ = [
    "user_changed",
    "group_changed",
]

user_changed = django.dispatch.Signal(providing_args=["user", "cause"])
group_changed = django.dispatch.Signal(providing_args=["group", "cause"])
# fired when the bootsettings of a device changes
bootsettings_changed = django.dispatch.Signal(providing_args=["device", "cause"])
