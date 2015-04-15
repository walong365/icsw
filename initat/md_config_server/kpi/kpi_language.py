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

import re
from types import NoneType
# noinspection PyUnresolvedReferences
import collections
# noinspection PyUnresolvedReferences
import pprint

from enum import IntEnum, Enum

from initat.md_config_server.kpi.kpi_historic import TimeLineUtils
from initat.md_config_server.kpi.kpi_utils import KpiUtils
import logging_tools
from initat.cluster.backbone.models.status_history import mon_icinga_log_raw_service_alert_data
from initat.cluster.backbone.models import mon_icinga_log_aggregated_service_data, mon_check_command


logger = logging_tools.logging.getLogger("cluster.kpi")


class KpiResult(IntEnum):
    # this is ordered by badness and also same as nagios convention
    ok = 0
    warning = 1
    critical = 2
    unknown = 3
    undetermined = 4

    def get_numeric_icinga_service_status(self):
        return self.value

    @classmethod
    def from_numeric_icinga_service_status(cls, num):
        if num == 0:
            return KpiResult.ok
        elif num == 1:
            return KpiResult.warning
        elif num == 2:
            return KpiResult.critical
        elif num == 3:
            return KpiResult.unknown
        elif num == 4:
            # icinga service status does not have undetermined, this is icsw-only
            return KpiResult.undetermined
        else:
            raise ValueError("Invalid numeric icinga service status: {}".format(num))

    def get_corresponding_service_enum_value(self):
        return {
            KpiResult.ok: mon_icinga_log_raw_service_alert_data.STATE_OK,
            KpiResult.warning: mon_icinga_log_raw_service_alert_data.STATE_WARNING,
            KpiResult.critical: mon_icinga_log_raw_service_alert_data.STATE_CRITICAL,
            KpiResult.unknown: mon_icinga_log_raw_service_alert_data.STATE_UNKNOWN,
            KpiResult.undetermined: mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED,
        }


