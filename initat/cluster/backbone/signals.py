#!/usr/bin/python-init
#
# Send feedback to: <lang-nevyjel@init.at>
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

import django.dispatch

__all__ = [
    "user_changed",
    "group_changed",
    "bootsettings_changed",
    "virtual_desktop_user_setting_changed",
    "SensorThresholdChanged",
]

user_changed = django.dispatch.Signal(providing_args=["user", "cause"])
group_changed = django.dispatch.Signal(providing_args=["group", "cause"])
# fired when the bootsettings of a device changes
bootsettings_changed = django.dispatch.Signal(providing_args=["device", "cause"])
virtual_desktop_user_setting_changed = django.dispatch.Signal(providing_args=["vdus", "cause"])
SensorThresholdChanged = django.dispatch.Signal(providing_args=["sensor_threshold", "cause"])
