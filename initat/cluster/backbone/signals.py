#!/usr/bin/python-init

import django.dispatch

__all__ = [
    "user_changed",
    "group_changed",
    "bootsettings_changed",
    "virtual_desktop_user_setting_changed",
]

user_changed = django.dispatch.Signal(providing_args=["user", "cause"])
group_changed = django.dispatch.Signal(providing_args=["group", "cause"])
# fired when the bootsettings of a device changes
bootsettings_changed = django.dispatch.Signal(providing_args=["device", "cause"])

virtual_desktop_user_setting_changed = django.dispatch.Signal(providing_args=["vdus", "cause"])