class KpiObject(object):
    def __init__(self, result=None, host_name=None, host_pk=None, kpi_id=None):
        if (host_name is None) != (host_pk is None):
            raise ValueError("host_name is {} but host_pk is {}".format(host_name, host_pk))

        self.kpi_id = kpi_id if kpi_id is not None else id(self)

        self.result = result if isinstance(result, (KpiResult, NoneType)) \
            else KpiResult.from_numeric_icinga_service_status(result)
        self.host_name = host_name
        self.host_pk = host_pk

    @classmethod
    def deserialize(cls, data):
        return KpiObject(**data)

    def serialize(self):
        # we serialize for the client to show something, not for a functional representation
        return {
            'kpi_id': self.kpi_id,
            'result': None if self.result is None else self.result.get_numeric_icinga_service_status(),
            'host_name': self.host_name,
            'host_pk': self.host_pk,
        }

    def get_object_identifier_properties(self):
        """Returns all properties of the object which identify it for the user (usually host and service)"""
        return {
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

    def serialize(self):
        trans = mon_icinga_log_aggregated_service_data.STATE_CHOICES_READABLE
        return dict(
            detail={"{};{}".format(trans[k[0]], k[1]): v for k, v in self.detail.iteritems()},
            **super(KpiDetailObject, self).serialize()
        )


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

    def serialize(self):
        return dict(
            rrd_key=self.rrd_key,
            rrd_value=self.rrd_value,
            **super(KpiRRDObject, self).serialize()
        )


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

    def serialize(self):
        return dict(
            service_name=self.check_command,
            service_info=self.service_info,
            **super(KpiServiceObject, self).serialize()
        )

    def get_object_identifier_properties(self):
        return dict(
            service_name=self.check_command,
            service_info=self.service_info,
            **super(KpiServiceObject, self).get_object_identifier_properties()
        )


class KpiTimeLineObject(KpiObject):
    """Kpi Object which has a time line"""
    def __init__(self, time_line=None, **kwargs):
        if time_line is None:
            raise ValueError("time_line is None")
        super(KpiTimeLineObject, self).__init__(**kwargs)
        self.time_line = time_line

    def serialize(self):
        trans = mon_icinga_log_aggregated_service_data.STATE_CHOICES_READABLE
        return dict(
            aggregated_tl={"{};{}".format(trans[k[0]], k[1]): v
                           for k, v in TimeLineUtils.aggregate_time_line(self).iteritems()},
            **super(KpiTimeLineObject, self).serialize()
        )


class KpiServiceTimeLineObject(KpiServiceObject, KpiTimeLineObject):
    pass


class KpiServiceDetailObject(KpiServiceObject, KpiDetailObject):
    pass


class KpiOperation(object):
    class Type(Enum):
        initial = 1
        filter = 2
        union = 3
        at_least = 4
        evaluate = 5
        evaluate_historic = 6
        evaluate_rrd = 7
        get_historic_data = 8
        aggregate_historic = 9

    def __init__(self, type, operands=None, arguments=None):
        if arguments is None:
            arguments = {}
        if operands is None:  # only for initial and possibly specially constructed sets
            operands = []
        self.type = type
        self.operands = operands
        self.arguments = arguments

    def serialize(self):
        return {
            'type': self.type.name,
            'operands': [oper.serialize() for oper in self.operands],
            'arguments': self.arguments,
        }


class KpiInitialOperation(KpiOperation):
    def __init__(self, kpi):
        super(KpiInitialOperation, self).__init__(type=KpiOperation.Type.initial)
        self.kpi = kpi


class KpiSet(object):
    @classmethod
    def get_singleton_ok(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.ok)], **kwargs)

    @classmethod
    def get_singleton_warn(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.warning)], **kwargs)

    @classmethod
    def get_singleton_critical(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.critical)], **kwargs)

    @classmethod
    def get_singleton_undetermined(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.undetermined)], **kwargs)

    @classmethod
    def get_singleton_unknown(cls, **kwargs):
        return KpiSet([KpiObject(result=KpiResult.unknown)], **kwargs)

    def __init__(self, objects, origin):
        """
        :type objects: list of KpiObject
        :type origin: KpiOperation
        """
        self.objects = objects
        self.origin = origin

    """
    @classmethod
    def deserialize(cls, data):
        objects = [KpiObject.deserialize(obj_json) for obj_json in data['objects']]
        parents = [KpiSet.deserialize(set_json) for set_json in data['parents']]\
            if data['parents'] is not None else None
        return KpiSet(objects, parents)
    """

    def serialize(self):
        # for obj in self.objects: print obj.serialize() json.dumps(obj.serialize())
        return {
            "objects": [obj.serialize() for obj in self.objects],
            "origin": self.origin.serialize() if self.origin is not None else None,
        }

    def _check_value(self, amount, limit_ok, limit_warn):
        if amount >= limit_ok:
            result = KpiResult.ok
        elif amount >= limit_warn:
            result = KpiResult.warning
        else:
            result = KpiResult.critical
        return result

    def _get_current_kpi(self):
        """
        Get Kpi object from original kpi set. Assumes that parent-chain is valid!
        :rtype : Kpi
        """
        if self.origin.type == KpiOperation.Type.initial:
            return self.origin.kpi
        else:
            kpi = None
            for parent in self.origin.operands:
                kpi = parent._get_current_kpi()
                if kpi is not None:
                    break
            else:
                raise ValueError("Failed to find initial kpi set.")
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

    @property
    def rrd_objects(self):
        """
        :rtype : list of KpiRRDObject
        """
        return [obj for obj in self.objects if isinstance(obj, KpiRRDObject)]

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

        return KpiSet(objects, origin=KpiOperation(KpiOperation.Type.filter, arguments=kwargs, operands=[self]))

    def union(self, kpi_set):
        return KpiSet(self.objects + kpi_set.objects,
                      origin=KpiOperation(KpiOperation.Type.union, operands=[self, kpi_set]))

    __add__ = union

    def at_least(self, num_ok, num_warn, result=KpiResult.ok):
        """
        Check if at_least a number of objects have a certain result.
        """
        if num_warn > num_ok:
            raise ValueError("num_warn is higher than num_ok ({} > {})".format(num_warn, num_ok))

        origin = KpiOperation(KpiOperation.Type.at_least,
                              arguments={'num_ok': num_ok, 'num_warn': num_warn, 'result': result},
                              operands=[self])

        num = sum(1 for obj in self.result_objects if obj.result == result)
        if num > num_ok:
            return KpiSet.get_singleton_ok(origin=origin)
        elif num > num_warn:
            return KpiSet.get_singleton_warn(origin=origin)
        else:
            return KpiSet.get_singleton_critical(origin=origin)

    def aggregate_historic(self, method):
        """
        :param method: "or" or "and"
        """
        origin = KpiOperation(KpiOperation.Type.aggregate_historic,
                              arguments={'method': method},
                              operands=[self])
        if not self.time_line_objects:
            retval = KpiSet.get_singleton_undetermined(origin=origin)
        else:
            # work on copies
            compound_time_line = TimeLineUtils.calculate_compound_time_line(
                method,
                [obj.time_line for obj in self.time_line_objects],
            )

            retval = KpiSet(
                objects=[KpiTimeLineObject(time_line=compound_time_line)],
                origin=origin
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

        return KpiSet(objects=objects,
                      origin=KpiOperation(KpiOperation.Type.get_historic_data, operands=[self]))

    def evaluate_historic(self, ratio_ok, ratio_warn, result=KpiResult.ok):
        """
        Check if up percentage is at least some value
        :type result: KpiResult
        """
        origin = KpiOperation(KpiOperation.Type.evaluate_historic,
                              arguments={'ratio_ok': ratio_ok, 'ratio_warn': ratio_warn},
                              operands=[self])
        if not self.time_line_objects:
            return KpiSet.get_singleton_undetermined(origin=origin)
        else:
            objects = []

            for tl_obj in self.time_line_objects:

                aggregated_tl = TimeLineUtils.aggregate_time_line(tl_obj)

                # also aggregate state types
                amount = sum(v for k, v in aggregated_tl.iteritems()
                             if k[0] == result.get_corresponding_service_enum_value())

                kwargs = tl_obj.get_object_identifier_properties()
                kwargs['result'] = self._check_value(amount, ratio_ok, ratio_warn)
                kwargs['detail'] = aggregated_tl
                if isinstance(tl_obj, KpiServiceObject):
                    obj = KpiServiceDetailObject(**kwargs)
                else:
                    obj = KpiDetailObject(**kwargs)
                objects.append(obj)

            return KpiSet(objects=objects, origin=origin)

    def evaluate(self):
        """
        Calculate "worst" result, i.e. result is critical
        if at least one is critical or else warn if at least one is warn etc.
        """
        # TODO: have parameter: method
        origin = KpiOperation(KpiOperation.Type.evaluate, operands=[self])
        if not self.result_objects:
            return KpiSet.get_singleton_undetermined(origin=origin)
        else:
            aggregated_result = max(obj.result for obj in self.result_objects)
            return KpiSet([KpiObject(result=aggregated_result)], origin=origin)

    def evaluate_rrd(self, limit_ok, limit_warn):
        origin = KpiOperation(KpiOperation.Type.evaluate_rrd,
                              arguments={'limit_ok': limit_ok, 'limit_warn': limit_warn},
                              operands=[self])

        if not self.rrd_objects:
            return KpiSet.get_singleton_undetermined(origin=origin)
        else:
            return KpiSet(
                objects=[
                    KpiRRDObject(
                        rrd_key=rrd_obj.rrd_key,
                        rrd_value=rrd_obj.rrd_value,
                        result=self._check_value(rrd_obj.rrd_value, limit_ok, limit_warn),
                        **rrd_obj.get_object_identifier_properties()
                    ) for rrd_obj in self.rrd_objects
                ],
                origin=origin,
            )

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
                     # logger.warn("Historical obj found but no kpi obj: {} {} {}".format(dev_id, service_id,
                     service_info))
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