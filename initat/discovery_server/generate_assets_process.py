# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, generate assets part """

import time

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import AssetRun, AssetBatch
from initat.tools import logging_tools, threading_tools, process_tools
from .config import global_config


class GenerateAssetsProcess(threading_tools.process_obj):
    def process_init(self):
        global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
        )
        # self.add_process(BuildProcess("build"), start=True)
        db_tools.close_connection()
        self.register_func("process_assets", self._process_assets)
        self.register_func("process_batch_assets", self._process_batch_assets)

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(lev, what)

    def loop_post(self):
        self.__log_template.close()

    def _process_assets(self, asset_run_id, **kwargs):
        self.log("start processing of assetrun {:d}".format(asset_run_id))
        s_time = time.time()
        asset_run = AssetRun.objects.get(pk=asset_run_id)
        try:
            asset_run.generate_assets()
        except:
            _err = process_tools.get_except_info()
            self.log(
                "error in asset_run.generate_assets: {}".format(_err),
                logging_tools.LOG_LEVEL_ERROR
            )
            asset_run.interpret_error_string = _err
            asset_run.save()
        finally:
            e_time = time.time()
            self.log(
                "generate_asset_run for {:d} took {}".format(
                    asset_run.scan_type,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
            asset_run.generate_duration = e_time - s_time
            asset_run.save(update_fields=["generate_duration"])
            self.send_pool_message(
                "process_assets_finished",
                asset_run.idx,
            )

    def _process_batch_assets(self, asset_batch_id, **kwargs):
        self.log("start processing of assetbatch {:d}".format(asset_batch_id))
        s_time = time.time()
        asset_batch = AssetBatch.objects.get(pk=asset_batch_id)
        try:
            asset_batch.generate_assets()
        except:
            _err = process_tools.get_except_info()
            self.log(
                "error in asset_batch.generate_assets: {}".format(_err),
                logging_tools.LOG_LEVEL_ERROR
            )
        finally:
            e_time = time.time()
            self.log(
                "processing of assetbatch {:d} took {}".format(
                    asset_batch_id,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
            self.send_pool_message(
                "process_batch_assets_finished",
                asset_batch.idx,
            )
