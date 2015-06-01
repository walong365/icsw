# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>
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

import json
# noinspection PyUnresolvedReferences
import pprint
import traceback
from django.db import connection
import django.utils.timezone
from initat.cluster.backbone.available_licenses import LicenseEnum
from initat.cluster.backbone.models import Kpi, License
from initat.md_config_server.kpi.kpi_data import KpiData
from initat.md_config_server.kpi.kpi_language import KpiObject, KpiResult, KpiSet, KpiOperation, KpiGlobals
from initat.md_config_server.kpi.kpi_utils import print_tree, KpiUtils
from initat.tools import logging_tools, process_tools, server_command, threading_tools


class KpiEvaluationError(Exception):
    pass


class KpiProcess(threading_tools.process_obj):

    def process_init(self):
        from initat.md_config_server.config.objects import global_config
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()

        self.register_timer(self.update, 60 if global_config["DEBUG"] else 300, instant=True)

        self.register_func('get_kpi_source_data', self._get_kpi_source_data)
        self.register_func('calculate_kpi', self._calculate_kpi)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _get_kpi_source_data(self, srv_com_src, **kwargs):
        srv_com = server_command.srv_command(source=srv_com_src)
        dev_mon_cat_tuples = json.loads(srv_com['tuples'].text)
        start, end = KpiUtils.parse_kpi_time_range(
            json.loads(srv_com['time_range'].text),
            json.loads(srv_com['time_range_parameter'].text),
        )
        kpi_set = KpiData(self.log, dev_mon_cat_tuples=dev_mon_cat_tuples).get_kpi_set_for_dev_mon_cat_tuples(
            start,
            end,
        )
        srv_com.set_result("ok")
        srv_com['kpi_set'] = json.dumps(kpi_set.serialize())

        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def update(self):
        """Recalculate all kpis and save result to database"""
        if License.objects.has_valid_license(LicenseEnum.kpi):
            KpiGlobals.set_context()
            try:
                data = KpiData(self.log)
            except Exception as e:
                self.log("Exception when gathering kpi data: {}".format(process_tools.get_except_info()))
            else:
                # recalculate kpis
                for kpi_db in Kpi.objects.filter(enabled=True):
                    try:
                        result_str = self._evaluate_kpi(data, kpi_db)
                    except KpiEvaluationError:
                        result_str = None
                    kpi_db.set_result(result_str, django.utils.timezone.now())

    def _calculate_kpi(self, srv_com_src, **kwargs):
        """Calculate single kpi"""
        srv_com = server_command.srv_command(source=srv_com_src)
        KpiGlobals.set_context()
        data = KpiData(self.log)
        kpi_db = Kpi.objects.get(pk=int(srv_com['kpi_pk'].text))
        kpi_db.formula = srv_com['formula'].text  # don't save
        try:
            srv_com['kpi_set'] = self._evaluate_kpi(data, kpi_db)
        except KpiEvaluationError as e:
            srv_com['kpi_error_report'] = json.dumps(e.message)
        srv_com.set_result("ok")

        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _evaluate_kpi(self, data, kpi_db):
        """Evaluates given kpi on data returning the result as string or raising KpiEvaluationError
        Does not write to the database.
        Kpi context must be set before call.
        Returns json-ified serialized kpi set
        """
        self.log("Evaluating kpi {}".format(kpi_db))
        # print '\nevaluating kpi', kpi_db
        # print eval("return {}".format(kpi_db.formula), {'data': kpi_set})
        eval_globals = {
            'data': data.get_kpi_set_for_kpi(kpi_db),
            'KpiSet': KpiSet,
            'KpiObject': KpiObject,
            'KpiResult': KpiResult,
        }
        eval_locals = {}
        result_str = None
        try:
            # KpiGlobals are used for evaluation, but not exposed to kpi user
            KpiGlobals.current_kpi = kpi_db
            exec (kpi_db.formula, eval_globals, eval_locals)
        except Exception as e:
            self.log(e)
            error_report = [u"Exception while calculating kpi {}: {}".format(kpi_db, e)]
            for idx, line in enumerate(traceback.format_exc().split("\n")):
                if idx not in (1, 2):  # these are internal
                    error_report.append(line)

                self.log(line)

            raise KpiEvaluationError(error_report)
        else:
            self.log("Kpi {} successfully evaluated".format(kpi_db))
            if 'kpi' not in eval_locals:
                self.log("Kpi {} does not define result".format(kpi_db))
            else:
                result = eval_locals['kpi']

                # print 'full result',
                # result.dump()
                # print_tree(result)

                serialized = result.serialize()
                # print 'serialized:', serialized
                result_str = json.dumps(serialized)

                try:
                    # there are objects which can be serialized but not deserialized, e.g. enums
                    json.loads(result_str)
                except ValueError:
                    self.log("result string can be serialized but not deserialized: {}".format(result_str),
                             logging_tools.LOG_LEVEL_ERROR)
                    result_str = None
        finally:
            KpiGlobals.current_kpi = None
        return result_str
