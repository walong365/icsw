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
import time

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import background_job, background_job_run, cluster_timezone
from initat.cluster.backbone.routing import srv_type_routing, get_server_uuid
from initat.tools import logging_tools, process_tools, server_command

from .tasks import BG_TASKS


class ServerBackgroundNotifyMixin(object):
    def init_notify_framework(self, global_config):
        self.__gc = global_config
        self.__server_idx = global_config["SERVER_IDX"]
        self.__waiting_ids = []
        self.__tasks = {_task.Meta.name: _task(self) for _task in BG_TASKS}
        # connections to other servers
        self.__other_server_dict = {}
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
        self.register_timer(self.bg_check_notify, 10 * 60, instant=True, oneshot=True)

    def bg_check_notify(self):
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
        if cur_bg.command not in self.__tasks:
            cur_bg.state = "ended"
            cur_bg.valid_until = None
            cur_bg.save()
        else:
            cur_bg.state = "pending"
            cur_bg.save()
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
        _run_job.state = _state
        _run_job.result = _str
        _run_job.result_xml = unicode(srv_com)
        _run_job.end = cluster_timezone.localize(datetime.datetime.now())
        _run_job.save()
        self.bg_notify_check_for_bgj_finish(_run_job.background_job)

    def bg_notify_check_for_bgj_finish(self, cur_bg):
        if not cur_bg.background_job_run_set.filter(Q(result="")).count():
            cur_bg.state = "done"
            cur_bg.save()
            self.log("{} finished".format(unicode(cur_bg)))

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
                        server_command.SRV_REPLY_STATE_CRITICAL,
                    )
                    self.bg_notify_handle_result(_send_xml)
                else:
                    _srv_uuid = get_server_uuid(_srv_type, _run_job.server.uuid)
                    self.log(
                        u"command to {} {} ({}, command {}, {})".format(
                            _srv_type,
                            _conn_str,
                            _srv_uuid,
                            _send_xml["*command"],
                            "local" if _is_local else "remote",
                        )
                    )
                    _ok = self.bg_send_to_server(
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
                        self.bg_notify_handle_result(_send_xml)
        else:
            self.bg_notify_check_for_bgj_finish(cur_bg)

    def bg_send_to_server(self, conn_str, srv_uuid, srv_com, **kwargs):
        _success = True
        # only for local calls
        local = kwargs.get("local", False)
        if local:
            self._execute_command(srv_com)
            self.bg_notify_handle_result(srv_com)
        else:
            if conn_str not in self.__other_server_dict:
                self.log("connecting to {} (uuid {})".format(conn_str, srv_uuid))
                self.__other_server_dict = srv_uuid
                self.main_socket.connect(conn_str)
                num_iters = 10
            else:
                num_iters = 1
            _cur_iter = 0
            while True:
                _cur_iter += 1
                try:
                    self.main_socket.send_unicode(srv_uuid, zmq.SNDMORE)  # @UndefinedVariable
                    self.main_socket.send_unicode(unicode(srv_com))
                except:
                    self.log(
                        "cannot send to {} [{:d}/{:d}]: {}".format(
                            conn_str,
                            _cur_iter,
                            num_iters,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                    _success = False
                else:
                    _success = True
                if _success:
                    self.log("send to {} [{:d}/{:d}]".format(conn_str, _cur_iter, num_iters))
                    break
                else:
                    if _cur_iter < num_iters:
                        time.sleep(0.2)
                    else:
                        break
        return _success
