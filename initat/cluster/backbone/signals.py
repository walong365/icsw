# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" signals for ICSW """

from __future__ import unicode_literals, print_function

import django.dispatch

__all__ = [
    b"UserChanged",
    b"GroupChanged",
    b"BootsettingsChanged",
    b"VirtualDesktopUserSettingChanged",
    b"SensorThresholdChanged",
    b"RoleChanged",
]

UserChanged = django.dispatch.Signal(providing_args=["user", "cause"])
GroupChanged = django.dispatch.Signal(providing_args=["group", "cause"])
RoleChanged = django.dispatch.Signal(providing_args=["role", "cause"])
# fired when the bootsettings of a device changes
BootsettingsChanged = django.dispatch.Signal(providing_args=["device", "cause"])
VirtualDesktopUserSettingChanged = django.dispatch.Signal(providing_args=["vdus", "cause"])
SensorThresholdChanged = django.dispatch.Signal(providing_args=["sensor_threshold", "cause"])
