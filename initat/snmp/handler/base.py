# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" handler structures """

from ..functions import oid_to_str
from ..snmp_struct import ResultNode
from initat.tools import logging_tools


class SNMPHandler(object):
    class Meta:
        version = 1
        vendor_name = "generic"
        initial = False
        tl_oids = []
        priority = 0
        identifier = ""

    def __init__(self, log_com):
        self.__log_com = log_com
        # copy keys when needed
        _keys = ["description", "vendor_name", "name", "version", "tl_oids", "priority", "initial", "identifier"]
        for _key in _keys:
            if not hasattr(self.Meta, _key) and hasattr(SNMPHandler.Meta, _key):
                # copy key from default Meta
                setattr(self.Meta, _key, getattr(SNMPHandler.Meta, _key))
            if not hasattr(self.Meta, _key):
                raise KeyError("key {} missing from SNMPHandler Meta {}".format(_key, str(self)))
        self.Meta.full_name = "{}.{}_v{:d}".format(
            self.Meta.vendor_name,
            self.Meta.name,
            self.Meta.version,
        )
        # set flags
        self.Meta.collect = hasattr(self, "collect_fetch")
        self.Meta.mon_check = hasattr(self, "config_mon_check")
        self.Meta.power_control = hasattr(self, "power_control")
        # set lookup keys
        self.Meta.lookup_keys = [
            "{}.{}_v{:d}".format(
                self.Meta.vendor_name,
                self.Meta.name,
                self.Meta.version,
            ),
            "{}.{}".format(
                self.Meta.vendor_name,
                self.Meta.name,
            ),
        ]

    def update(self, dev, scheme, result_dict, oid_list, flags):
        # dummy call
        return ResultNode()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[SH] {}".format(what), log_level)

    def filter_results(self, in_dict, keys_are_strings=True):
        # return a dict where only keys below the tl_oids are present
        # and the top level keys are only strings
        _oid_lut = {
            oid_to_str(oid): oid for oid in in_dict.iterkeys()
        }
        oids = set([oid_to_str(oid) for oid in self.Meta.tl_oids])
        for _key in _oid_lut.iterkeys():
            if _key not in oids and any(_key.startswith(_oid) for _oid in oids):
                oids.add(_key)
        if keys_are_strings:
            return {
                oid: in_dict[_oid_lut[oid]] for oid in oids if oid in _oid_lut
            }
        else:
            return {
                _oid_lut[oid]: in_dict[_oid_lut[oid]] for oid in oids if oid in _oid_lut
            }

    def __unicode__(self):
        return "SNMPHandler {}".format(self.Meta.full_name)
