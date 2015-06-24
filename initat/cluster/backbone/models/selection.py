# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
""" selection models for NOCTUA, CORVUS and NESTOR """

from django.db import models

__all__ = [
    "DeviceSelection",
]


class DeviceSelection(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="")
    user = models.ForeignKey("user")
    # link to devices
    devices = models.ManyToManyField("device")
    # lazy device_groups
    device_groups = models.ManyToManyField("device_group")
    # lazy categories
    categories = models.ManyToManyField("category")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"Selection '{}' for user {}".format(
            self.name,
            unicode(self.user),
        )

    class Meta:
        ordering = ("-date",)
