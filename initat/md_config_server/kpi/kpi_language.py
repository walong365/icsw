# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
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
import ast
import re
from enum import Enum, IntEnum


class KpiResult(IntEnum):
    # this is ordered by badness
    ok = 10
    warn = 20
    unknown = 30
    critical = 40

    @classmethod
    def from_numeric_icinga_service_status(cls, num):
        if num == 0:
            return KpiResult.ok
        elif num == 1:
            return KpiResult.warn
        elif num == 2:
            return KpiResult.critical
        elif num == 3:
            return KpiResult.unknown


class KpiObject(object):
    def __init__(self, result=None, historical_data=None, rrd=None, **properties):
        self.result = result
        self.historical_data = historical_data
        self.rrd = rrd
        for k, v in properties.iteritems():
            setattr(self, k, v)

    def __repr__(self):
        contents = ""
        data = ("result", "historical_data", "rrd")
        for prop in data:
            val = getattr(self, prop, None)
            if val is not None:
                contents += "{}={};".format(prop, val)
        contents += "properties={}".format({k: v for k, v in self.__dict__.iteritems() if k not in data})
        return "KpiObject({})".format(contents)


class KpiSet(object):
    @classmethod
    def get_singleton_ok(cls):
        return KpiSet([KpiObject(result=KpiResult.ok)])

    @classmethod
    def get_singleton_warn(cls):
        return KpiSet([KpiObject(result=KpiResult.warn)])

    @classmethod
    def get_singleton_critical(cls):
        return KpiSet([KpiObject(result=KpiResult.critical)])

    def __init__(self, objects):
        self.objects = objects

    @property
    def result_objects(self):
        return [obj for obj in self.objects if obj.result is not None]

    def filter(self, **kwargs):
        objects = self.objects
        for k, v in kwargs.iteritems():
            if isinstance(v, basestring):
                match_re = re.compile(".*{}.*".format(v))
                is_match = lambda x: match_re.match(x)
            else:
                is_match = lambda x: x == v
            objects = [obj for obj in objects if is_match(getattr(obj, k, None))]

        return KpiSet(objects)

    def union(self, kpiSet):
        return KpiSet(self.objects + kpiSet.objects)

    __add__ = union

    def at_least(self, num_ok, num_warn, result=KpiResult.ok):
        """
        Check if at_least a number of objects have a certain result.
        """
        if num_warn > num_ok:
            raise ValueError("num_warn is higher than num_ok ({} > {})".format(num_warn, num_ok))
        num = sum(1 for obj in self.result_objects if obj.result == result)
        if num > num_ok:
            return KpiSet.get_singleton_ok()
        elif num > num_warn:
            return KpiSet.get_singleton_warn()
        else:
            return KpiSet.get_singleton_critical()

    def aggregate(self):
        """
        Calculate "worst" result, i.e. result is critical if at least one is critical or else warn if at least one is warn etc.
        """
        aggregated_result = max(obj.result for obj in self.result_objects)
        return KpiSet([KpiObject(result=aggregated_result)])

    def __repr__(self):
        return "KpiSet({})".format(self.objects)


if __name__ == "__main__":

    kpi = """ (
        data
        .filter(device_name='am-admin')
        .filter(config='am_admin_checks')

        +

        data
        .filter(device_name='am-directory')
        .filter(config='am_directory_checks')
    ).aggregate()
    """

    data = KpiSet([
        KpiObject(result=KpiResult.ok, device_name='am-admin', config='am_admin_checks', check='am_admin_check_1'),
        KpiObject(result=KpiResult.warn, device_name='am-admin', config='am_admin_checks', check='am_admin_check_2'),
        KpiObject(result=KpiResult.ok, device_name='am-directory', config='am_directory_checks', check='some_check'),
    ])

    kpi = kpi.replace("\n \t", "").strip()

    print eval(compile(ast.parse(kpi, mode='eval'), '<string>', mode='eval'))
    print eval(kpi)

    # TODO: check which operations we need to perform on this data (mostly drill-down probably)





