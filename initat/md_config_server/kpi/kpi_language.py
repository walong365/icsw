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

from collections import defaultdict
import datetime
from enum import IntEnum, Enum
import pytz

from initat.md_config_server.kpi.kpi_historic import TimeLineUtils
from initat.tools import logging_tools
from initat.cluster.backbone.models.status_history import mon_icinga_log_raw_service_alert_data, \
    mon_icinga_log_raw_host_alert_data
from initat.cluster.backbone.models import mon_check_command, device, \
    cluster_timezone


logger = logging_tools.logging.getLogger("cluster.kpi")


class KpiResult(IntEnum):
    # this is ordered by badness and also same as nagios convention
    # names are same as in status history but lower case
    planned_down = -1
    ok = 0
    warning = 1
    critical = 2
    unknown = 3
    undetermined = 4

    def __unicode__(self):
        return self.name.capitalize().replace("_", " ")

    def get_numeric_icinga_service_state(self):
        return self.value

    @classmethod
    def from_numeric_icinga_host_state(cls, num):
        # NOTE: these are different than for services!
        if num == 0:  # UP
            return KpiResult.ok
        elif num == 1:  # DOWN
            return KpiResult.critical
        elif num == 2:  # UNREACHABLE
            return KpiResult.warning
        else:
            return cls.from_icinga_service_status(num)

    @classmethod
    def from_numeric_icinga_service_state(cls, num):
        if num == -1:  # icsw-only
            return KpiResult.planned_down
        elif num == 0:
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

    @classmethod
    def from_icinga_service_status(cls, state):
        return _icinga_service_to_kpi_state_map[state]

    @classmethod
    def from_icinga_host_status(cls, state):
        return _icinga_host_to_kpi_state_map[state]

    def get_corresponding_service_enum_value(self):
        return _kpi_to_icinga_service_state_map[self]

    def get_corresponding_host_enum_value(self):
        return _kpi_to_icinga_host_state_map[self]


_kpi_to_icinga_service_state_map = {
    KpiResult.planned_down: mon_icinga_log_raw_service_alert_data.STATE_PLANNED_DOWN,
    KpiResult.ok: mon_icinga_log_raw_service_alert_data.STATE_OK,
    KpiResult.warning: mon_icinga_log_raw_service_alert_data.STATE_WARNING,
    KpiResult.critical: mon_icinga_log_raw_service_alert_data.STATE_CRITICAL,
    KpiResult.unknown: mon_icinga_log_raw_service_alert_data.STATE_UNKNOWN,
    KpiResult.undetermined: mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED,
}

_icinga_service_to_kpi_state_map = {v: k for k, v in _kpi_to_icinga_service_state_map.iteritems()}

_kpi_to_icinga_host_state_map = {
    KpiResult.planned_down: mon_icinga_log_raw_host_alert_data.STATE_PLANNED_DOWN,
    KpiResult.ok: mon_icinga_log_raw_host_alert_data.STATE_UP,
    KpiResult.warning: mon_icinga_log_raw_host_alert_data.STATE_UNREACHABLE,
    KpiResult.critical: mon_icinga_log_raw_host_alert_data.STATE_DOWN,
    KpiResult.unknown: mon_icinga_log_raw_host_alert_data.STATE_UNKNOWN,
    KpiResult.undetermined: mon_icinga_log_raw_host_alert_data.STATE_UNDETERMINED,
}

_icinga_host_to_kpi_state_map = {v: k for k, v in _kpi_to_icinga_host_state_map.iteritems()}


