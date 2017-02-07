# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring / relay mixin """


from initat.constants import PLATFORM_SYSTEM_TYPE
from .constants import HMAccessClassEnum


class HMHRMixin(object):
    def COM_open(self, local_mc, verbose, enable_filter=False):
        self.local_mc = local_mc
        self.local_mc.set_log_command(self.log)
        if enable_filter:
            # read access level and platform
            _platform = PLATFORM_SYSTEM_TYPE
            _access_class = HMAccessClassEnum(self.CC.CS["hm.access_class"])
        else:
            _platform = None
            _access_class = None
        self.log(
            "command filtering is {}{}".format(
                "enabled" if enable_filter else "disabled",
                " (platform {}, access-class {})".format(
                    str(_platform),
                    str(_access_class),
                ) if _platform else "",
            )
        )
        self.local_mc.build_structure(_platform, _access_class)
        _init_ok = self.local_mc.init_commands(self, verbose)
        return _init_ok

    def COM_close(self):
        self.local_mc.close_modules()
