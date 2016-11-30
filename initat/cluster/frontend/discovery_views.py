# Copyright (C) 2015-2016 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
# -*- coding: utf-8 -*-
#
from __future__ import print_function, unicode_literals

import collections
import json

import bson.json_util
import dateutil.parser
import pymongo
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from pymongo.errors import PyMongoError

from initat.cluster.backbone.models import device, DispatcherLink, DispatcherSetting, user
from initat.cluster.backbone.serializers import DispatcherLinkSerializer
from initat.cluster.frontend.rest_views import rest_logging
from initat.tools.mongodb import MongoDbConnector


class GetEventLogDeviceInfo(View):
    """Returns which logs the given devices have"""

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        device_pks = json.loads(request.GET['device_pks'])
        ret = {}
        mongo = MongoDbConnector()
        if not mongo.connected:
            ret = MongoDbConnector.json_error_dict()
        else:
            try:
                _wmi_res = mongo.event_log_db.wmi_event_log.aggregate(
                    [
                        {
                            '$group': {
                                '_id': {
                                    'device_pk': '$device_pk',
                                }
                            }
                        }
                    ]
                )
                devices_with_wmi = {entry['_id']['device_pk'] for entry in _wmi_res}

                _ipmi_res = mongo.event_log_db.ipmi_event_log.aggregate(
                    [
                        {
                            '$group': {
                                '_id': {
                                    'device_pk': '$device_pk',
                                }
                            }
                        }
                    ]
                )
                devices_with_ipmi = {entry['_id']['device_pk'] for entry in _ipmi_res}

                _syslog_res = mongo.event_log_db.system_log.aggregate(
                    [
                        {
                            '$group': {
                                '_id': {
                                    'device_pk': '$device_pk',
                                }
                            }
                        }
                    ]
                )
                devices_with_syslog = {entry["_id"]["device_pk"] for entry in _syslog_res}

                for entry in device.objects.filter(pk__in=device_pks):
                    capabilities = []
                    if entry.pk in devices_with_ipmi:
                        capabilities.append("ipmi")
                    if entry.pk in devices_with_wmi:
                        capabilities.append("wmi")
                    if entry.pk in devices_with_syslog:
                        capabilities.append("syslog")
                    ret[entry.pk] = {
                        'name': entry.full_name,
                        'capabilities': capabilities,
                    }
            except PyMongoError as e:
                ret = MongoDbConnector.json_error_dict()

        return HttpResponse(json.dumps(ret), content_type='application/json')


