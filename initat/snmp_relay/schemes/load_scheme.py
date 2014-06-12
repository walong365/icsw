#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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
""" SNMP CPU-Load Scheme """

class load_scheme(snmp_scheme):
    def scheme_init(self, **kwargs):
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.4.1.2021.10.1.3", cache=True)
        self.parser.add_option("-w", type="float", dest="warn", help="warning value [%default]", default=5.0)
        self.parser.add_option("-c", type="float", dest="crit", help="critical value [%default]", default=10.0)
        self.parse_options(kwargs["options"])
    def process_return(self):
        simple_dict = self._simplify_keys(self.snmp_dict.values()[0])
        load_array = [float(simple_dict[key]) for key in [1, 2, 3]]
        max_load = max(load_array)
        ret_state = limits.nag_STATE_CRITICAL if max_load > self.opts.crit else (limits.nag_STATE_WARNING if max_load > self.opts.warn else limits.nag_STATE_OK)
        return ret_state, "load 1/5/15: %.2f / %.2f / %.2f" % (
            load_array[0],
            load_array[1],
            load_array[2])
