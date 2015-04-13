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
import collections
import pprint
import ast
import re
import json
import datetime
from types import NoneType
from enum import IntEnum
import django.utils.timezone
from initat.md_config_server.kpi.kpi_historic import TimeLineEntry, TimeLine
import logging_tools
from initat.cluster.backbone.models.status_history import mon_icinga_log_raw_service_alert_data
from initat.cluster.backbone.models import mon_icinga_log_aggregated_service_data, duration, \
    mon_icinga_log_aggregated_timespan, mon_icinga_log_raw_base


logger = logging_tools.logging.getLogger("cluster.kpi")


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
        self.result = result if isinstance(result, (KpiResult, NoneType)) \
                             else KpiResult.from_numeric_icinga_service_status(result)
        self.historical_data = historical_data
        # self.rrd = rrd
        self.host_name = host_name
        self.properties = properties if properties is not None else {}

        # current state of properties (make this into proper data structures):
        # rrd: host_name, key, value (also scale, etc). NO SERVICE
        # check result: description string, hence check command pk, service_info and device
        # historic: same as check result plus time range


    @classmethod
    def deserialize(cls, data):
        return KpiObject(**data)

    SERIALIZE_BLACKLIST = ["time_line"]

    def serialize(self):
        return {
            'result': None if self.result is None else self.result.get_numeric_icinga_service_status(),
            'historical_data': self.historical_data,
            # 'rrd': self.rrd,
            'host_name': self.host_name,
            'properties': {k: v for k, v in self.properties.iteritems() if k not in self.__class__.SERIALIZE_BLACKLIST},
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

    def __init__(self, objects, parents=None, explanation=None, kpi=None):
        """
        :type objects: list of KpiObject
        :type parents: list of KpiSet
        :param explanation: KpiSet of objects which explain the current state, e.g. services which are critical
        :type explanation: KpiSet
        :param kpi: Kpi object we are calculating. Only set for first KpiSet, with which the calculations start.
        """
        self.objects = objects
        self.parents = parents
        self.explanation = explanation
        self.kpi = kpi

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

    def _get_current_kpi(self):
        """
        Get Kpi object from original kpi set. Assumes that parent-chain is valid!
        :rtype : Kpi
        """
        if self.kpi is not None:
            kpi = self.kpi
        else:
            kpi = None
            if self.parents is not None:
                for par in self.parents:
                    kpi = par._get_current_kpi()
                    if kpi is not None:
                        break
                else:
                    raise ValueError("Failed to find top level kpi set.")
        return kpi

    def __iter__(self):
        return iter(self.objects)

    def __len__(self):
        return len(self.objects)

    @property
    def result_objects(self):
        return [obj for obj in self.objects if obj.result is not None]

    @property
    def check_command_objects(self):
        return [obj for obj in self.objects if 'check_command_pk' in obj.properties]  # TODO: make into nice obj

    @property
    def host_check_objects(self):
        return [obj for obj in self.objects if True]  # TODO: make into nice obj

    @property
    def historical_data_objects(self):
        # TODO: there is hist_data for aggregated and time_line currently
        return [obj for obj in self.objects if 'time_line' in obj.properties]  # TODO: make into nice obj

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

    def aggregate_historic(self, method):
        """
        :param method: "or" or "and"
        """
        if not self.historical_data_objects:
            retval = KpiSet.get_singleton_unknown(parents=[self])
        else:
            # work on copies
            compound_time_line = TimeLine.calculate_compound_time_line(
                method,
                [(obj.properties['time_line']) for obj in self.historical_data_objects],
            )

            retval = KpiSet(
                objects=[KpiObject(properties={'time_line': compound_time_line})],
                parents=[self],
            )

        return retval

    def historic_or(self):
        return self.aggregate_historic(method='or')

    def historic_and(self):
        return self.aggregate_historic(method='and')

    def get_historic(self):
        # group historic data per dev and service
        device_service_identifiers = []
        # TODO: host check results
        for obj in self.check_command_objects:
            device_service_identifiers.append(
                (obj.properties['host_pk'], obj.properties['check_command_pk'], obj.properties['service_info'])
            )

        objects = []
        if device_service_identifiers:

            #end = django.utils.timezone.now()
            #start = end - datetime.timedelta(days=7)
            #start = datetime.date(2014, 01, 25)  # django change
            #end = datetime.date(2015, 01, 01)

            # start = datetime.date(2014, 01, 06)
            # end = datetime.date(2014, 01, 30)

            kpi_db = self._get_current_kpi()
            start, end = _KpiUtil.parse_kpi_time_range(kpi_db.time_range, kpi_db.time_range_parameter)
            if start is None:
                raise RuntimeError("get_historic called for kpi with no defined time range.")

            time_lines = TimeLine.calculate_time_lines(device_service_identifiers, start, end)

            for (dev_id, service_id, service_info), time_line in time_lines.iteritems():
                for kpi_obj in self.check_command_objects:
                    if kpi_obj.properties['host_pk'] == dev_id \
                            and kpi_obj.properties['check_command_pk'] == service_id \
                            and kpi_obj.properties['service_info'] == service_info:
                        kpi_obj.properties['time_line'] = time_line
                        # NOTE: we reuse the objects here
                        objects.append(kpi_obj)
                        break
                else:
                    print ("Historical obj found but no kpi obj: {} {} {}".format(dev_id, service_id, service_info))
                    # TODO: logging is broken in this context

        return KpiSet(objects=objects, parents=[self])

    def get_historic_only_aggregated_data(self):
        # TODO: deprecate?
        """
        Retrieve historical data and returns set of only those which have it
        """
        # group historic data per dev and service
        devices = collections.defaultdict(lambda: [])
        for obj in self.check_command_objects:
            devices[obj.properties['host_pk']].append(
                (obj.properties['check_command_pk'], obj.properties['service_info'])
            )

        objects = []
        if devices:

            # end = django.utils.timezone.now()
            # start = end - datetime.timedelta(days=7*4)
            # start = datetime.date(2014, 01, 25)  # django change
            # end = datetime.date(2014, 12, 31)

            # TODO: handle case where len(timespans) is too small (this will depend on the kind of dates we support)

            timespans = mon_icinga_log_aggregated_timespan.objects.filter(duration_type=duration.Day.ID,
                                                                          start_date__range=(start, end))

            hist_data = mon_icinga_log_aggregated_service_data.objects.get_data(devices=devices,
                                                                                timespans=timespans,
                                                                                use_client_name=False)

            for dev_id, service_data in hist_data.iteritems():
                for (service_id, service_info), state_list in service_data.iteritems():
                    for kpi_obj in self.check_command_objects:
                        if kpi_obj.properties['host_pk'] == dev_id \
                                and kpi_obj.properties['check_command_pk'] == service_id \
                                and kpi_obj.properties['service_info'] == service_info:
                            kpi_obj.properties['hist_data'] = "{}, {}, {}".format(dev_id, service_id, service_info)
                            kpi_obj.properties['hist_detail'] = state_list
                            objects.append(kpi_obj)
                            break
                    else:
                        print ("Historical obj found but no kpi obj: {} {} {}".format(dev_id, service_id, service_info))
                        # TODO: logging is broken in this context
                        # logger.warn("Historical obj found but no kpi obj: {} {} {}".format(dev_id, service_id, service_info))
        return KpiSet(objects=objects, parents=[self])

    def interpret_historic(self, ratio_ok, ratio_warn):
        """
        Currently we check if up percentage is at least
        """
        objects = []
        for obj in self.historical_data_objects:
            for dev_id, service_data in obj.properties['hist_data'].iteritems():
                for (service_id, service_info), state_list in service_data.iteritems():
                    # TODO: create nice KpiHistoricObject, also KpiCheckObject, make both inherit _KpiCheckObjectBase
                    # the hist obj has additional date info containing actual date used

                    ok_states = [state_entry for state_entry in state_list
                                 if state_entry['state'] == mon_icinga_log_raw_service_alert_data.STATE_OK]
                    if not ok_states:
                        ok_value = 0
                    else:
                        ok_value = ok_states[0]['value']
                        if len(ok_states) > 1:
                            logger.warn("Multiple ok states for {} {} {}: {}".format(dev_id, service_id,
                                                                                     service_data, state_list))

                    if ok_value >= ratio_ok:
                        result = KpiResult.ok
                    elif ok_value >= ratio_warn:
                        result = KpiResult.warn
                    else:
                        result = KpiResult.critical

                    objects.append(
                        KpiObject(
                            result=result,
                        )
                    )

        return KpiSet(objects=objects, parents=[self])

    def evaluate(self):
        """
        Calculate "worst" result, i.e. result is critical
        if at least one is critical or else warn if at least one is warn etc.
        """
        # TODO: have parameter method
        # print 'call aggregate on ', self.result_objects
        if not self.result_objects:
            return KpiSet.get_singleton_unknown(parents=[self])
        else:
            aggregated_result = max(obj.result for obj in self.result_objects)
            causes = list(obj for obj in self.result_objects if obj.result == aggregated_result)
            return KpiSet([KpiObject(result=aggregated_result)], parents=[self], explanation=KpiSet(objects=causes))

    def dump(self, msg=None):
        """Debug function: Log set contents and return itself"""
        print "\nDUMP {}:".format("" if msg is None else msg), self.objects
        for obj in self.objects:
            print obj.full_repr()
            if 'time_line' in obj.properties:
                print "TL:", obj.properties['time_line']
        print "DUMP END"

        return self

    def __repr__(self):
        magic = 3
        return "KpiSet({})".format(self.objects if len(self.objects) <= magic else
                                   repr(self.objects[:magic]) + "... ({} more)".format(len(self.objects) - magic))


class _KpiUtil(object):
    @staticmethod
    def parse_kpi_time_range(time_range, time_range_parameter):

        def get_duration_class_start_end(duration_class, time_point):
            start = duration_class.get_time_frame_start(
                time_point
            )
            end = duration_class.get_end_time_for_start(start)
            return start, end

        start, end = None, None

        if time_range == 'none':
            pass
        elif time_range == 'yesterday':
            start, end = get_duration_class_start_end(
                duration.Day,
                django.utils.timezone.now() - datetime.timedelta(days=1),
                )
        elif time_range == 'last week':
            start, end = get_duration_class_start_end(
                duration.Week,
                django.utils.timezone.now() - datetime.timedelta(days=7),
                )
        elif time_range == 'last month':
            start, end = get_duration_class_start_end(
                duration.Month,
                django.utils.timezone.now().replace(day=1) - datetime.timedelta(days=1)
            )
        elif time_range == 'last year':
            start, end = get_duration_class_start_end(
                duration.Year,
                django.utils.timezone.now().replace(day=1, month=1) - datetime.timedelta(days=1)
            )
        elif time_range == 'last n days':
            start = duration.Day.get_time_frame_start(
                django.utils.timezone.now() - datetime.timedelta(days=time_range_parameter)
            )
            end = start + datetime.timedelta(days=time_range_parameter)

        return (start, end)

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
    print " " * i, t, t.explanation
    if t.parents:
        for p in t.parents:
            print_tree(p, i + 8)