class GetEventLog(View):
    """Returns actual log data (all kinds of logs currently)"""

    class EventLogResult(
        collections.namedtuple(
            "EventLogResult",
            [
                "entries", "keys_ordered", "grouping_keys", "total_num",
                "mode_specific_parameters"
            ]
        )
    ):
        # this pattern allows for default values:
        def __new__(cls, grouping_keys=None, mode_specific_parameters=None, *args, **kwargs):
            return super(
                GetEventLog.EventLogResult,
                cls
            ).__new__(
                cls,
                grouping_keys=grouping_keys,
                mode_specific_parameters=mode_specific_parameters, *args, **kwargs
            )

    @classmethod
    def _parse_datetime(cls, datetime_str):
        try:
            _dt = dateutil.parser.parse(datetime_str)
        except ValueError as e:
            raise RuntimeError("Failed to parse date time {}: {}".format(datetime_str, e))
        else:
            return _dt

    @classmethod
    def _paginate_list(cls, l, skip, limit):
        return l[skip:][:limit]

    @classmethod
    def rename_column_of_dict_list(self, l, old_name, new_name):
        for entry in l:
            entry[new_name] = entry[old_name]
            del entry[old_name]

    class GetIpmiEventLog(object):
        def __init__(self):
            self.mongo = MongoDbConnector()

        def __call__(self, device_pks, pagination_skip, pagination_limit,
                     filter_str=None, from_date=None, to_date=None, group_by=None):

            self.from_date_parsed = None if from_date is None else GetEventLog._parse_datetime(from_date)
            self.to_date_parsed = None if to_date is None else GetEventLog._parse_datetime(to_date)

            if group_by is None:
                return self._regular_query(device_pks, pagination_skip, pagination_limit, filter_str)
            else:
                return self._group_by_query(device_pks, pagination_skip, pagination_limit, filter_str, group_by)

        def _add_date_constraints(self, query_obj):
            if self.from_date_parsed is not None:
                query_obj.setdefault('creation_date', {})['$gte'] = self.from_date_parsed
            if self.to_date_parsed is not None:
                query_obj.setdefault('creation_date', {})['$lte'] = self.to_date_parsed

        def _is_reasonable_grouping_key(self, key):
            return key in ('Record Type', "Sensor Type", "Event Direction", "Record Type", "EvM Revision", "Event Type",
                           "Description", "Event Interpretation")

        def _get_match_obj(self, device_pks, filter_str):
                _match_obj = {
                    'device_pk': {'$in': device_pks},
                }
                if filter_str is not None:
                    _match_obj["$text"] = {'$search': filter_str}

                self._add_date_constraints(_match_obj)
                return _match_obj

        def _group_by_query(self, device_pks, pagination_skip, pagination_limit, filter_str, group_by):
            aggregate_pipeline = [
                {
                    '$match': self._get_match_obj(device_pks, filter_str)
                },
                {
                    '$group': {
                        '_id': {'$arrayElemAt': ['$sections', 1]},
                        'c': {'$sum': 1},
                    }
                },
                {
                    '$group': {
                        '_id': '$_id.{}'.format(group_by),
                        'Count': {'$sum': '$c'},
                    }
                }
            ]

            entries = self.mongo.event_log_db.ipmi_event_log.aggregate(aggregate_pipeline)

            result = list(entries)  # exhaust cursor
            total_num = len(result)
            result_paginated = GetEventLog._paginate_list(result, pagination_skip, pagination_limit)
            # results now are of this form: {'_id': <group_by_field_value>, 'count': <num>}
            GetEventLog.rename_column_of_dict_list(result_paginated, old_name='_id', new_name=group_by)
            keys_ordered = [group_by, 'Count']

            return GetEventLog.EventLogResult(total_num=total_num, keys_ordered=keys_ordered, entries=result_paginated)

        def _regular_query(self, device_pks, pagination_skip, pagination_limit, filter_str=None):
            projection_obj = {
                'sections': 1,
                'device_pk': 1,
                'keys_ordered': 1,
            }
            query_obj = self._get_match_obj(device_pks, filter_str)

            sort_obj = [('creation_date', pymongo.DESCENDING)]
            entries = self.mongo.event_log_db.ipmi_event_log.find(
                query_obj,
                projection_obj,
                sort=sort_obj,
            )

            total_num = entries.count()

            entries.skip(pagination_skip)
            entries.limit(pagination_limit)

            entry_keys = collections.OrderedDict()  # we only use it as set

            device_name_lut = {dev[0]: dev[1] for dev in device.objects.values_list('pk', 'name')}

            # merge ipmi sections into one dict for each entry
            result_merged = []
            grouping_keys = collections.OrderedDict()  # only set again

            include_device_info = len(device_pks) > 1

            for entry in entries:  # exhaust cursor
                # remove internal info
                for key in entry['keys_ordered']:
                    if key != '__icsw_ipmi_section_type':
                        entry_keys[key] = None  # add k to ordered set

                entry_sections_merged = {}
                for section_num, section in enumerate(entry['sections']):
                    # filter internal fields
                    for k, v in section.iteritems():
                        if k != '__icsw_ipmi_section_type':
                            entry_sections_merged[k] = v
                            # support grouping for section 1 (0 is local timestamp, so 1 is first ipmi)
                            if section_num == 1 and self._is_reasonable_grouping_key(k):
                                grouping_keys[k] = None

                if include_device_info:
                    entry_sections_merged['Device'] = device_name_lut.get(entry['device_pk'], "Unknown device")

                result_merged.append(entry_sections_merged)

            keys_ordered = entry_keys.keys()
            if include_device_info:
                keys_ordered = ['Device'] + keys_ordered

            return GetEventLog.EventLogResult(
                total_num=total_num,
                keys_ordered=keys_ordered,
                entries=result_merged,
                grouping_keys=grouping_keys.keys()
            )

    class GetSystemLogEventLog(object):
        def __init__(self, device_pks, pagination_skip, pagination_limit,
                     group_by=None, filter_str=None, from_date=None, to_date=None):
            self.device_pks = device_pks
            self.pagination_skip = pagination_skip
            self.pagination_limit = pagination_limit
            self.group_by = group_by
            self.filter_str = filter_str
            self.from_date = from_date
            self.to_date = to_date

            self.mongo = MongoDbConnector()

        def __call__(self,):
            # if self.group_by:
            #     return self._group_by_query()
            # else:
            return self._regular_query()

        def _create_match_obj(self):
            query_obj = {
                'device_pk': {'$in': self.device_pks},
            }
            if self.filter_str is not None:
                query_obj["$text"] = {'$search': self.filter_str}
            if self.from_date is not None:
                query_obj.setdefault('line_datetime', {})['$gte'] = GetEventLog._parse_datetime(self.from_date)
            if self.to_date is not None:
                query_obj.setdefault('line_datetime', {})['$lte'] = GetEventLog._parse_datetime(self.to_date)
            print("Q=", query_obj)
            return query_obj

        def _regular_query(self):
            query_obj = self._create_match_obj()

            projection_obj = {
                'line_id': 1,
                "line_datetime": 1,
                'device_pk': 1,
                "text": 1,
                "facility": 1,
                "priority": 1,
                "hostname": 1,
                "tag": 1,
            }
            sort_obj = [('time_generated', pymongo.DESCENDING), ('record_number', pymongo.DESCENDING)]
            entries = self.mongo.event_log_db.system_log.find(query_obj, projection_obj, sort=sort_obj)
            total_num = entries.count()
            entries.skip(self.pagination_skip)
            entries.limit(self.pagination_limit)

            include_device_info = len(self.device_pks) > 1
            device_name_lut = {
                dev[0]: dev[1] for dev in device.objects.values_list('pk', 'name')
            }

            result = []
            keys = set()
            for entry in entries:  # exhaust cursor
                # entry = db_row['entry']
                keys.update(entry.iterkeys())

                entry["line_datetime"] = entry["line_datetime"].strftime("%Y-%m-%d %H:%M:%S")
                if include_device_info:
                    entry['Device'] = device_name_lut.get(entry['device_pk'])
                result.append(entry)

            mode_specific_parameters = {}

            grouping_keys = [k for k in keys if self._is_reasonable_grouping_key(k)]

            if include_device_info:
                keys = ['Device'] + list(keys)

            return GetEventLog.EventLogResult(
                total_num=total_num, keys_ordered=keys, entries=result, grouping_keys=grouping_keys,
                mode_specific_parameters=mode_specific_parameters
            )

        def _is_reasonable_grouping_key(self, key):
            return key in ()

    class GetWmiEventLog(object):
        def __init__(self, device_pks, pagination_skip, pagination_limit,
                     group_by=None, filter_str=None, from_date=None, to_date=None, logfile=None):
            self.device_pks = device_pks
            self.pagination_skip = pagination_skip
            self.pagination_limit = pagination_limit
            self.group_by = group_by
            self.filter_str = filter_str
            self.from_date = from_date
            self.to_date = to_date
            self.logfile = logfile

            self.mongo = MongoDbConnector()

        def _is_reasonable_grouping_key(self, key):
            return key in ("Category", "ComputerName", "CategoryString", "EventCode", "SourceName", "User", "Logfile",
                           "Type", "EventIdentifier")

        def _group_by_query(self):
            aggregate_pipeline = [
                {
                    '$match': self._create_match_obj()
                },
                {
                    '$group': {
                        '_id': '$entry.{}'.format(self.group_by),
                        'Count': {'$sum': 1},
                    }
                }
            ]

            entries = self.mongo.event_log_db.wmi_event_log.aggregate(aggregate_pipeline)

            result = list(entries)  # exhaust cursor
            total_num = len(result)
            result_paginated = GetEventLog._paginate_list(result, self.pagination_skip, self.pagination_limit)
            GetEventLog.rename_column_of_dict_list(result_paginated, old_name='_id', new_name=self.group_by)
            keys_ordered = [self.group_by, 'Count']
            mode_specific_parameters = self._get_mode_specific_parameters()
            return GetEventLog.EventLogResult(total_num=total_num, keys_ordered=keys_ordered, entries=result_paginated,
                                              mode_specific_parameters=mode_specific_parameters)

        def _regular_query(self):
            query_obj = self._create_match_obj()

            projection_obj = {
                'entry': 1,
                'device_pk': 1,
            }
            sort_obj = [('time_generated', pymongo.DESCENDING), ('record_number', pymongo.DESCENDING)]
            entries = self.mongo.event_log_db.wmi_event_log.find(query_obj, projection_obj, sort=sort_obj)
            total_num = entries.count()
            entries.skip(self.pagination_skip)
            entries.limit(self.pagination_limit)

            include_device_info = len(self.device_pks) > 1
            device_name_lut = {dev[0]: dev[1] for dev in device.objects.values_list('pk', 'name')}

            result = []
            keys = set()
            for db_row in entries:  # exhaust cursor
                entry = db_row['entry']
                keys.update(entry.iterkeys())

                if include_device_info:
                    entry['Device'] = device_name_lut.get(db_row['device_pk'])
                result.append(entry)

            mode_specific_parameters = self._get_mode_specific_parameters()

            if self.logfile is None:
                grouping_keys = [k for k in keys if self._is_reasonable_grouping_key(k)]
            else:
                grouping_keys = None

            if include_device_info:
                keys = ['Device'] + list(keys)

            return GetEventLog.EventLogResult(
                total_num=total_num,
                keys_ordered=keys,
                entries=result,
                grouping_keys=grouping_keys,
                mode_specific_parameters=mode_specific_parameters
            )

        def __call__(self,):
            if self.group_by:
                return self._group_by_query()
            else:
                return self._regular_query()

        def _get_mode_specific_parameters(self):
            logfiles = set()
            for logfile_entry in self.mongo.event_log_db.wmi_logfile.find({'device_pk': {'$in': self.device_pks}}):
                logfiles.update(logfile_entry['logfiles'])
            mode_specific_parameters = {
                'logfiles': list(logfiles),
            }
            return mode_specific_parameters

        def _create_match_obj(self):
            query_obj = {
                'device_pk': {'$in': self.device_pks},
            }
            if self.logfile is not None:
                query_obj['logfile_name'] = self.logfile
            if self.filter_str is not None:
                query_obj["$text"] = {'$search': self.filter_str}
            if self.from_date is not None:
                query_obj.setdefault('time_generated', {})['$gte'] = GetEventLog._parse_datetime(self.from_date)
            if self.to_date is not None:
                query_obj.setdefault('time_generated', {})['$lte'] = GetEventLog._parse_datetime(self.to_date)
            return query_obj

    @method_decorator(login_required)
    @rest_logging
    def post(self, request, *args, **kwargs):
        # NOTE: currently, this list always contains one entry
        device_pks = json.loads(request.POST['device_pks'])
        pagination_skip = int(request.POST.get('pagination_skip'))
        pagination_limit = int(request.POST.get('pagination_limit'))

        # misc additional parameters passed directly to handler functions
        query_parameters = json.loads(request.POST['query_parameters'])

        mode = request.POST['mode']

        if mode == 'wmi':
            # a = time.time()
            event_log_result = GetEventLog.GetWmiEventLog(
                device_pks,
                pagination_skip,
                pagination_limit,
                **query_parameters
            )()
            # print 'took', time.time() - a

        elif mode == 'ipmi':
            event_log_result = self.__class__.GetIpmiEventLog()(
                device_pks,
                pagination_skip,
                pagination_limit,
                **query_parameters
            )

        elif mode == "syslog":
            event_log_result = GetEventLog.GetSystemLogEventLog(
                device_pks,
                pagination_skip,
                pagination_limit,
                **query_parameters
            )()
        else:
            raise AssertionError("Invalid mode: {} ".format(mode))

        ret_dict = {field_name: getattr(event_log_result, field_name) for field_name in event_log_result._fields}

        return HttpResponse(
            bson.json_util.dumps(ret_dict),
            content_type="application/json"
        )


