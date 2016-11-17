# Copyright (C) 2014-2016 Andreas Lang-Nevyjel
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
""" various servers, create background jobs """

from __future__ import unicode_literals, print_function

import datetime

from django.db.models import Q

from initat.cluster.backbone.models.functions import cluster_timezone
from initat.tools import server_command, logging_tools


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
        cause = "{} of {}".format(cause, unicode(obj))

    if obj_list is not None:
        srv_com[None] = _bld.objects(
            *[
                _bld.object(
                    unicode(obj),
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
        command_xml=unicode(srv_com),
        num_objects=len(obj_list) if obj_list else 0,
        # valid for 4 hours
        valid_until=cluster_timezone.localize(datetime.datetime.now() + datetime.timedelta(seconds=timeout)),
    )
    _new_job.set_state(kwargs.get("state", BackgroundJobState.pre_init))
    # print srv_com.pretty_print()
    return _new_job


def notify_command():
    return server_command.srv_command(command="wf_notify")
