# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
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
""" various servers, background inotify import script """

import datetime

from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import background_job, background_job_run, cluster_timezone, BackgroundJobState
from initat.cluster.backbone.routing import SrvTypeRouting
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.tools import logging_tools, process_tools, server_command
from .tasks import BG_TASKS


class ServerBackgroundNotifyMixin(object):
    # requires to SendToRemoteServerMixin
    def init_notify_framework(self, global_config):
        self.__gc = global_config
        self.__server_idx = global_config["SERVER_IDX"]
        self.__waiting_ids = []
        self.__tasks = {_task.Meta.name: _task(self) for _task in BG_TASKS}
        self.srv_routing = SrvTypeRouting(force=True, logger=self.log_template)
        if self.srv_routing.local_device.pk != self.__server_idx:
            self.log(
                "local_device from srv_routing '{}' ({:d}) differs from SERVER_IDX '{:d}'".format(
                    str(self.srv_routing.local_device),
                    self.srv_routing.local_device.pk,
                    self.__server_idx,
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            self["exit_requested"] = True
        # check for background jobs and register timer to check for every 10 minutes
        self.register_timer(self.bg_check_notify, 10 * 60, instant=True, oneshot=True)

    def bg_check_notify(self):
        self.srv_routing.update()
        # step 1: delete pending jobs which are too old
        _timeout = background_job.objects.filter(
            Q(initiator=self.srv_routing.local_device.pk) &
            Q(state__in=[BackgroundJobState.pre_init.value, BackgroundJobState.pending.value]) &
            Q(valid_until__lte=cluster_timezone.localize(datetime.datetime.now()))
        )
        if _timeout.count():
            self.log("{} timeout".format(logging_tools.get_plural("background job", _timeout.count())), logging_tools.LOG_LEVEL_WARN)
            for _to in _timeout:
                _to.set_state(BackgroundJobState.timeout)
        # print background_job.objects.filter(Q(initiator=self.srv_routing.local_device.pk) & Q(state="pre-init") & Q(valid_until_lt=datetime.datetime.now()))
        try:
            _pending = background_job.objects.filter(
                Q(initiator=self.srv_routing.local_device.pk) &
                Q(state=BackgroundJobState.pre_init.value)
            ).order_by("pk")
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
            db_tools.close_connection()
        else:
            if _pc:
                self.log("pending background jobs: {:d}".format(_pc))
                for _cur_bg in _pending:
                    self._handle_bgj(_cur_bg)

    def _handle_bgj(self, cur_bg):
        if cur_bg.command not in self.__tasks:
            self.log("unknown background-command '{}', ending".format(cur_bg.command), logging_tools.LOG_LEVEL_ERROR)
            cur_bg.set_state(BackgroundJobState.ended, server_command.SRV_REPLY_STATE_ERROR)
            cur_bg.valid_until = None
            cur_bg.save()
        else:
            cur_bg.set_state(BackgroundJobState.pending)
            self.log("handling {}".format(cur_bg.command))
            to_run = self.__tasks[cur_bg.command].run(cur_bg)
            self._run_bg_jobs(cur_bg, to_run)

    def bg_notify_waiting_for_job(self, srv_com):
        _waiting = False
        # we only accept to srv_com if bgjrid and executed are set
        if "bgjrid" in srv_com and "executed" in srv_com:
            _id = int(srv_com["*bgjrid"])
            if _id in self.__waiting_ids:
                _waiting = True
        return _waiting

    def bg_notify_handle_result(self, srv_com):
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
        _run_job.state = server_command.log_level_to_srv_reply(_state)
        _run_job.result = _str
        _run_job.result_xml = str(srv_com)
        _run_job.end = cluster_timezone.localize(datetime.datetime.now())
        _run_job.save()
        self.bg_notify_check_for_bgj_finish(_run_job.background_job)

    def bg_notify_check_for_bgj_finish(self, cur_bg):
        _runs = cur_bg.background_job_run_set.all()
        if len(_runs):
            # background run sets defined (== subcommands, for example for node splitting [mother])
            if not any([_run.result == "" for _run in _runs]):
                # all results set
                _states = cur_bg.background_job_run_set.all().values_list("state", flat=True)
                if len(_states):
                    cur_bg.set_state(BackgroundJobState.done, result=max(_states))
                else:
                    cur_bg.set_state(BackgroundJobState.done, result=server_command.SRV_REPLY_STATE_UNSET)
                self.log("{} finished".format(str(cur_bg)))
        else:
            # no subcommands, mark as done
            cur_bg.set_state(BackgroundJobState.done)

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
                _is_local = _run_job.server_id == self.__server_idx and _srv_type == icswServiceEnum.cluster_server
                # _conn_str = self.srv_routing.get_connection_string(_srv_type, _run_job.server_id)
                self.__waiting_ids.append(_run_job.pk)
                if _is_local:
                    self._execute_command(_send_xml)
                    self.bg_notify_handle_result(_send_xml)
                    self.log("handled command {} locally".format(*_send_xml["*command"]))
                    _ok = True
                else:
                    # returns False or rsa with error flags set
                    _rsa = self.send_to_remote_server(_srv_type, _send_xml)
                    if _rsa.success:
                        self.log(
                            "command {} to remote {} on {} {}".format(
                                _send_xml["*command"],
                                _srv_type.name,
                                str(_run_job.server),
                                _rsa.connection_string,
                            )
                        )
                    else:
                        _send_xml.set_result(
                            "error sending to {}, please check logs".format(
                                _srv_type.name,
                            ),
                            server_command.SRV_REPLY_STATE_CRITICAL
                        )
                        self.bg_notify_handle_result(_send_xml)
                # # old code
                # if not _conn_str:
                #     self.log(
                #         u"got empty connection_string for {} ({})".format(
                #             _srv_type.name,
                #             _send_xml["*command"],
                #         ),
                #         logging_tools.LOG_LEVEL_ERROR
                #     )
                #     # set result
                #     _send_xml.set_result(
                #         "empty connection string",
                #         server_command.SRV_REPLY_STATE_CRITICAL,
                #     )
                #     self.bg_notify_handle_result(_send_xml)
                # else:
                #     _srv_uuid = get_server_uuid(_srv_type, _run_job.server.uuid)
                #     self.log(
                #         u"command to {} on {} {} ({}, command {}, {})".format(
                #             _srv_type.name,
                #             unicode(_run_job.server),
                #             _conn_str,
                #             _srv_uuid,
                #             _send_xml["*command"],
                #             "local" if _is_local else "remote",
                #         )
                #     )
                #     _ok = self.bg_send_to_server(
                #         _conn_str,
                #         _srv_uuid,
                #         _send_xml,
                #         local=_is_local,
                #     )
                #     if not _ok:
                #         _send_xml.set_result(
                #             "error sending to {} via {}".format(
                #                 _srv_type.name,
                #                 _conn_str
                #             ),
                #             server_command.SRV_REPLY_STATE_CRITICAL
                #         )
                #         self.bg_notify_handle_result(_send_xml)
        else:
            self.bg_notify_check_for_bgj_finish(cur_bg)