class DispatcherLinkLoader(View):
    @method_decorator(login_required)
    def post(self, request):
        model_name = request.POST.get("model_name")
        queryset = DispatcherLink.objects.filter(model_name=model_name)
        serializer = DispatcherLinkSerializer(queryset, many=True)
        return HttpResponse(json.dumps(serializer.data))

class DispatcherLinkSyncer(View):
    @method_decorator(login_required)
    def post(self, request):
        model_name = request.POST.get("model_name")
        object_id = request.POST.get("object_id")
        schedule_handler = request.POST.get("schedule_handler")
        user_id = request.POST.get("user_id")
        dispatcher_setting_ids = [int(value) for value in request.POST.getlist("dispatcher_setting_ids[]")]

        current_links = DispatcherLink.objects.filter(
            model_name=model_name,
            object_id=object_id,
            schedule_handler=schedule_handler)

        links_deleted = []
        for link in current_links:
            if link.dispatcher_setting.idx in dispatcher_setting_ids:
                dispatcher_setting_ids.remove(link.dispatcher_setting.idx)
            else:
                links_deleted.append(link.idx)
                link.delete()

        links_created = []
        for dispatcher_setting_id in dispatcher_setting_ids:
            new_link = DispatcherLink(
                model_name=model_name,
                object_id=object_id,
                schedule_handler=schedule_handler,
                dispatcher_setting=DispatcherSetting.objects.get(idx=dispatcher_setting_id),
                user=user.objects.get(idx=user_id)
            )

            new_link.save()
            links_created.append(new_link.idx)

        return HttpResponse(json.dumps([links_deleted, links_created]))