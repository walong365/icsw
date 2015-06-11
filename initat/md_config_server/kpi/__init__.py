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
from initat.md_config_server.kpi.kpi_utils import print_tree
from initat.tools import logging_tools, process_tools, server_command, threading_tools


class KpiEvaluationError(Exception):
    def __init__(self, error_report):
        if not isinstance(error_report, (tuple, list)):
            error_report = [error_report]
        super(KpiEvaluationError, self).__init__(error_report)


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

        self.register_timer(self.periodic_update, 60 if global_config["DEBUG"] else 300, instant=True)

        self.register_func('get_kpi_source_data', self._get_kpi_source_data)
        self.register_func('calculate_kpi_preview', self._calculate_kpi_preview)
        self.register_func('calculate_kpi_db', self._calculate_kpi_db)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _get_kpi_source_data(self, srv_com_src, **kwargs):
        srv_com = server_command.srv_command(source=srv_com_src)
        dev_mon_cat_tuples = json.loads(srv_com['dev_mon_cat_tuples'].text)
        start, end = Kpi.objects.parse_kpi_time_range(
            json.loads(srv_com['time_range'].text),
            json.loads(srv_com['time_range_parameter'].text),
        )
        self.log("Calculating KPI source data for: {}; start: {}; end: {}".format(dev_mon_cat_tuples, start, end))
        kpi_set = KpiData(self.log, dev_mon_cat_tuples=dev_mon_cat_tuples).get_kpi_set_for_dev_mon_cat_tuples(
            start,
            end,
        )
        srv_com.set_result("ok")
        srv_com['kpi_set'] = json.dumps(kpi_set.serialize())

        self.send_pool_message("remote_call_async_result", unicode(srv_com))

        self.log("Finished KPI source data")

    def _calculate_kpi_db(self, srv_com_src, **kwargs):
        srv_com = server_command.srv_command(source=srv_com_src)
        kpi_data = KpiData(self.log)
        kpi_pk = int(srv_com['kpi_pk'].text)
        kpi_db = Kpi.objects.get(pk=kpi_pk)
        self._update_single_kpi_result(kpi_data, kpi_db)

    def _update_single_kpi_result(self, kpi_data, kpi_db):
        try:
            initial_kpi_set = kpi_data.get_kpi_set_for_kpi(kpi_db)
            result_str = self._evaluate_kpi(initial_kpi_set, kpi_db)
        except KpiEvaluationError:
            result_str = None
        kpi_db.set_result(result_str, django.utils.timezone.now())



    def periodic_update(self):
        """Recalculate all kpis and save result to database"""
        if License.objects.has_valid_license(LicenseEnum.kpi):
            KpiGlobals.set_context()
            try:
                kpi_data = KpiData(self.log)
            except Exception as e:
                self.log("Exception when gathering kpi data: {}".format(process_tools.get_except_info()))
            else:
                # recalculate kpis
                for kpi_db in Kpi.objects.filter(enabled=True):
                    self._update_single_kpi_result(kpi_data, kpi_db)

                """
                # code for exporting kpi results as csv (written for oekotex KPIs June 2015)

                import csv
                with open("/tmp/a.csv", "w") as f:
                    writer = csv.writer(f)
                    for kpi_db in Kpi.objects.filter(enabled=True):
                        try:
                            print 'data', kpi_data
                            result_str = self._evaluate_kpi(kpi_data, kpi_db)
                        except KpiEvaluationError:
                            result_str = None

                        kpi_db.set_result(result_str, django.utils.timezone.now())
                        writer.writerow([unicode(kpi_db)])

                        writer.writerow(["Month", "Ok", 'Warn', 'Critical', 'Undetermined'])
                        if result_str is None:
                            writer.writerow(["no result"])
                        else:
                            for month, obj in enumerate(json.loads(result_str)['objects']):
                                data = obj['aggregated_tl']
                                ok_val = data.pop('Ok', 0)
                                warn_val = data.pop('Warning', 0)
                                crit_val = data.pop('Critical', 0)
                                undet_val = data.pop('Undetermined', 0) + data.pop("Unknown", 0)
                                if data:
                                    raise RuntimeError("item not used: {}".format(data))

                                format = lambda f: "{:.5f}".format(f)

                                month_table = {
                                    0: "Jan",
                                    1: "Feb",
                                    2: "Mar",
                                    3: "Apr",
                                    4: "May",
                                }
                                writer.writerow([
                                    month_table[month],
                                    format(ok_val),
                                    format(warn_val),
                                    format(crit_val),
                                    format(undet_val)
                                ])
                print 'done'
                """

    def _calculate_kpi_preview(self, srv_com_src, **kwargs):
        """Calculate single kpi with data from command and return result without saving"""
        srv_com = server_command.srv_command(source=srv_com_src)
        KpiGlobals.set_context()

        # set kpi to serialized data (but don't save)
        kpi_serialized = json.loads(srv_com['kpi_serialized'].text)
        kpi_idx = kpi_serialized.get('idx', None)
        kpi_db = Kpi.objects.get(pk=kpi_idx) if kpi_idx is not None else Kpi()
        field_names = frozenset(Kpi._meta.get_all_field_names())
        for k, v in kpi_serialized.iteritems():
            if k in field_names:
                setattr(kpi_db, k, v)

        start, end = Kpi.objects.parse_kpi_time_range(
            kpi_serialized['time_range'],
            kpi_serialized['time_range_parameter'],
        )

        dev_mon_cat_tuples = json.loads(srv_com['dev_mon_cat_tuples'].text)
        initial_kpi_set = KpiData(self.log, dev_mon_cat_tuples=dev_mon_cat_tuples).get_kpi_set_for_dev_mon_cat_tuples(
            start=start, end=end,
        )

        self.log("Calculating KPI {} with custom formula".format(kpi_db))
        try:
            srv_com['kpi_set'] = self._evaluate_kpi(initial_kpi_set, kpi_db)
        except KpiEvaluationError as e:
            srv_com['kpi_error_report'] = json.dumps(e.message)
        srv_com.set_result("ok")

        self.send_pool_message("remote_call_async_result", unicode(srv_com))
        self.log("Finished calculating KPI")

    def _evaluate_kpi(self, kpi_set, kpi_db):
        """Evaluates given kpi on data returning the result as string or raising KpiEvaluationError
        Does not write to the database.
        Kpi context must be set before call.
        Returns json-ified serialized kpi set
        """
        self.log("Evaluating kpi {}".format(kpi_db))
        # print '\nevaluating kpi', kpi_db
        # print eval("return {}".format(kpi_db.formula), {'data': kpi_set})
        eval_globals = {
            'initial_data': kpi_set,
            'KpiSet': KpiSet,
            'KpiObject': KpiObject,
            'KpiResult': KpiResult,
        }
        eval_locals = {}
        result_str = None
        # build function such that return works in the kpi function
        eval_formula = u"def _kpi():\n"
        # indent
        eval_formula += u"\n".join(((u"    " + line) for line in kpi_db.formula.split(u"\n"))) + u"\n"
        eval_formula += u"kpi = _kpi()\n"
        try:
            # KpiGlobals are used for evaluation, but not exposed to kpi user
            KpiGlobals.current_kpi = kpi_db
            exec (eval_formula, eval_globals, eval_locals)
        except Exception as e:
            self.log(e)
            error_report = [u"Exception while calculating kpi {}: {}".format(kpi_db, e)]
            for idx, line in enumerate(traceback.format_exc().split("\n")):
                if idx not in (1, 2):  # these are internal
                    error_report.append(line)

                self.log(line)

            raise KpiEvaluationError(error_report)
        else:
            if 'kpi' not in eval_locals:
                msg = "Internal error evaluating kpis (1)"
                self.log(msg)
                raise KpiEvaluationError(msg)
            else:
                self.log("{} successfully evaluated".format(kpi_db))
                result = eval_locals['kpi']

                if result is None:
                    raise KpiEvaluationError("Kpi formula did not return a result.\n" +
                                             "Please use `return kpi_set`, where kpi_set is your result.")

                if not isinstance(result, KpiSet):
                    raise KpiEvaluationError("Result is not a KpiSet but {}".format(type(result)))

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
