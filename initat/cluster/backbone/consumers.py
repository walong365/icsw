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

from channels import Group
from channels.generic.websockets import JsonWebsocketConsumer, WebsocketDemultiplexer
from django.conf import settings


class icswConsumer(JsonWebsocketConsumer):
    http_user = True

    def connect(self, message, multiplexer, **kwargs):
        if settings.DEBUG:
            print(
                "ws_connect called, session is {}".format(
                    "valid" if message.http_session else "not valid",
                )
            )
        if message.http_session:
            message.reply_channel.send({"accept": True})
            Group("general").add(message.reply_channel)

    def connection_groups(self, **kwargs):
        return []

    def receive(self, content, multiplexer, **kwargs):
        """
        Called when a message is received with either text or bytes
        filled out.
        """
        if content["action"] == "add":
            Group(multiplexer.stream).add(self.message.reply_channel)
        elif content["action"] == "remove":
            Group(multiplexer.stream).discard(self.message.reply_channel)


class icswDemultiplexer(WebsocketDemultiplexer):
    consumers = {
        "device_log_entries": icswConsumer,
        "general": icswConsumer,
    }
