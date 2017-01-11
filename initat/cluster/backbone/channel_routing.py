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
Channel settings
"""



from channels.routing import route, route_class

from initat.cluster.backbone.consumers import ws_add, ws_disconnect, ws_message, icswConsumer


channel_routing = [
    #  route_class(icswConsumer, path=r"^/icsw/ws/device_log_entries/$"),
    # route("websocket.connect", ws_add, path=r"^/icsw/ws/(?P<model_name>[0-9a-zA-Z_]+)/$"),
    route("websocket.connect", ws_add, path=r"^/icsw/ws/(?P<model_name>[0-9a-zA-Z_]+)/$"),
    route("websocket.receive", ws_message),
    route("websocket.disconnect", ws_disconnect),
]
