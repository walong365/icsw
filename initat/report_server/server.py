# Copyright (C) 2016 init.at
#
# this file is part of report-server
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
from initat.cluster.backbone import db_tools
""" report-server, server process """
from multiprocessing import Pool
import zmq

from initat.tools import (logging_tools, process_tools, threading_tools,
    server_mixins)
from initat.cluster.backbone.models.report import ReportHistory
from initat.tools.server_mixins import RemoteCall
from initat.cluster.backbone.models import device
from .config import global_config
from .report import PDFReportGenerator
from .generation import ReportGenerationProcess


@server_mixins.RemoteCallProcess
class server_process(server_mixins.ICSWBasePool,
        server_mixins.RemoteCallMixin, server_mixins.SendToRemoteServerMixin):

    def __init__(self):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init("report-server", global_config)
        self.CC.check_config()
        self.__pid_name = global_config["PID_NAME"]
        self.__msi_block = self._init_msi_block()
        self.CC.log_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._init_network_sockets()
        db_tools.close_connection()
        self.add_process(
            ReportGenerationProcess("report-generation"),
            start=True
        )
        self.register_func("report_finished", self._report_finished)

        self._job_queue = []
        self._wait_result = False

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log(
                "exit already requested, ignoring",
                logging_tools.LOG_LEVEL_WARN,
            )
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=4)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("discovery-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4)
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            client_type="report-server",
            simple_server_bind=True,
            pollin=self.remote_call,
        )

    @RemoteCall()
    def generate_report(self, srv_com, **kwargs):
        # create an empty report history
        report_history = ReportHistory()
        report_history.save()
        self.log(
            'queued report {}'.format(report_history.idx),
            logging_tools.LOG_LEVEL_OK,
        )
        self._job_queue.append(
            {
                'report_history_id': report_history.idx,
                'pk_settings': srv_com['pk_settings'].text,
                'device_ids': srv_com['devices'].text,
            }
        )
        self._run_queue()
        # return the id of the report history object
        srv_com["report_id"] = report_history.idx
        srv_com.set_result("ok")
        return srv_com

    def _report_finished(self, process, src_process, report_history_id):
        self._wait_result = False
        self._run_queue()

    def _run_queue(self):
        if self._job_queue and not self._wait_result:
            # trigger the actual report generation process
            job_args = self._job_queue.pop()
            self._wait_result = True
            self.send_to_process(
                t_process="report-generation",
                m_type="generate",
                **job_args
            )

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()
