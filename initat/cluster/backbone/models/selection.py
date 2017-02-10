# Copyright (C) 2015,2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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
""" selection models for NOCTUA, CORVUS and NESTOR """



from django.db import models
from django.db.models import Q


__all__ = [
    "DeviceSelection",
]


class DeviceSelection(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="")
    user = models.ForeignKey("user")
    # link to devices
    devices = models.ManyToManyField("device", blank=True)
    # lazy device_groups
    device_groups = models.ManyToManyField("device_group", blank=True)
    # lazy categories
    categories = models.ManyToManyField("category", blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def resolve(self):
        # return a list of all effectively selectded devices
        return list(
            self.devices.all()
        ) + sum(
            [
                list(_dev_group.device_group.filter(Q(is_meta_device=False))) for _dev_group in self.device_groups.all()
            ],
            []
        ) + sum(
            [
                list(_cat.device_set.filter(Q(is_metadevice=False))) for _cat in self.categories.all()
            ],
            []
        )

    def __str__(self):
        return "Selection '{}' for user {}".format(
            self.name,
            str(self.user),
        )

    class Meta:
        ordering = ("-date",)