class KpiObject(object):
    def __init__(self, result=None, host_name=None, host_pk=None, kpi_id=None):
        """
        :type host_name: str | unicode
        :type host_pk: int
        """
        if (host_name is None) != (host_pk is None):
            raise ValueError("host_name is {} but host_pk is {}".format(host_name, host_pk))

        self.kpi_id = kpi_id if kpi_id is not None else id(self)

        self.result = result if isinstance(result, (KpiResult, NoneType)) \
            else KpiResult.from_numeric_icinga_service_state(result)
        self.host_name = host_name
        self.host_pk = host_pk

        # this is actually a list of strings
        self.device_category = KpiGlobals.device_category_cache[self.host_pk]

    """
    @classmethod
    def deserialize(cls, data):
        return KpiObject(**data)
    """

    def serialize(self):
        # we serialize for the client to show something, not for a functional representation
        return {
            'kpi_id': self.kpi_id,
            'result': None if self.result is None else unicode(self.result),
            'host_name': self.host_name,
            'host_pk': self.host_pk,
            'device_category': ", ".join(self.device_category),
        }

    def is_service(self):
        return False

    def matches_id(self, ident):
        return self.host_pk == ident

    def get_machine_object_id_properties(self):
        """Returns all properties of the object which are necessary to identify the object"""
        # TODO: refactor this, see get_machine_object_id_type
        return self.host_pk

    class IdType(Enum):
        service = 1
        device = 2
        rrd = 3

    @classmethod
    def get_machine_object_id_type(cls, ident):
        # TODO: refactor this system to something which explicitly says what it represents
        # for this, get_machine_object_id_properties must be changed
        # the current system assumes that there are no rrd-objects which are service-objects
        try:
            obj_len = len(ident)
        except TypeError:
            obj_len = None
        if obj_len == 3:
            return cls.IdType.service
        elif obj_len == 2:
            return cls.IdType.rrd
        elif isinstance(ident, (int, long)):
            return cls.IdType.device
        else:
            raise ValueError()

    def get_full_object_id_properties(self):
        """Returns all properties of the object which can be passed to KpiObject constructors
        (including respective subclasses)"""
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

# rrd_id, rrd_name rrd_value, host
# result, host
# result, host, serv_id, service_info
# host (historic host)
# host, serv_id, service_info (historic service)
# host, serv_id, service_info, time line
# compound time line
# result
# detail


class KpiDetailObject(KpiObject):
    """Kpi Object with some data attached"""
    def __init__(self, time_line, **kwargs):
        if time_line is None:
            raise ValueError("no detail data set")
        super(KpiDetailObject, self).__init__(**kwargs)
        self.time_line = time_line

    def __repr__(self, child_repr=""):
        return super(KpiDetailObject, self).__repr__(child_repr=child_repr + ";time_line:{}".format(self.time_line))

    def serialize(self):
        aggr_tl = TimeLineUtils.merge_state_types(
            self.time_line,
            KpiGlobals.current_kpi.soft_states_as_hard_states,
        )
        return dict(
            aggregated_tl={unicode(k): v for k, v in aggr_tl.iteritems()},
            **super(KpiDetailObject, self).serialize()
        )


