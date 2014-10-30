# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
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
""" maps current structure with database """

from initat.cluster.backbone.models import snmp_scheme_vendor, snmp_scheme
from initat.snmp.handler.instances import handlers
from .functions import oid_to_str
import logging_tools


class Schemes(object):
    # to ease access
    def __init__(self, log_com):
        self.__log_com = log_com
        self.__all_vendors = snmp_scheme_vendor.objects.all()
        self.__all_schemes = snmp_scheme.objects.all().prefetch_related("snmp_scheme_tl_oid_set")
        self.__vendor_dict = {value.idx: value for value in self.__all_vendors}
        self.__scheme_dict = {
            "{}.{}".format(
                self.__vendor_dict[value.snmp_scheme_vendor_id].name,
                value.name,
            ): value for value in self.__all_schemes}
        # ToDo: check for database / filesystem mismatch
        # print self.__scheme_dict
        self.__handlers = [_handler(self.__log_com) for _handler in handlers]
        # for _h in self.__handlers:
        #    print _h.Meta.lookup_keys
        for _scheme in self.__all_schemes:
            self.__scheme_dict[_scheme.pk] = _scheme
        self.__oid_lut = {}
        for _sc in self.__all_schemes:
            for _tl in _sc.snmp_scheme_tl_oid_set.all():
                self.__oid_lut[_tl.oid] = _sc
        self.log("init Schemes")

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[Sc] {}".format(what), log_level)

    def all_schemes(self):
        return self.__scheme_dict.itervalues()

    def all_tl_oids(self):
        return sum([list(_sc.snmp_scheme_tl_oid_set.all()) for _sc in self.__scheme_dict.itervalues()], [])

    def get_scheme(self, key):
        return self.__scheme_dict[key]

    def get_scheme_by_oid(self, oid):
        return self.__oid_lut.get(oid_to_str(oid), None)

    def filter_results(self, in_dict, oids):
        # return a dict where only the given oids are present
        # and the top level keys are only strings
        _oid_lut = {oid_to_str(oid): oid for oid in in_dict.iterkeys()}
        oids = [oid_to_str(oid) for oid in oids]
        return {oid: in_dict[_oid_lut[oid]] for oid in oids if oid in _oid_lut}

    def get_handlers(self, scheme_names):
        print "gh", scheme_names
