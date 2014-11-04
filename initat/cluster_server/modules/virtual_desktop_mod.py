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
"""contains command for reloading/restarting the virtual desktop"""

from initat.cluster.backbone.models.user import virtual_desktop_user_setting
from initat.cluster_server.capabilities.virtual_desktop import virtual_desktop_server
from initat.cluster_server.modules import cs_base_class
from django.db.models.query_utils import Q


class reload_virtual_desktop(cs_base_class.server_com):
    def _call(self, cur_inst):
        '''
        :param com_instance cur_inst:
        '''
        vdus_pk = cur_inst.srv_com["*vdus"]
        cur_inst.log("restarting virtual desktop {}".format(vdus_pk))
        vdus = virtual_desktop_user_setting.objects.get(Q(pk=vdus_pk))

        control = virtual_desktop_server.get_instance_for_vdus(vdus, cur_inst.log)
        control.stop()
        if vdus.is_running:
            control.start()
