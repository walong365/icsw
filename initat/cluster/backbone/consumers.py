# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2016 Andreas Lang-Nevyjel
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
from channels.sessions import channel_session
from channels.generic import BaseConsumer


# testcode, not working / needed
class icswConsumer(BaseConsumer):
    method_mapping = {
        "device_log_entries": "test_name"
    }

    def test_name(self, message, **kwargs):
        print("X", message, kwargs)


@channel_session
def ws_add(message, model_name):
    message.channel_session["model_name"] = model_name
    Group(message.channel_session["model_name"]).add(message.reply_channel)


@channel_session
def ws_disconnect(message, model_name):
    print("*", model_name, message.channel_session["model_name"])
    Group(
        message.channel_session["model_name"]
    ).discard(message.reply_channel)


@channel_session
def ws_message(message):
    print("***", dir(message))
    message.reply_channel.send(
        {
            "text": message.content['text'],
        }
    )
