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


from django.db.models import Q
import datetime
from initat.cluster.backbone.models import user, background_job_run, cluster_timezone
from .base import BGInotifyTask
from initat.tools import logging_tools, server_command, config_tools


class SyncUserTask(BGInotifyTask):
    class Meta:
        name = "sync_users"
        short = "su"

    def run(self, cur_bg):
        # step 1: create user homes
        _uo = user.objects  # @UndefinedVariable
        create_user_list = _uo.exclude(
            Q(export=None)
        ).filter(
            Q(home_dir_created=False) & Q(active=True) & Q(group__active=True)
        ).select_related(
            "export__device"
        )
        to_run = []
        if create_user_list.count():
            self.log("{} to create".format(logging_tools.get_plural("user home", len(create_user_list))))
            for create_user in create_user_list:
                srv_com = server_command.srv_command(command="create_user_home")
                srv_com["server_key:username"] = create_user.login
                to_run.append(
                    (
                        background_job_run(
                            background_job=cur_bg,
                            server=create_user.export.device,
                            command_xml=unicode(srv_com),
                            start=cluster_timezone.localize(datetime.datetime.now()),
                        ),
                        srv_com,
                        "server",
                        #
                    )
                )
        else:
            self.log("no user homes to create", logging_tools.LOG_LEVEL_WARN)
        # check directory sync requests
        no_device = []
        for _config, _command, _srv_type in [
            ("ldap_server", "sync_ldap_config", "server"),
            ("yp_server", "write_yp_config", "server"),
            ("monitor_server", "sync_http_users", "md-config"),
        ]:
            _cdict = config_tools.device_with_config(_config)
            for _sc in _cdict.itervalues():
                if _sc.effective_device:
                    self.log(
                        u"effective device for {} (command {}) is {}".format(
                            _config,
                            _command,
                            unicode(_sc.effective_device),
                        )
                    )
                    srv_com = server_command.srv_command(command=_command)
                    to_run.append(
                        (
                            background_job_run(
                                background_job=cur_bg,
                                server=_sc.effective_device,
                                command_xml=unicode(srv_com),
                                start=cluster_timezone.localize(datetime.datetime.now()),
                            ),
                            srv_com,
                            _srv_type,
                        )
                    )
            else:
                no_device.append(_command)
        if no_device:
            self.log("no device(s) found for {}".format(", ".join(no_device)), logging_tools.LOG_LEVEL_WARN)
        return to_run
