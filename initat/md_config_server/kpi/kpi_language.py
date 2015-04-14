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
# noinspection PyUnresolvedReferences
import pprint
import ast
import re
from types import NoneType

from enum import IntEnum
import itertools

from initat.md_config_server.kpi.kpi_historic import TimeLineUtils, TimeLineEntry
from initat.md_config_server.kpi.kpi_utils import KpiUtils
import logging_tools
from initat.cluster.backbone.models.status_history import mon_icinga_log_raw_service_alert_data
from initat.cluster.backbone.models import mon_icinga_log_aggregated_service_data, duration, \
    mon_icinga_log_aggregated_timespan, mon_check_command, device


logger = logging_tools.logging.getLogger("cluster.kpi")


# itertools recipe
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


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
    def __init__(self, result=None, host_name=None, host_pk=None):
        if (host_name is None) != (host_pk is None):
            raise ValueError("host_name is {} but host_pk is {}".format(host_name, host_pk))

        self.result = result if isinstance(result, (KpiResult, NoneType)) \
            else KpiResult.from_numeric_icinga_service_status(result)
        self.host_name = host_name
        self.host_pk = host_pk

    @classmethod
    def deserialize(cls, data):
        return KpiObject(**data)

    def serialize(self):
        return {
            'result': None if self.result is None else self.result.get_numeric_icinga_service_status(),
            'host_name': self.host_name,
            'host_pk': self.host_pk,
        }

    def __repr__(self, child_repr=""):
        contents = ""
        # if self.rrd is not None:
        #    contents += 'rrd={}:{};'.format(self.rrd.key, self.rrd.get_value())
        if self.result is not None:
            contents += 'result={}'.format(self.result)

        return "KpiObject(host={}:{};{}{})".format(self.host_name, self.host_pk, contents, child_repr)

    def full_repr(self):
        return self.__repr__()


# all object types:

# rrd_key, rrd_value, host
# result, host
# result, host, serv_id, service_info
# host (historic host)
# host, serv_id, service_info (historic service)
# host, serv_id, service_info, time line
# compound time line
# result
# detail


class KpiDetailObject(KpiObject):
    """Kpi Object with some misc data attached"""
    def __init__(self, detail, **kwargs):
        if detail is None:
            raise ValueError("detail is None")
        super(KpiDetailObject, self).__init__(**kwargs)
        self.detail = detail

    def __repr__(self, child_repr=""):
        return super(KpiDetailObject, self).__repr__(child_repr=child_repr + ";detail:{}".format(self.detail))


class KpiRRDObject(KpiObject):
    """Kpi Object with rrd data"""
    def __init__(self, rrd_key, rrd_value, **kwargs):
        if rrd_key is None:
            raise ValueError("rrd_key is None")
        if rrd_value is None:
            raise ValueError("rrd_value is None")
        super(KpiRRDObject, self).__init__(**kwargs)
        self.rrd_key = rrd_key
        self.rrd_value = rrd_value

    def __repr__(self, child_repr=""):
        return super(KpiRRDObject, self).__repr__(child_repr=child_repr +
                                                  "rrd:{}:{}".format(self.rrd_key, self.rrd_value))


class KpiServiceObject(KpiObject):
    """Kpi Object which references a particular service"""
    def __init__(self, service_id=None, service_info=None, mcc=None, **kwargs):
        if service_id is None:
            raise ValueError("service_id is None")
        if service_info is None:
            raise ValueError("service_info is None")
        super(KpiServiceObject, self).__init__(**kwargs)
        if self.host_pk is None:
            logger.warn("KpiServiceObject without host pk: {} {}".format(service_id, service_info))
        self.service_id = service_id
        self.service_info = service_info
        try:
            if mcc is None:
                mcc = mon_check_command.objects.get(pk=service_id)
        except mon_check_command.DoesNotExist:
            logger.debug("referenced check command which does not exist: {}".format(service_id))
            self.check_command = None
            self.check_command_description = None
            self.config = None
            self.config_description = None
        else:
            self.check_command = mcc.name
            self.check_command_description = mcc.description
            self.config = mcc.config.name
            self.config_description = mcc.config.description

    def __repr__(self, child_repr=""):
        my_repr = ";service:{}:{}".format(self.check_command if self.check_command is not None else self.service_id,
                                          self.service_info)
        return super(KpiServiceObject, self).__repr__(child_repr=child_repr + my_repr)


class KpiTimeLineObject(KpiObject):
    """Kpi Object which has a time line"""
    def __init__(self, time_line=None, **kwargs):
        if time_line is None:
            raise ValueError("time_line is None")
        super(KpiTimeLineObject, self).__init__(**kwargs)
        self.time_line = time_line


