# Copyright (C) 2014-2017 Andreas Lang-Nevyjel
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
for various servers
  o create background jobs
  o send to websocket channels
"""

import datetime
import json
import requests

from channels import Group
from django.conf import settings
from django.db.models import Q

from initat.cluster.backbone.models.functions import cluster_timezone
from initat.tools import server_command, logging_tools


__all__ = [
    "create_bg_job",
    "notify_command",
    "propagate_channel_object",
]


PROPAGATE_URL_TEMPLATE = "http://{}:{}/icsw/api/v2/base/propagate_channel_message/{{}}"
PROPAGATE_URL_HEADERS = {
    'Content-type': 'application/json',
    'Accept': 'text/plain'
}


class WebServerTarget(object):
    def __init__(self):
        self.port = None
        self.ip = None

    @property
    def address(self):
        if not self.port:
            self.resolve()
        return PROPAGATE_URL_TEMPLATE.format(self.ip, self.port)

    def resolve(self):
        # from initat.tools import config_tools
        # from initat.cluster.backbone.server_enums import icswServiceEnum
        from initat.cluster.settings import DEBUG
        # todo fixme via proper routing
        if DEBUG or not __file__.startswith("/opt/"):
            self.port = 8080
        else:
            self.port = 80
        # print("*", self.port)
        # self.ip = config_tools.server_check(service_type_enum=icswServiceEnum.cluster_server).ip_list[0]
        self.ip = "127.0.0.1"


web_target = WebServerTarget()


def create_bg_job(server_pk, user_obj, cmd, cause, obj, **kwargs):
    # late import to break import loop
    from initat.cluster.backbone.models import background_job, device, BackgroundJobState
    srv_com = server_command.srv_command(
        command=cmd,
    )
    timeout = kwargs.get("timeout", 60 * 5)
    _bld = srv_com.builder()
    if obj is None:
        obj_list = None
    elif isinstance(obj, list):
        obj_list = obj
        cause = "{} of {}".format(cause, logging_tools.get_plural("object", len(obj_list)))
    else:
        obj_list = [obj]
        cause = "{} of {}".format(cause, str(obj))

    if obj_list is not None:
        srv_com[None] = _bld.objects(
            *[
                _bld.object(
                    str(obj),
                    model=obj._meta.model_name,
                    app=obj._meta.app_label,
                    pk="{:d}".format(obj.pk),
                ) for obj in obj_list
            ]
        )
    # print "***", server_pk
    _new_job = background_job(
        command=cmd,
        cause=cause[:255],
        options=kwargs.get("options", ""),
        initiator=device.objects.get(Q(pk=server_pk)),
        user=user_obj,
        command_xml=str(srv_com),
        num_objects=len(obj_list) if obj_list else 0,
        # valid for 4 hours
        valid_until=cluster_timezone.localize(datetime.datetime.now() + datetime.timedelta(seconds=timeout)),
    )
    _new_job.set_state(kwargs.get("state", BackgroundJobState.pre_init))
    # print srv_com.pretty_print()
    return _new_job


def notify_command():
    return server_command.srv_command(command="wf_notify")


def propagate_channel_object(ws_enum, dict_obj):
    from initat.cluster.backbone.websockets.constants import WSStreamEnum
    if not isinstance(ws_enum, WSStreamEnum):
        raise TypeError("not of type WSStreamEnum: {}".format(str(ws_enum)))
    # json_obj is an already jsonified object
    _hosts = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"]
    # print("G", group, dict_obj)
    if any([_addr == "127.0.0.1" for _addr, _port in _hosts]):
        import redis
        # send to backend, only text is allowed as key
        # print("g", group, dict_obj)
        try:
            Group(ws_enum.name).send(
                {
                    "text": json.dumps(
                        {
                            "payload": dict_obj,
                            "stream": ws_enum.name,
                        }
                    )
                },
                immediately=True
            )
        except redis.ConnectionError:
            print("Error connecting to redis, ignoring ...")
    else:
        requests.post(
            web_target.address.format(ws_enum.name),
            data=json.dumps(dict_obj),
            headers=PROPAGATE_URL_HEADERS
        )
