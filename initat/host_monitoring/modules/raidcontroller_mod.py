# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" checks for various RAID controllers """

from initat.host_monitoring import hm_classes

from initat.host_monitoring.modules.raidcontrollers import COMMAND_DICT
from initat.host_monitoring.modules.raidcontrollers.all import AllRAIDCtrl


# add commands to be included automatically
for _key, _value in COMMAND_DICT.iteritems():
    locals()[_key] = _value


class _general(hm_classes.hm_module):
    def init_module(self):
        AllRAIDCtrl.init(self)
