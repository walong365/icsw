#!/usr/bin/python3-init -Ot
#
# Copyright (C) 2015,2017 Bernhard Mallinger, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <mallinger@init.at>
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

from factory import DjangoModelFactory, Sequence, SubFactory
from initat.cluster.backbone.models import device, device_group


class DeviceGroupTestFactory(DjangoModelFactory):
    class Meta:
        model = device_group

    name = Sequence(lambda n: 'test_device_group_{}'.format(n))


class DeviceTestFactory(DjangoModelFactory):
    class Meta:
        model = device

    name = Sequence(lambda n: 'test_device_{}'.format(n))
    device_group = SubFactory(DeviceGroupTestFactory)
