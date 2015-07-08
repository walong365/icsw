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

from django.contrib.auth.decorators import login_required
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

    def _get_wmi_event_log(self, device_pks):
        db = MongoDbInterface()
        entries = db.event_log_db.wmi_event_log.find({'device_pk': {'$in': device_pks}})
        print 'WMI'
        pprint.pprint(list(entries))

    @method_decorator(login_required)
    def list(self, request, *args, **kwargs):
        device_pks = json.loads(request.GET['device_pks'])
        #self._get_ipmi_event_log(device_pks)
        self._get_wmi_event_log(device_pks)

        return Response([])


