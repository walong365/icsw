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
""" cluster-server, background inotify import script """

import datetime

from initat.cluster.backbone.models import background_job_run, cluster_timezone
from initat.tools import logging_tools, config_tools, server_command

from .base import BGInotifyTask


class SyncSensorThresholdTask(BGInotifyTask):
    class Meta:
        name = "sync_sensor_threshold"
        short = "sst"

    def run(self, cur_bg):
        _src_com = server_command.srv_command(source=cur_bg.command_xml)
        # target command
        srv_com = server_command.srv_command(command="sync_sensor_threshold")
        _sc = config_tools.server_check(server_type="rrd_collector")
        to_run = []
        if _sc.effective_device:
            to_run.append(
                (
                    background_job_run(
                        background_job=cur_bg,
                        server=_sc.effective_device,
                        command_xml=unicode(srv_com),
                        start=cluster_timezone.localize(datetime.datetime.now()),
                    ),
                    srv_com,
                    "collectd",
                )
            )
        else:
            self.log("no valid rrd-collector found", logging_tools.LOG_LEVEL_ERROR)
        return to_run
