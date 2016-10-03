# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of report-server
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
""" report-server, report part """
import traceback
import ast

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device
from initat.cluster.backbone.models.report import ReportHistory
from initat.tools import logging_tools, threading_tools
from initat.report_server.config import global_config
from initat.report_server.report import PDFReportGenerator, XlsxReportGenerator

class ReportGenerationProcess(threading_tools.process_obj):
    def process_init(self):
        global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        db_tools.close_connection()
        self.register_func("generate", self._generate)
        self.__run_idx = 0
        # global job list
        self.__job_list = []
        self.__pending_commands = {}
        # self._init_subsys()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _generate(self, report_history_id, pk_settings, device_ids, format, **kwargs):
        self.log(
            'generating report {}'.format(report_history_id),
            logging_tools.LOG_LEVEL_OK,
        )

        pk_settings = ast.literal_eval(pk_settings)
        device_ids = ast.literal_eval(device_ids)
        devices = device.objects.filter(idx__in=device_ids)

        report_history = ReportHistory.objects.get(idx=report_history_id)

        try:
            if format == "pdf":
                report_generator = PDFReportGenerator(
                    pk_settings,
                    devices,
                    report_history
                )
            else:
                report_generator = XlsxReportGenerator(
                    pk_settings,
                    devices,
                    report_history
                )

            report_generator.generate_report()
        except Exception:
            self.log(traceback.format_exc(), logging_tools.LOG_LEVEL_CRITICAL)

        self.send_pool_message("report_finished", report_history_id)
