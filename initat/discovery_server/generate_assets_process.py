# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, generate assets part """

import time

from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import AssetRun
from initat.tools import logging_tools, threading_tools, process_tools
from .config import global_config


class GenerateAssetsProcess(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # self.add_process(build_process("build"), start=True)
        db_tools.close_connection()
        self.register_func("process_assets", self._process_assets)

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(lev, what)

    def loop_post(self):
        self.__log_template.close()

    def _process_assets(self, *args, **kwargs):
        db_idx = args[0]
        self.log("start processing of assetrun {:d}".format(db_idx))
        s_time = time.time()
        run_db_obj = AssetRun.objects.get(Q(pk=db_idx))
        try:
            run_db_obj.generate_assets()
        except:
            _err = process_tools.get_except_info()
            self.log(
                "error in generate_assets: {}".format(_err),
                logging_tools.LOG_LEVEL_ERROR
            )
            run_db_obj.interpret_error_string = _err
            run_db_obj.save()
        finally:
            e_time = time.time()
            self.log(
                "generate_asset_run for {:d} took {}".format(
                    run_db_obj.scan_type,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
            run_db_obj.generate_duration = e_time - s_time
            run_db_obj.save(update_fields=["generate_duration"])
