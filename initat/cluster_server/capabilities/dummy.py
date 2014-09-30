# Copyright (C) 2001-2014 Andreas Lang-Nevyjel
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
""" cluster-server """

from initat.cluster_server.background.base import bg_stuff
from initat.host_monitoring import hm_classes
import time


class dummy_stuff(bg_stuff):
    class Meta:
        name = "dummy"

    def init_bg_stuff(self):
        self.load_value = hm_classes.mvect_entry("sys.load1", info="test entry", default=0.0)

    def _call(self, cur_time, builder):
        self.load_value.update(float(file("/proc/loadavg", "r").read().split()[0]))
        self.load_value.valid_until = time.time() + 10
        my_vector = builder("values")
        my_vector.append(self.load_value.build_xml(builder))
        return my_vector