class KpiServiceTimeLineObject(KpiServiceObject, KpiTimeLineObject):
    pass


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
        parents = [KpiSet.deserialize(set_json) for set_json in data['parents']]\
            if data['parents'] is not None else None
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

    ########################################
    # data accessors
    #

    def __iter__(self):
        return iter(self.objects)

    def __len__(self):
        return len(self.objects)

    @property
    def result_objects(self):
        return [obj for obj in self.objects if obj.result is not None]

    @property
    def service_objects(self):
        """
        :rtype : list of KpiServiceObject
        """
        return [obj for obj in self.objects if isinstance(obj, KpiServiceObject)]

    @property
    def time_line_objects(self):
        """
        :rtype : list of KpiTimeLineObject
        """
        return [obj for obj in self.objects if isinstance(obj, KpiTimeLineObject)]

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
        if not self.time_line_objects:
            retval = KpiSet.get_singleton_unknown(parents=[self])
        else:
            # work on copies
            compound_time_line = TimeLineUtils.calculate_compound_time_line(
                method,
                [obj.time_line for obj in self.time_line_objects],
            )

            retval = KpiSet(
                objects=[KpiTimeLineObject(time_line=compound_time_line)],
                parents=[self],
            )

        return retval

    def historic_or(self):
        return self.aggregate_historic(method='or')

    def historic_and(self):
        return self.aggregate_historic(method='and')

    def get_historic_data(self):
        # group historic data per dev and service
        device_service_identifiers = []
        # TODO: host check results
        for obj in self.service_objects:
            if obj.host_pk is not None:
                device_service_identifiers.append(
                    (obj.host_pk, obj.service_id, obj.service_info)
                )

        objects = []
        if device_service_identifiers:

            # end = django.utils.timezone.now()
            # start = end - datetime.timedelta(days=7)
            # start = datetime.date(2014, 01, 25)  # django change
            # end = datetime.date(2015, 01, 01)

            # start = datetime.date(2014, 01, 06)
            # end = datetime.date(2014, 01, 30)

            start, end = KpiUtils.parse_kpi_time_range_from_kpi(self._get_current_kpi())

            time_lines = TimeLineUtils.calculate_time_lines(device_service_identifiers, start, end)

            for (dev_id, service_id, service_info), time_line in time_lines.iteritems():
                for kpi_obj in self.service_objects:
                    if kpi_obj.host_pk == dev_id \
                            and kpi_obj.service_id == service_id \
                            and kpi_obj.service_info == service_info:
                        objects.append(
                            KpiServiceTimeLineObject(
                                host_name=kpi_obj.host_name,
                                host_pk=kpi_obj.host_pk,
                                service_id=kpi_obj.service_id,
                                service_info=kpi_obj.service_info,
                                time_line=time_line
                            )
                        )
                        break
                else:
                    print ("Historical obj found but no kpi obj: {} {} {}".format(dev_id, service_id, service_info))
                    # TODO: logging is broken in this context

        return KpiSet(objects=objects, parents=[self])

    def evaluate_historic(self, ratio_ok, ratio_warn):
        """
        Check if up percentage is at least some value
        """
        if not self.time_line_objects:
            return KpiSet.get_singleton_unknown(parents=[self])
        else:
            objects = []
            start, end = KpiUtils.parse_kpi_time_range_from_kpi(self._get_current_kpi())

            for tl_obj in self.time_line_objects:

                states_accumulator = collections.defaultdict(lambda: 0)
                for entry1, entry2 in pairwise(itertools.chain(tl_obj.time_line,
                                                               [TimeLineEntry(date=end, state=None)])):
                    time_span = entry2.date - entry1.date
                    states_accumulator[entry1.state] += time_span.total_seconds()

                total_time_span = sum(states_accumulator.itervalues())
                amount_ok = sum(v for k, v in states_accumulator.iteritems()
                                if k[0] == mon_icinga_log_raw_service_alert_data.STATE_OK)

                amount_warn = sum(v for k, v in states_accumulator.iteritems()
                                  if k[0] == mon_icinga_log_raw_service_alert_data.STATE_WARNING)
                detail = {k: v / total_time_span for k, v in states_accumulator.iteritems()}

                if amount_ok / total_time_span >= ratio_ok:
                    result = KpiResult.ok
                elif amount_warn / total_time_span >= ratio_warn:
                    result = KpiResult.warn
                else:
                    result = KpiResult.critical

                objects.append(
                    KpiDetailObject(result=result, detail=detail)
                )

            return KpiSet(objects=objects, parents=[self])

    def evaluate(self):
        """
        Calculate "worst" result, i.e. result is critical
        if at least one is critical or else warn if at least one is warn etc.
        """
        # TODO: have parameter: method
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
            # if 'time_line' in obj.__dict__: print "TL:", obj.time_line
        print "DUMP END"

        return self

    def __repr__(self):
        magic = 3
        return "KpiSet({})".format(self.objects if len(self.objects) <= magic else
                                   repr(self.objects[:magic]) + "... ({} more)".format(len(self.objects) - magic))


"""
 def get_historic_only_aggregated_data(self):
     # TODO: deprecate?
     ""
     Retrieve historical data and returns set of only those which have it
     ""
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

def evaluate_historic(self, ratio_ok, ratio_warn):
    ""
    Currently we check if up percentage is at least
    ""

    objects = []
    for obj in self.time_line_objects:
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
                    KpiObject(result=result)
                )

    return KpiSet(objects=objects, parents=[self])
    #"""
