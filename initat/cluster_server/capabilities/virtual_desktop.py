# Copyright (C) 2014 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
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
""" virtual desktop capability """

from django.db.models import Q
from initat.cluster_server.capabilities.base import bg_stuff
from initat.cluster_server.config import global_config
from initat.cluster.backbone.models import virtual_desktop_protocols, window_managers, device
import process_tools


class virtual_desktop_stuff(bg_stuff):
    class Meta:
        name = "virtual_desktop"

    def init_bg_stuff(self):
        self.__effective_device = device.objects.get(Q(pk=global_config["EFFECTIVE_DEVICE_IDX"]))

    def _call(self, cur_time, builder):
        for vd_proto in virtual_desktop_protocols.objects.all():
            _vd_update = False
            available = process_tools.find_file(vd_proto.binary)
            if vd_proto.devices.filter(pk=self.__effective_device.pk):
                if not available:
                    _vd_update = True
                    vd_proto.devices.remove(self.__effective_device)
                    self.log("removing virtual desktop proto {} from {}".format(vd_proto.name, self.__effective_device.name))
            else:
                if available:
                    _vd_update = True
                    vd_proto.devices.add(self.__effective_device)
                    self.log("adding virtual desktop proto {} to {}".format(vd_proto.name, self.__effective_device.name))

            if _vd_update:
                vd_proto.save()

        for wm in window_managers.objects.all():
            _wm_update = False
            available = process_tools.find_file(wm.binary)
            if wm.devices.filter(pk=self.__effective_device.pk):
                if not available:
                    _wm_update = True
                    wm.devices.remove(self.__effective_device)
                    self.log("removing window  manager {} from {}".format(wm.name, self.__effective_device.name))
            else:
                if available:
                    _wm_update = True
                    wm.devices.add(self.__effective_device)
                    self.log("adding window manager {} to {}".format(wm.name, self.__effective_device.name))

            if _wm_update:
                wm.save()
