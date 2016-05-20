#
# Copyright (C) 2016 Gregor Kaufmann, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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

from django.db import models

class VmHost(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device", null=True)
    name = models.TextField(null=True)

class VmSubDevice(models.Model):
    idx = models.AutoField(primary_key=True)
    vm_host= models.ForeignKey("backbone.VmHost")
    name = models.TextField(null=True)

class VMDataStore(models.Model):
    idx = models.AutoField(primary_key=True)

    collection = models.ForeignKey("backbone.VMCollection")

    result = models.TextField(null=True)

    vm_sub_device = models.ForeignKey("backbone.VmSubDevice")


class VMCollection(models.Model):
    idx = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True)
