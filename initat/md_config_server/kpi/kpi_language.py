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

# noinspection PyUnresolvedReferences
import pprint
import ast
import re
import json
from enum import IntEnum


class KpiResult(IntEnum):
    # this is ordered by badness and also same as nagios convention
    ok = 0
    warn = 1
    critical = 2
    unknown = 3

    def get_numeric_icinga_service_status(self):
        return self.value

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
        else:
            raise ValueError("Invalid numeric icinga service status: {}".format(num))


class KpiObject(object):
    def __init__(self, result=None, historical_data=None, rrd=None, host_name=None, properties=None):
        self.result = result if isinstance(result, KpiResult) else KpiResult.from_numeric_icinga_service_status(result)
        self.historical_data = historical_data
        # self.rrd = rrd
        self.host_name = host_name
        self.properties = properties if properties is not None else {}

    @classmethod
    def deserialize(cls, data):
        return KpiObject(**data)

    def serialize(self):
        return {
            'result': self.result.get_numeric_icinga_service_status(),
            'historical_data': self.historical_data,
            # 'rrd': self.rrd,
            'host_name': self.host_name,
            'properties': self.properties,
        }

    def __repr__(self):
        contents = ""
        # if self.rrd is not None:
        #    contents += 'rrd={}:{};'.format(self.rrd.key, self.rrd.get_value())
        if self.result is not None:
            cc = self.properties.get('check_command', None)
            res_type = "{}:".format(cc) if cc is not None else ""
            contents += 'result={}{}'.format(res_type, self.result)
        if 'rrd_key' in self.properties:
            contents += 'rrd={}:{};'.format(self.properties['rrd_key'], self.properties['rrd_value'])
        if self.historical_data is not None:
            raise NotImplementedError()

        return "KpiObject(host_name={};{})".format(self.host_name, contents)

    def full_repr(self):
        contents = ""
        data = ("result", "historical_data", "rrd")
        for prop in data:
            val = getattr(self, prop, None)
            if val is not None:
                contents += "{}={};".format(prop, val)
        contents += "properties={}".format({k: v for k, v in self.properties.iteritems()})
        return "KpiObject({})".format(contents)

    # we use this to eliminate duplicates in the kpi set, but only for initial data currently
    def __hash_key(self):
        return (self.result, self.historical_data,
                # self.rrd,
                self.host_name, tuple(self.properties.items()))

    def __eq__(self, other):
        return isinstance(other, KpiObject) and self.__hash_key() == other.__hash_key()

    def __hash__(self):
        return hash(self.__hash_key())


class KpiSet(object):
    @classmethod
    def get_singleton_ok(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.ok)], **kwargs)

    @classmethod
    def get_singleton_warn(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.warn)], **kwargs)

    @classmethod
    def get_singleton_critical(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.critical)], **kwargs)

    @classmethod
    def get_singleton_unknown(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.unknown)], **kwargs)

    def __init__(self, objects, parents=None):
        """
        :type objects: list of KpiObject
        :type parents: list of KpiSet
        """
        self.objects = objects
        self.parents = parents

    @classmethod
    def deserialize(cls, data):
        objects = [KpiObject.deserialize(obj_json) for obj_json in data['objects']]
        parents = [KpiSet.deserialize(set_json) for set_json in data['parents']] if data['parents'] is not None else None
        return KpiSet(objects, parents)

    def serialize(self):
        return {
            "objects": [obj.serialize() for obj in self.objects],
            "parents": [par.serialize() for par in self.parents] if self.parents is not None else None,
        }

    @property
    def result_objects(self):
        return [obj for obj in self.objects if obj.result is not None]

    ########################################
    # proper kpi language elements
    #

    def filter(self, **kwargs):
        objects = self.objects
        # print 'call filter args:', kwargs
        # print '    on objs:', objects
        # pprint.pprint(objects)
        for k, v in kwargs.iteritems():
            if isinstance(v, basestring):
                match_re = re.compile(".*{}.*".format(v))
                is_match = lambda x: x is not None and match_re.match(x)
            else:
                is_match = lambda x: x == v
            objects = [obj for obj in objects if
                       is_match(obj.properties.get(k, None)) or
                       is_match(getattr(obj, k, None))]

        # print '    results', objects

        return KpiSet(objects, parents=[self])

    def union(self, kpi_set):
        return KpiSet(self.objects + kpi_set.objects, parents=[self, kpi_set])

    __add__ = union

    def at_least(self, num_ok, num_warn, result=KpiResult.ok):
        """
        Check if at_least a number of objects have a certain result.
        """
        if num_warn > num_ok:
            raise ValueError("num_warn is higher than num_ok ({} > {})".format(num_warn, num_ok))
        num = sum(1 for obj in self.result_objects if obj.result == result)
        if num > num_ok:
            return KpiSet.get_singleton_ok(parents=[self])
        elif num > num_warn:
            return KpiSet.get_singleton_warn(parents=[self])
        else:
            return KpiSet.get_singleton_critical(parents=[self])

    def aggregate(self):
        """
        Calculate "worst" result, i.e. result is critical
        if at least one is critical or else warn if at least one is warn etc.
        """
        # print 'call aggregate on ', self.result_objects
        if not self.result_objects:
            return KpiSet.get_singleton_unknown(parents=[self])
        else:
            aggregated_result = max(obj.result for obj in self.result_objects)
            return KpiSet([KpiObject(result=aggregated_result)], parents=[self])

    def dump(self):
        """Debug function: Log set contents and return itself"""
        print "DUMP:", self.objects
        return self

    def __repr__(self):
        magic = 3
        return "KpiSet({})".format(self.objects if len(self.objects) <= magic else
                                   repr(self.objects[:magic]) + "... ({} more)".format(len(self.objects) - magic))


def astdump(node, annotate_fields=True, include_attributes=False, indent='  '):
    """
    Return a formatted dump of the tree in *node*.  This is mainly useful for
    debugging purposes.  The returned string will show the names and the values
    for fields.  This makes the code impossible to evaluate, so if evaluation is
    wanted *annotate_fields* must be set to False.  Attributes such as line
    numbers and column offsets are not dumped by default.  If this is wanted,
    *include_attributes* can be set to True.
    """
    def _format(node, level=0):
        if isinstance(node, ast.AST):
            fields = [(a, _format(b, level)) for a, b in ast.iter_fields(node)]
            if include_attributes and node._attributes:
                fields.extend([(a, _format(getattr(node, a), level))
                               for a in node._attributes])
            return ''.join([
                node.__class__.__name__,
                '(',
                ', '.join(('%s=%s' % field for field in fields) if annotate_fields else (b for a, b in fields)),
                ')'])
        elif isinstance(node, list):
            lines = ['[']
            lines.extend((indent * (level + 2) + _format(x, level + 2) + ','
                         for x in node))
            if len(lines) > 1:
                lines.append(indent * (level + 1) + ']')
            else:
                lines[-1] += ']'
            return '\n'.join(lines)
        return repr(node)
    if not isinstance(node, ast.AST):
        raise TypeError('expected AST, got %r' % node.__class__.__name__)
    return _format(node)


def print_tree(t, i=0):
    print " " * i, t
    if t.parents:
        for p in t.parents:
            print_tree(p, i + 8)
