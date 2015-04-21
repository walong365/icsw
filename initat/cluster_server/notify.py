# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-server
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

""" notify mixin for server processes """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import background_job, user, background_job_run, device, \
    cluster_timezone, virtual_desktop_user_setting
from initat.cluster.backbone.routing import srv_type_routing, get_server_uuid
from initat.tools import config_tools
import datetime
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command

# background job command mapping
BGJ_CM = {
    "sync_users": True,
    "change_bootsetting": True,
    "reload_virtual_desktop_dispatcher": True
}


class notify_mixin(object):
    def init_notify_framework(self, global_config):
        self.__gc = global_config
        self.__server_idx = global_config["SERVER_IDX"]
        self.__waiting_ids = []
        self.srv_routing = srv_type_routing(force=True, logger=self.log_template)
        if self.srv_routing.local_device.pk != self.__server_idx:
            self.log(
                u"local_device from srv_routing '{}' ({:d}) differs from SERVER_IDX '{:d}'".format(
                    unicode(self.srv_routing.local_device),
                    self.srv_routing.local_device.pk,
                    self.__server_idx,
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            self["exit_requested"] = True
        # check for background jobs and register timer to check for every 10 minutes
        self.register_timer(self.check_notify, 10 * 60, instant=True, oneshot=True)

    def check_notify(self):
        self.srv_routing.update()
        # step 1: delete pending jobs which are too old
        _timeout = background_job.objects.filter(
            Q(initiator=self.srv_routing.local_device.pk) & Q(state__in=["pre-init", "pending"]) & Q(valid_until__lte=datetime.datetime.now())
        )
        if _timeout.count():
            self.log("{} timeout".format(logging_tools.get_plural("background job", _timeout.count())), logging_tools.LOG_LEVEL_WARN)
            for _to in _timeout:
                _to.state = "timeout"
                _to.save()
        # print background_job.objects.filter(Q(initiator=self.srv_routing.local_device.pk) & Q(state="pre-init") & Q(valid_until_lt=datetime.datetime.now()))
        try:
            _pending = background_job.objects.filter(Q(initiator=self.srv_routing.local_device.pk) & Q(state="pre-init")).order_by("pk")
            # force evaluation
            _pc = _pending.count()
        except:
            self.log(
                "error accessing DB: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            # close connection
            connection.close()
        else:
            if _pc:
                self.log("pending background jobs: {:d}".format(_pc))
                for _cur_bg in _pending:
                    self._handle_bgj(_cur_bg)

    def _handle_bgj(self, cur_bg):
        if cur_bg.command not in BGJ_CM:
            cur_bg.state = "ended"
            cur_bg.valid_until = None
            cur_bg.save()
        else:
            _com_name = "_bgjp_{}".format(cur_bg.command)
            if hasattr(self, _com_name):
                cur_bg.state = "pending"
                cur_bg.save()
                self.log("handling {}".format(cur_bg.command))
                getattr(self, "_bgjp_{}".format(cur_bg.command))(cur_bg)
            else:
                self.log("no {} function defined".format(_com_name), logging_tools.LOG_LEVEL_CRITICAL)
                cur_bg.state = "ended"
                cur_bg.save()

    def notify_waiting_for_job(self, srv_com):
        _waiting = False
        # we only accept to srv_com if bgjrid and executed are set
        if "bgjrid" in srv_com and "executed" in srv_com:
            _id = int(srv_com["*bgjrid"])
            if _id in self.__waiting_ids:
                _waiting = True
        return _waiting

    def notify_handle_result(self, srv_com):
        _str, _state = srv_com.get_log_tuple()
        _id = int(srv_com["*bgjrid"])
        self.__waiting_ids.remove(_id)
        self.log(
            "got result for bgjrid {:d} ({:d}): {}".format(
                _id,
                _state,
                _str,
            ),
            _state
        )
        _run_job = background_job_run.objects.select_related("background_job").get(Q(pk=_id))
        _run_job.state = _state
        _run_job.result = _str
        _run_job.result_xml = unicode(srv_com)
        _run_job.end = cluster_timezone.localize(datetime.datetime.now())
        _run_job.save()
        self.notify_check_for_bgj_finish(_run_job.background_job)

    def notify_check_for_bgj_finish(self, cur_bg):
        if not cur_bg.background_job_run_set.filter(Q(result="")).count():
            cur_bg.state = "done"
            cur_bg.save()
            self.log("{} finished".format(unicode(cur_bg)))

    def _bgjp_reload_virtual_desktop_dispatcher(self, cur_bg):
        '''
        Find actual cluster-server of virtual desktop and reload/restart there
        :param cur_bg:
        '''
        _src_com = server_command.srv_command(source=cur_bg.command_xml)
        vdus = virtual_desktop_user_setting.objects.get(Q(pk=_src_com.xpath(".//ns:object/@pk")[0]))

        srv_com = server_command.srv_command(command="reload_virtual_desktop")
        srv_com["vdus"] = vdus.pk

        to_run = [
            (
                background_job_run(
                    background_job=cur_bg,
                    server=vdus.device,
                    command_xml=unicode(srv_com),
                    start=cluster_timezone.localize(datetime.datetime.now()),
                ),
                srv_com,
                "server",
            )
        ]
        self._run_bg_jobs(cur_bg, to_run)

    def _bgjp_change_bootsetting(self, cur_bg):
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
        self._run_bg_jobs(cur_bg, to_run)

    def _bgjp_sync_users(self, cur_bg):
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
                to_run.append((
                    background_job_run(
                        background_job=cur_bg,
                        server=create_user.export.device,
                        command_xml=unicode(srv_com),
                        start=cluster_timezone.localize(datetime.datetime.now()),
                    ),
                    srv_com,
                    "server",
                    #
                ))
        else:
            self.log("no user homes to create", logging_tools.LOG_LEVEL_WARN)
        # check directory sync requests
        no_device = []
        for _config, _command, _srv_type in [
            ("ldap_server", "sync_ldap_config", "server"),
            ("yp_server", "write_yp_config", "server"),
            ("monitor_server", "sync_http_users", "md-config"),
        ]:
            _sc = config_tools.server_check(server_type=_config)
            if _sc.effective_device:
                self.log(u"effective device for {} (command {}) is {}".format(
                    _config,
                    _command,
                    unicode(_sc.effective_device),
                ))
                srv_com = server_command.srv_command(command=_command)
                to_run.append((
                    background_job_run(
                        background_job=cur_bg,
                        server=_sc.effective_device,
                        command_xml=unicode(srv_com),
                        start=cluster_timezone.localize(datetime.datetime.now()),
                    ),
                    srv_com,
                    _srv_type,
                ))
            else:
                no_device.append(_command)
        if no_device:
            self.log("no device(s) found for {}".format(", ".join(no_device)), logging_tools.LOG_LEVEL_WARN)
        self._run_bg_jobs(cur_bg, to_run)

    def _run_bg_jobs(self, cur_bg, to_run):
        if to_run:
            self.log("commands to execute: {:d}".format(len(to_run)))
            cur_bg.num_servers = len(to_run)
            cur_bg.save()
            for _run_job, _send_xml, _srv_type in to_run:
                _run_job.save()
                # set BackGroundJobRunID
                _send_xml["bgjrid"] = "{:d}".format(_run_job.pk)
                # add to waiting list
                _is_local = _run_job.server_id == self.__server_idx and _srv_type == "server"
                _conn_str = self.srv_routing.get_connection_string(_srv_type, _run_job.server_id)
                self.__waiting_ids.append(_run_job.pk)
                if not _conn_str:
                    self.log(
                        u"got empty connection_string for {} ({})".format(
                            _srv_type,
                            _send_xml["*command"],
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    # set result
                    _send_xml.set_result(
                        "empty connection string",
                        server_command.SRV_REPLY_STATE_CRITICAL
                        )
                    self.notify_handle_result(_send_xml)
                else:
                    _srv_uuid = get_server_uuid(_srv_type, _run_job.server.uuid)
                    self.log(u"command to {} {} ({}, command {}, {})".format(
                        _srv_type,
                        _conn_str,
                        _srv_uuid,
                        _send_xml["*command"],
                        "local" if _is_local else "remote",
                        ))
                    _ok = self.send_to_server(
                        _conn_str,
                        _srv_uuid,
                        _send_xml,
                        local=_is_local,
                    )
                    if not _ok:
                        _send_xml.set_result(
                            "error sending to {}".format(_conn_str),
                            server_command.SRV_REPLY_STATE_CRITICAL
                        )
                        self.notify_handle_result(_send_xml)
        else:
            self.notify_check_for_bgj_finish(cur_bg)
