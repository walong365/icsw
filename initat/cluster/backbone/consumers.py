# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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

"""

daphne consumers

"""

from __future__ import print_function, unicode_literals

from channels import Group
from channels.generic import BaseConsumer
from django.conf import settings

from channels.auth import channel_session_user_from_http

GROUP_KEY = "model_name"


# testcode, not working / needed
class icswConsumer(BaseConsumer):
    method_mapping = {
        "device_log_entries": "test_name"
    }

    def test_name(self, message, **kwargs):
        print("X", message, kwargs)


@channel_session_user_from_http
def ws_add(message, model_name):
    if settings.DEBUG:
        print("ws_add for group {}".format(model_name))
    if message.http_session:
        message.reply_channel.send({"accept": True})
        # print("add", model_name)
        message.channel_session[GROUP_KEY] = model_name
        # print("d", message.channel_session[GROUP_KEY])
        Group(message.channel_session[GROUP_KEY]).add(message.reply_channel)
        # channels 1.0.0
    else:
        if settings.DEBUG:
            print("no valid session for {}".format(model_name))


@channel_session_user_from_http
def ws_disconnect(message):
    if GROUP_KEY not in message.channel_session.keys():
        print(
            "GROUP_KEY '{}' missing from channel_session keys(): {}".format(
                GROUP_KEY,
                ", ".join(sorted(message.channel_session.keys()))
            )
        )
    else:
        model_name = message.channel_session[GROUP_KEY]
        Group(
            model_name,
        ).discard(message.reply_channel)


@channel_session_user_from_http
def ws_message(message):
    message.reply_channel.send(
        {
            "text": message.content['text'],
        },
    )