class KpiRRDObject(KpiObject):
    """Kpi Object with rrd data"""
    def __init__(self, rrd_id, rrd_name, rrd_value, **kwargs):
        if rrd_id is None:
            raise ValueError("rrd_id is None")
        if rrd_name is None:
            raise ValueError("rrd_name is None")
        if rrd_value is None:
            raise ValueError("rrd_value is None")
        super(KpiRRDObject, self).__init__(**kwargs)
        self.rrd_id = rrd_id
        self.rrd_name = rrd_name
        self.rrd_value = rrd_value

    def __repr__(self, child_repr=""):
        return super(KpiRRDObject, self).__repr__(child_repr=child_repr +
                                                  "rrd:{}:{}".format(self.rrd_id, self.rrd_value))

    def matches_id(self, ident):
        try:
            return ident[1] == self.rrd_id and super(KpiRRDObject, self).matches_id(ident[0])
        except TypeError:
            return False

    def get_machine_object_id_properties(self):
        return (
            super(KpiRRDObject, self).get_machine_object_id_properties(),
            self.rrd_id,
        )

    def get_full_object_id_properties(self):
        return dict(
            rrd_id=self.rrd_id,
            rrd_name=self.rrd_name,
            rrd_value=self.rrd_value,
            **super(KpiRRDObject, self).get_full_object_id_properties()
        )

    def serialize(self):
        return dict(
            rrd_id=self.rrd_id,
            rrd_name=self.rrd_name,
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

            # this is actually a list of strings
            self.monitoring_category = KpiGlobals.mcc_category_cache[mcc.pk]

        self.mcc = mcc  # saved for convenience, but use other attributes except mcc is needed specifically

    def __repr__(self, child_repr=""):
        my_repr = ";service:{}:{}".format(self.check_command if self.check_command is not None else self.service_id,
                                          self.service_info)
        return super(KpiServiceObject, self).__repr__(child_repr=child_repr + my_repr)

    def serialize(self):
        return dict(
            service_name=self.check_command,
            service_info=self.service_info,
            monitoring_category=", ".join(self.monitoring_category),
            check_command=self.check_command,
            check_command_description=self.check_command_description,
            config=self.config,
            config_description=self.config_description,
            **super(KpiServiceObject, self).serialize()
        )

    def is_service(self):
        return True

    def matches_id(self, ident):
        try:
            return self.service_id == ident[1] and \
                self.service_info == ident[2] and \
                super(KpiServiceObject, self).matches_id(ident[0])
        except TypeError:
            return False

    def get_machine_object_id_properties(self):
        return (
            super(KpiServiceObject, self).get_machine_object_id_properties(),
            self.service_id,
            self.service_info,
        )

    def get_full_object_id_properties(self):
        return dict(
            mcc=self.mcc,
            service_id=self.service_id,
            service_info=self.service_info,
            **super(KpiServiceObject, self).get_full_object_id_properties()
        )


class KpiTimeLineObject(KpiObject):
    """Kpi Object which has a time line"""
    def __init__(self, time_line=None, **kwargs):
        if time_line is None:
            raise ValueError("time_line is None")
        super(KpiTimeLineObject, self).__init__(**kwargs)
        self.time_line = time_line

    def serialize(self):
        aggr_tl = TimeLineUtils.merge_state_types(
            TimeLineUtils.aggregate_time_line(self.time_line),
            KpiGlobals.current_kpi.soft_states_as_hard_states,
        )
        return dict(
            aggregated_tl={unicode(k): v for k, v in aggr_tl.iteritems()},
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
        exclude = 10

    def __init__(self, operation_type, operands=None, arguments=None):
        if arguments is None:
            arguments = {}
        if operands is None:  # only for initial and possibly specially constructed sets
            operands = []
        self.type = operation_type
        self.operands = operands
        self.arguments = arguments

    @property
    def type_for_client(self):
        if self.type == self.Type.union:
            return "+"
        else:
            return self.type.name

    def serialize(self):
        return {
            'type': self.type_for_client,
            'operands': [oper.serialize() for oper in self.operands],
            'arguments': self.arguments,
        }


class KpiGlobals(object):
    # these are set during the execution of a kpi

    current_kpi = None

    @classmethod
    def _init(cls, device_category_cache, mcc_category_cache):
        # use this pattern to make sure to always set all vars
        cls.device_category_cache = device_category_cache
        cls.mcc_category_cache = mcc_category_cache

    @classmethod
    def set_context(cls):
        class CategoryCache(dict):
            def __init__(self, model):
                super(CategoryCache, self).__init__()
                self.model = model

            def __getitem__(self, obj_pk):
                # obj_pk may be None
                try:
                    return super(CategoryCache, self).__getitem__(obj_pk)
                except KeyError:
                    try:
                        cats = self.model.objects.get(pk=obj_pk).categories.all()
                    except self.model.DoesNotExist:
                        cats = []
                    retval = self[obj_pk] = [cat.name for cat in cats]
                    return retval

        cls._init(
            device_category_cache=CategoryCache(device),
            mcc_category_cache=CategoryCache(mon_check_command),
        )

    @classmethod
    def clear_context(cls):
        cls._init(None, None)


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

    def __init__(self, objects=None, origin=None):
        """
        :type objects: list of KpiObject
        :type origin: KpiOperation | None
        """
        self.objects = objects if objects is not None else []
        self.origin = origin if origin else KpiOperation(KpiOperation.Type.initial)

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

    def _check_value(self, amount, limit_ok, limit_warn, method='at least'):
        if method == 'at least':
            if limit_warn is not None and limit_ok < limit_warn:
                raise RuntimeError("With at least comparisons, limit_ok must be greater than or equal to limit_warn")

            if amount >= limit_ok:
                result = KpiResult.ok
            elif limit_warn is not None and amount >= limit_warn:
                result = KpiResult.warning
            else:
                result = KpiResult.critical
        elif method == 'at most':
            if limit_warn is not None and limit_ok > limit_warn:
                raise RuntimeError("With at least comparisons, limit_ok must be lesser than or equal to limit_warn")

            if amount <= limit_ok:
                result = KpiResult.ok
            elif limit_warn is not None and amount <= limit_warn:
                result = KpiResult.warning
            else:
                result = KpiResult.critical
        else:
            raise ValueError("Invalid comparison method: '{}'. Supported methods are 'at least' or 'at most'.")

        return result

    def _filter_impl(self, parameters, positive):
        """
        Implementation of filter and exclude
        :param parameters: kwargs of actual filter/exclude fun
        :param positive: True for filter, False for exclude
        """
        objects = self.objects

        def check_match(match_check_fun, obj):
            # apply match_check_fun to obj
            if isinstance(obj, (list, tuple)):
                # for convenience in specifying kpis:
                return any(match_check_fun(obj_entry) for obj_entry in obj)
            else:
                return match_check_fun(obj)

        for k, v in parameters.iteritems():
            # match_check_fun is actually 'equality'-testing
            if isinstance(v, basestring):
                match_re = re.compile(v)

                def create_matcher(match_re=match_re):  # force closure
                    return lambda x: x is not None and match_re.search(x)
                match_check_fun = create_matcher()
            else:
                match_check_fun = lambda x: x == v

            if positive:
                objects = [
                    obj for obj in objects if
                    check_match(match_check_fun, getattr(obj, k, None))
                ]
            else:
                objects = [
                    obj for obj in objects if
                    not check_match(match_check_fun, getattr(obj, k, None))
                ]
        return objects

    ########################################
    # data accessors
    #

    def __iter__(self):
        return iter(self.objects)

    def __len__(self):
        return len(self.objects)

    @property
    def result_objects(self):
        """
        :rtype : list of KpiObject
        """
        return [obj for obj in self.objects if obj.result is not None]

    @property
    def host_objects(self):
        """
        :rtype : list of KpiObject
        """
        return [obj for obj in self.objects if obj.host_pk is not None]

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

    def get_by_id(self, ident):
        """
        :rtype : list of KpiObject
        """
        return [obj for obj in self.objects if obj.matches_id(ident)]

    ########################################
    # proper kpi language elements
    #

    def filter(self, **kwargs):
        """
        Return all objects which have the required properties.
        Matches on all properties. Interprets strings as regexp /.*thestring.*/.
        If properties are lists or tuples, checks if any of them match.
        """
        objects = self._filter_impl(kwargs, positive=True)
        return KpiSet(objects, origin=KpiOperation(KpiOperation.Type.filter, arguments=kwargs, operands=[self]))

    def exclude(self, **kwargs):
        """
        Inverse to `filter`. Returns all objects which `filter` removes.
        This invariant holds for any kpi_set and params (modulo ordering):
        kpi_set == kpi_set.filter(params) + kpi_set.exclude(params)
        """
        objects = self._filter_impl(kwargs, positive=False)
        return KpiSet(objects, origin=KpiOperation(KpiOperation.Type.exclude, arguments=kwargs, operands=[self]))

    def union(self, kpi_set):
        return KpiSet(self.objects + kpi_set.objects,
                      origin=KpiOperation(KpiOperation.Type.union, operands=[self, kpi_set]))

    __add__ = union

    def at_least(self, num_ok, num_warn=None, result=KpiResult.ok):
        """
        Check if at_least a number of objects have at least a certain result
        (i.e. if checking for e.g. warning, ok is included).
        If num_warn is None, the result can only be ok or critical.
        :type result: KpiResult
        """
        if num_warn is not None and num_warn > num_ok:
            raise ValueError("num_warn is higher than num_ok ({} > {})".format(num_warn, num_ok))

        origin = KpiOperation(KpiOperation.Type.at_least,
                              arguments={'num_ok': num_ok, 'num_warn': num_warn, 'result': unicode(result)},
                              operands=[self])

        num = sum(1 for obj in self.result_objects if obj.result <= result)

        if num >= num_ok:
            return KpiSet.get_singleton_ok(origin=origin)
        elif num_warn is not None and num >= num_warn:
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

    def historic_best(self):
        return self.aggregate_historic(method='best')

    def historic_worst(self):
        return self.aggregate_historic(method='worst')

    def get_historic_data(self, start=None, end=None):
        """
        Returns a KpiSet containing historic data for each KpiObject in the original set which has historic data.
        :param start: Desired start for historic data. Defaults to global kpi time range start
        :param end: Desired end for historic data. Defaults to global kpi time range end
        """
        relevant_obj_identifiers = [obj.get_machine_object_id_properties() for obj in self.host_objects]

        objects = []
        if relevant_obj_identifiers:
            kpi_global_start, kpi_global_end = KpiGlobals.current_kpi.get_time_range()

            # help user by fixing their timezones
            def fix_input(moment):
                # moment might be date
                if not isinstance(moment, datetime.datetime):
                    moment = datetime.datetime(moment.year, moment.month, moment.day)
                if moment.tzinfo is not None:
                    return moment
                else:
                    return moment.replace(tzinfo=pytz.utc)

            start = fix_input(start) if start is not None else kpi_global_start
            end = fix_input(end) if end is not None else kpi_global_end

            if start < kpi_global_start:
                raise RuntimeError(
                    "Start date for get_historic_data() is earlier than KPI time range start ({} < {})".format(
                        start, kpi_global_start,
                    )
                )

            if end > kpi_global_end:
                raise RuntimeError(
                    "End date for get_historic_data() is later than KPI time range end ({} > {})".format(
                        end, kpi_global_end,
                    )
                )

            if start == end:
                raise RuntimeError("Same start and end date for get_historic_data(): {}".format(start))

            if start > end:
                raise RuntimeError("Start date for get_historic_data() is later than end date ({} > {})".format(
                    start, end
                ))

            # have to sort by service and device ids
            idents_by_type = defaultdict(lambda: set())
            for ident in relevant_obj_identifiers:
                idents_by_type[KpiObject.get_machine_object_id_type(ident)].add(ident)

            time_lines = {}

            if KpiObject.IdType.service in idents_by_type:
                time_lines.update(
                    TimeLineUtils.calculate_time_lines(idents_by_type[KpiObject.IdType.service], is_host=False,
                                                       start=start, end=end)
                )
            if KpiObject.IdType.device in idents_by_type:
                time_lines.update(
                    TimeLineUtils.calculate_time_lines(idents_by_type[KpiObject.IdType.device], is_host=True,
                                                       start=start, end=end)
                )

            for ident, time_line in time_lines.iteritems():
                id_objs = self.get_by_id(ident)
                if id_objs:
                    obj_id = KpiObject.get_machine_object_id_type(ident)
                    if obj_id == KpiObject.IdType.service:
                        kpi_klass = KpiServiceTimeLineObject
                    elif obj_id == KpiObject.IdType.device:
                        kpi_klass = KpiTimeLineObject
                    else:
                        kpi_klass = None  # this does not happen as only service and device objects are added

                    if kpi_klass:
                        objects.append(
                            kpi_klass(
                                time_line=time_line,
                                **id_objs[0].get_full_object_id_properties()
                            )
                        )
                else:
                    print ("Historical obj found but no kpi obj: {} {} {}".format(ident))
                    # TODO: logging is broken in this context

        return KpiSet(objects=objects,
                      origin=KpiOperation(KpiOperation.Type.get_historic_data, operands=[self]))

    # noinspection PyUnresolvedReferences
    def evaluate_historic(self, ratio_ok, ratio_warn=None, result=KpiResult.ok, method='at least',
                          discard_planned_downtimes=True):
        """
        Check if up percentage is at least some value
        :type result: KpiResult
        :param method: 'at least' or 'at most'
        """
        if ratio_ok > 1.0:
            raise ValueError("ratio_ok is greater than 1.0: {}. ".format(ratio_ok) +
                             "Please specify ratio_ok as floating point number between 0.0 and 1.0.")
        if ratio_warn is not None and ratio_warn > 1.0:
            raise ValueError("ratio_warn is greater than 1.0: {}. ".format(ratio_warn) +
                             "Please specify ratio_warn as floating point number between 0.0 and 1.0.")
        origin = KpiOperation(KpiOperation.Type.evaluate_historic,
                              arguments={'ratio_ok': ratio_ok, 'ratio_warn': ratio_warn, 'result': unicode(result),
                                         'method': method},
                              operands=[self])
        if not self.time_line_objects:
            return KpiSet.get_singleton_undetermined(origin=origin)
        else:
            objects = []

            for tl_obj in self.time_line_objects:

                aggregated_tl = TimeLineUtils.aggregate_time_line(tl_obj.time_line)

                # also aggregate state types
                ratio = sum(v for k, v in aggregated_tl.iteritems()
                            if k[0] <= result)

                if discard_planned_downtimes:
                    ratio_planned_down = sum(v for k, v in aggregated_tl.iteritems()
                                             if k[0] == KpiResult.planned_down)
                    # ignore ratio_planned_down
                    try:
                        ratio /= (1 - ratio_planned_down)
                    except ZeroDivisionError:
                        # ratio_planned_down is 1, always there
                        ratio = 0

                kwargs = tl_obj.get_full_object_id_properties()
                kwargs['result'] = self._check_value(ratio, ratio_ok, ratio_warn, method)
                kwargs['time_line'] = aggregated_tl
                if isinstance(tl_obj, KpiServiceObject):
                    obj = KpiServiceDetailObject(**kwargs)
                else:
                    obj = KpiDetailObject(**kwargs)
                objects.append(obj)

            return KpiSet(objects=objects, origin=origin)

    def worst(self):
        """
        Calculate "worst" result, i.e. result is critical
        if at least one is critical or else warn if at least one is warn etc.
        """
        return self.evaluate(method='worst')

    def best(self):
        """
        Calculate "best" result, i.e. result is ok
        if at least one is ok or else warn if at least one is warn etc.
        """
        return self.evaluate(method='best')

    def evaluate(self, method='worst'):
        # usually called through either worst() or best()
        if method not in ('worst', 'best'):
            raise ValueError("method must be either 'worst' or 'best', not {}".format(method))
        origin = KpiOperation(KpiOperation.Type.evaluate,
                              arguments={'method': method},
                              operands=[self])
        if not self.result_objects:
            return KpiSet.get_singleton_undetermined(origin=origin)
        else:
            aggr_fun = max if method == 'worst' else min
            aggregated_result = aggr_fun(obj.result for obj in self.result_objects)
            return KpiSet([KpiObject(result=aggregated_result)], origin=origin)

    def evaluate_rrd(self, limit_ok, limit_warn=None, method='at least'):
        """
        :param method: 'at least' or 'at most'
        """
        origin = KpiOperation(KpiOperation.Type.evaluate_rrd,
                              arguments={'limit_ok': limit_ok, 'limit_warn': limit_warn, 'method': method},
                              operands=[self])

        if not self.rrd_objects:
            return KpiSet.get_singleton_undetermined(origin=origin)
        else:
            # construct same RRD-objects but with results
            return KpiSet(
                objects=[
                    KpiRRDObject(
                        result=self._check_value(rrd_obj.rrd_value, limit_ok, limit_warn, method),
                        **rrd_obj.get_full_object_id_properties()
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
        num_objs_to_show = 3
        return "KpiSet({})".format(self.objects if len(self.objects) <= num_objs_to_show else
                                   repr(self.objects[:num_objs_to_show]) +
                                   "... ({} more)".format(len(self.objects) - num_objs_to_show))


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