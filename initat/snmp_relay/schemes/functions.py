# Copyright (C) 2009-2015 Andreas Lang-Nevyjel
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
""" helper functions for SNMP relayer """


def k_str(i_val):
    f_val = float(i_val)
    if f_val < 1024:
        return "%0.f kB" % (f_val)
    f_val /= 1024.
    if f_val < 1024.:
        return "%.2f MB" % (f_val)
    f_val /= 1024.
    return "%.2f GB" % (f_val)
