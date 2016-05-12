# Copyright (C) 2014-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" cluster-server, create background jobs """

import datetime

from django.db.models import Q
from initat.tools import server_command
from initat.cluster.backbone.models.functions import cluster_timezone


def create_bg_job(server_pk, user_obj, cmd, cause, obj, **kwargs):
    # late import to break import loop
    from initat.cluster.backbone.models import background_job, device
    srv_com = server_command.srv_command(
        command=cmd,
    )
    _bld = srv_com.builder()
    if type(obj) == list:
        obj_list = obj
    else:
        obj_list = [obj]
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
    _new_job = background_job.objects.create(
        command=cmd,
        cause=u"{} of '{}'".format(cause, unicode(obj))[:255],
        state="pre-init",
        options=kwargs.get("options", ""),
        initiator=device.objects.get(Q(pk=server_pk)),
        user=user_obj,
        command_xml=unicode(srv_com),
        num_objects=len(obj_list),
        # valid for 4 hours
        valid_until=cluster_timezone.localize(datetime.datetime.now() + datetime.timedelta(seconds=60 * 5)),  # 3600 * 4)),
    )
    # print srv_com.pretty_print()
    return _new_job


def notify_command():
    return server_command.srv_command(command="wf_notify")
