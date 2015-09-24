# Copyright (C) 2015 Andreas Lang-Nevyjel init.at
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
""" monitor ovirt instances """

from lxml import etree  # @UnresolvedImport
import commands
import requests

from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools, process_tools, server_command


class _general(hm_classes.hm_module):
    def init_module(self):
        pass


class ovort_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        pass

    def interpret(self, srv_com, cur_ns):
        return limits.nag_STATE_CRITICAL, "not implemented"


def test_code():
    print("test code")
    r = requests.get(
        "https://192.168.1.44/api/vms",
        auth=("admin@internal", "init4u"),
        verify=False,
    )
    _resp = etree.fromstring(r.content)
    print etree.tostring(_resp.findall("vm")[0], pretty_print=True)


if __name__ == "__main__":
    test_code()
