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

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.response import Response
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


class GetEventLog(ListAPIView):

    def _get_ipmi_event_log(self, device_pks):
        db = MongoDbInterface()
        entries = db.event_log_db.ipmi_event_log.find({'device_pk': {'$in': device_pks}})
        print 'IPMI'
        pprint.pprint(list(entries))

    def _get_wmi_event_log(self, device_pks, logfile_name=None, pagination_skip=None, pagination_limit=None):
        db = MongoDbInterface()
        query_obj = {
            'device_pk': {'$in': device_pks},
        }
        if logfile_name is not None:
            query_obj['logfile_name'] = logfile_name
        entries = db.event_log_db.wmi_event_log.find(query_obj)
        entries.sort([('time_generated', pymongo.DESCENDING)])
        if pagination_skip is not None:
            entries.skip(pagination_skip)
        if pagination_limit is not None:
            entries.limit(pagination_limit)
        return list(entries)

    @method_decorator(login_required)
    def list(self, request, *args, **kwargs):
        device_pks = json.loads(request.GET['device_pks'])
        logfile_name = request.GET['logfile_name']
        int_or_none = lambda x: int(x) if x is not None else x
        pagination_skip = int_or_none(request.GET.get('pagination_skip'))
        pagination_limit = int_or_none(request.GET.get('pagination_limit'))

        # self._get_ipmi_event_log(device_pks)
        wmi_res = self._get_wmi_event_log(device_pks, logfile_name, pagination_skip, pagination_limit)

        return HttpResponse(bson.json_util.dumps(wmi_res), content_type="application/json")
        # return Response(serializer.data)


