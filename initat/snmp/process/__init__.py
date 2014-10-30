# Copyright (C) 2009-2014 Andreas Lang-Nevyjel
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

# --- hack Counter type, from http://pysnmp.sourceforge.net/faq.html

from pysnmp.proto import rfc1155, rfc1902, api  # @UnresolvedImport


def counter_clone_hack(self, *args):
    if args and args[0] < 0:
        args = (0xffffffff + args[0] - 1,) + args[1:]

    return self.__class__(*args)

rfc1155.TimeTicks.clone = counter_clone_hack
rfc1902.TimeTicks.clone = counter_clone_hack
rfc1155.Counter.clone = counter_clone_hack
rfc1902.Counter32.clone = counter_clone_hack

from batch import snmp_batch
from process import snmp_process
from container import snmp_process_container
