# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
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
""" cluster-server, change bootsetting tasks """

import datetime

from django.db.models import Q
from initat.cluster.backbone.models import background_job_run, device, \
    cluster_timezone
from initat.tools import server_command

from .base import BGInotifyTask


class ControlTask(object):
    pass


class ChangeBootsettingTask(BGInotifyTask, ControlTask):
    class Meta:
        name = "halt;sw"
        short = "hsw"

    def run(self, cur_bg):
        _src_com = server_command.srv_command(source=cur_bg.command_xml)
        dev = device.objects.get(Q(pk=int(_src_com.xpath(".//ns:object/@pk")[0])))
        # target command
        srv_com = server_command.srv_command(command="refresh")
        srv_com["devices"] = srv_com.builder(
            "devices",
            srv_com.builder("device", name=dev.name, pk="{:d}".format(dev.pk)))
        to_run = [
            (
                background_job_run(
                    background_job=cur_bg,
                    server=dev.bootserver,
                    command_xml=unicode(srv_com),
                    start=cluster_timezone.localize(datetime.datetime.now()),
                ),
                srv_com,
                "mother",
            )
        ]
        return to_run
