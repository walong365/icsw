# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of webfrontend
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
# -*- coding: utf-8 -*-
#
import json
import pprint
import bson.json_util
import collections
import datetime
import dateutil.parser

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
import itertools
from rest_framework.response import Response
import time
from initat.cluster.backbone.models import device
from initat.cluster.backbone.models.functions import memoize_with_expiry
import pymongo
from rest_framework.generics import ListAPIView
from initat.cluster.backbone.render import render_me


class MongoDbInterface(object):
    def __init__(self):
        self.client, self.event_log_db = self.__class__._get_config()

    @classmethod
    @memoize_with_expiry(60)
    def _get_config(cls):
        # TODO: Make this configurable, access discovery server config somehow?
        client = pymongo.MongoClient("localhost", 27017,
                                     tz_aware=True)

        event_log_db = client.icsw_event_log

        return client, event_log_db


class DiscoveryOverview(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render_me(request, "discovery_overview.html")()


class EventLogOverview(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render_me(request, "event_log.html")()


class GetEventLogDeviceInfo(View):
    """Returns which logs the given devices have"""
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        device_pks = json.loads(request.GET['device_pks'])
        ret = {}
        mongo = MongoDbInterface()

        _wmi_res = mongo.event_log_db.wmi_event_log.aggregate([{
            '$group': {
                '_id': {
                    'device_pk': '$device_pk',
                }
            }
        }])
        devices_with_wmi = {entry['_id']['device_pk'] for entry in _wmi_res}

        _ipmi_res = mongo.event_log_db.ipmi_event_log.aggregate([{
            '$group': {
                '_id': {
                    'device_pk': '$device_pk',
                }
            }
        }])
        devices_with_ipmi = {entry['_id']['device_pk'] for entry in _ipmi_res}

        for entry in device.objects.filter(pk__in=device_pks):
            capabilities = []
            if entry.pk in devices_with_ipmi:
                capabilities.append("ipmi")
            if entry.pk in devices_with_wmi:
                capabilities.append("wmi")
            ret[entry.pk] = {
                'name': entry.full_name,
                'capabilities': capabilities,
            }

        return HttpResponse(json.dumps(ret), content_type='application/json')


class GetEventLog(ListAPIView):
    """Returns actual log data (all kinds of logs currently)"""

    @classmethod
    def _parse_datetime(cls, datetime_str):
        return dateutil.parser.parse(datetime_str)

    def _get_ipmi_event_log(self, device_pks, pagination_skip, pagination_limit,
                            filter_str=None, from_date=None, to_date=None):
        mongo = MongoDbInterface()
        projection_obj = {
            'sections': 1,
            'keys_ordered': 1,
        }
        query_obj = {
            'device_pk': {'$in': device_pks},
        }

        if from_date is not None:
            query_obj.setdefault('creation_date', {})['$gte'] = self._parse_datetime(from_date)
        if to_date is not None:
            query_obj.setdefault('creation_date', {})['$lte'] = self._parse_datetime(to_date)

        if filter_str is not None:
            query_obj["$text"] = {'$search': filter_str}
        sort_obj = [('record_id', pymongo.DESCENDING)]
        print 'query', query_obj, projection_obj, sort_obj
        entries = mongo.event_log_db.ipmi_event_log.find(
            query_obj,
            projection_obj,
            sort=sort_obj,
        )
        # pprint.pprint(entries.explain())

        total_num = entries.count()

        entries.skip(pagination_skip)
        entries.limit(pagination_limit)

        result = []
        entry_keys = collections.OrderedDict()  # we only use it as set
        for entry in entries:  # exhaust cursor
            result.append(entry['sections'])
            for k in entry['keys_ordered']:
                if k != '__icsw_ipmi_section_type':
                    entry_keys[k] = None
        # merge ipmi sections
        result_merged = []
        for entry in result:
            entry_merged = {}
            for section in entry:
                # filter internal fields
                entry_merged.update({k: v for k, v in section.iteritems() if k != '__icsw_ipmi_section_type'})
            result_merged.append(entry_merged)
        return total_num, entry_keys.keys(), result_merged

    def _get_wmi_event_log(self, device_pks, pagination_skip, pagination_limit,
                           filter_str=None, from_date=None, to_date=None, logfile_name=None):
        mongo = MongoDbInterface()
        query_obj = {
            'device_pk': {'$in': device_pks},
        }
        if logfile_name is not None:
            query_obj['logfile_name'] = logfile_name
        if filter_str is not None:
            query_obj["$text"] = {'$search': filter_str}

        if from_date is not None:
            query_obj.setdefault('time_generated', {})['$gte'] = self._parse_datetime(from_date)
        if to_date is not None:
            query_obj.setdefault('time_generated', {})['$lte'] = self._parse_datetime(to_date)

        projection_obj = {
            'entry': 1,
        }
        sort_obj = [('time_generated', pymongo.DESCENDING), ('record_number', pymongo.DESCENDING)]
        entries = mongo.event_log_db.wmi_event_log.find(query_obj, projection_obj, sort=sort_obj)
        print 'query', query_obj, projection_obj, sort_obj
        total_num = entries.count()
        # entries.sort(
        entries.skip(pagination_skip)
        entries.limit(pagination_limit)
        result = [entry['entry'] for entry in entries]  # exhaust cursor
        keys = set()
        for entry in result:
            keys.update(entry.iterkeys())
        return total_num, keys, result

    @method_decorator(login_required)
    def list(self, request, *args, **kwargs):
        # NOTE: currently, this list always contains one entry
        device_pks = json.loads(request.GET['device_pks'])
        pagination_skip = int(request.GET.get('pagination_skip'))
        pagination_limit = int(request.GET.get('pagination_limit'))

        # misc additional parameters passed directly to handler functions
        query_parameters = json.loads(request.GET['query_parameters'])

        mode = request.GET['mode']

        if mode == 'wmi':
            # a = time.time()
            total_num, keys, entries =\
                self._get_wmi_event_log(device_pks, pagination_skip, pagination_limit, **query_parameters)
            # print 'took', time.time() - a

        elif mode == 'ipmi':
            total_num, keys, entries =\
                self._get_ipmi_event_log(device_pks, pagination_skip, pagination_limit, **query_parameters)
        else:
            raise AssertionError("Invalid mode: {} ".format(mode))

        return HttpResponse(bson.json_util.dumps([total_num, keys, entries]),
                            content_type="application/json")
