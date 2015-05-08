# Copyright (C) 2015 Bernhard Mallinger
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
from initat.cluster_server.license_checker import LicenseChecker

from initat.cluster_server.modules import cs_base_class


class check_license_violations(cs_base_class.server_com):
    def _call(self, cur_inst):
        LicenseChecker.check(cur_inst.log)
        cur_inst.srv_com.set_result("finished checking license")  # this is ignored
