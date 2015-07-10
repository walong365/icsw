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

    def _get_ipmi_event_log(self, device_pks, pagination_skip, pagination_limit, filter_str=None):
        mongo = MongoDbInterface()
        projection_obj = {
            'sections': 1,
        }
        query_obj = {
            'device_pk': {'$in': device_pks},
        }
        if filter_str is not None and filter_str:  # "" means no search as well
            query_obj["$text"] = {'$search': filter_str}
        sort_obj = [('record_id', pymongo.DESCENDING)]
        entries = mongo.event_log_db.ipmi_event_log.find(
            query_obj,
            projection_obj,
            sort=sort_obj,
        )
        total_num = entries.count()

        if pagination_skip is not None:
            entries.skip(pagination_skip)
        if pagination_limit is not None:
            entries.limit(pagination_limit)
        result = [entry['sections'] for entry in entries]  # exhaust cursor
        entry_keys = collections.OrderedDict()  # we only use it as set
        # merge ipmi sections
        result_merged = []
        for entry in result:
            entry_merged = {}
            for section in entry:
                # filter internal fields
                entry_merged.update({k: v for k, v in section.iteritems() if k != '__icsw_ipmi_section_type'})
            entry_keys.update({k: None for k in entry_merged.iterkeys()})
            result_merged.append(entry_merged)
        return total_num, entry_keys.keys(), result_merged

    def _get_wmi_event_log(self, device_pks, logfile_name=None, pagination_skip=None, pagination_limit=None,
                           filter_str=None):
        mongo = MongoDbInterface()
        query_obj = {
            'device_pk': {'$in': device_pks},
        }
        if logfile_name is not None:
            query_obj['logfile_name'] = logfile_name
        if filter_str is not None:
            query_obj["$text"] = {'$search': filter_str}

        projection_obj = {
            'entry': 1,
        }
        sort_obj = [('time_generated', pymongo.DESCENDING), ('record_number', pymongo.DESCENDING)]
        entries = mongo.event_log_db.wmi_event_log.find(query_obj, projection_obj, sort=sort_obj)
        total_num = entries.count()
        # entries.sort(
        if pagination_skip is not None:
            entries.skip(pagination_skip)
        if pagination_limit is not None:
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
        logfile_name = request.GET.get('logfile_name')
        int_or_none = lambda x: int(x) if x is not None else x
        pagination_skip = int_or_none(request.GET.get('pagination_skip'))
        pagination_limit = int_or_none(request.GET.get('pagination_limit'))

        mode_query_parameters = json.loads(request.GET['mode_query_parameters'])

        mode = request.GET['mode']

        if mode == 'wmi':
            # a = time.time()
            total_num, keys, entries =\
                self._get_wmi_event_log(device_pks, logfile_name, pagination_skip, pagination_limit,
                                        **mode_query_parameters)
            # print 'took', time.time() - a

        elif mode == 'ipmi':
            total_num, keys, entries =\
                self._get_ipmi_event_log(device_pks, pagination_skip, pagination_limit, **mode_query_parameters)
        else:
            raise AssertionError("Invalid mode: {} ".format(mode))

        return HttpResponse(bson.json_util.dumps([total_num, keys, entries]),
                            content_type="application/json")
