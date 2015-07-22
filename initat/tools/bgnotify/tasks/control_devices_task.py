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
    cluster_timezone, SensorAction
from initat.tools import server_command

from .base import BGInotifyTask


class ChangeBootsettingTask(BGInotifyTask):
    class Meta:
        name = "sensor_action"
        short = "sa"

    def run(self, cur_bg):
        to_run = []
        sensor_action = SensorAction.objects.get(Q(pk=cur_bg.options))
        _mother_com = sensor_action.get_mother_command()
        if _mother_com is not None:
            _src_com = server_command.srv_command(source=cur_bg.command_xml)
            devs = device.objects.filter(Q(pk__in=[int(_pk) for _pk in _src_com.xpath(".//ns:object/@pk")]))
            # split for bootservers
            _boot_dict = {}
            for _dev in devs:
                if _dev.bootserver_id:
                    _boot_dict.setdefault(_dev.bootserver_id, []).append(_dev)
            for srv_id, dev_list in _boot_dict.iteritems():
                # target command
                srv_com = server_command.srv_command(command=_mother_com[0])
                # only valid for one device
                srv_com["devices"] = srv_com.builder(
                    "devices",
                    *sum([sensor_action.build_mother_element(srv_com.builder, dev) for dev in dev_list], [])
                )
                to_run.append(
                    (
                        background_job_run(
                            background_job=cur_bg,
                            server=dev_list[0].bootserver,
                            command_xml=unicode(srv_com),
                            start=cluster_timezone.localize(datetime.datetime.now()),
                        ),
                        srv_com,
                        "mother",
                    )
                )
        return to_run
