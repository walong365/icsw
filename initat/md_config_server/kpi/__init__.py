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
from initat.cluster.backbone.models import Kpi
from initat.md_config_server.config.objects import global_config
from initat.md_config_server.kpi.kpi_data import KpiData
from initat.md_config_server.kpi.kpi_language import KpiObject, KpiResult, KpiSet, KpiOperation, KpiGlobals
from initat.md_config_server.kpi.kpi_utils import print_tree
import logging_tools
import process_tools
import threading_tools


class KpiProcess(threading_tools.process_obj):

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()

        self.register_timer(self.update, 30 if global_config["DEBUG"] else 300, instant=True)
        # self.update()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def update(self):
        KpiGlobals.set_context()

        try:
            data = KpiData(self.log)
        except Exception as e:
            self.log("Exception when gathering kpi data: {}".format(process_tools.get_except_info()))
            for line in traceback.format_exc().split("\n"):
                self.log(line)
        else:

            # recalculate kpis

            # calculate kpis, such that drill down data is present
            # print '\n\nkpi evaluation\n'

            for kpi_db in Kpi.objects.filter(enabled=True):

                self.log("Evaluating kpi {}".format(kpi_db))

                # print '\nevaluating kpi', kpi_db
                kpi_set = KpiSet(data.get_data_for_kpi(kpi_db),
                                 origin=KpiOperation(type=KpiOperation.Type.initial))

                # print eval("return {}".format(kpi_db.formula), {'data': kpi_set})
                eval_globals = {'data': kpi_set, 'KpiSet': KpiSet, 'KpiObject': KpiObject, 'KpiResult': KpiResult}
                eval_locals = {}
                result_str = None
                try:
                    # KpiGlobals are used for evaluation, but not exposed to kpi user
                    KpiGlobals.current_kpi = kpi_db
                    exec(kpi_db.formula, eval_globals, eval_locals)
                except Exception as e:
                    self.log(e)
                    self.log("Exception while executing kpi {} with formula {}: {}".format(kpi_db, kpi_db.formula, e))
                    for line in traceback.format_exc().split("\n"):
                        self.log(line)
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

                kpi_db.set_result(result_str, django.utils.timezone.now())

                """

                class MyNV(ast.NodeVisitor):
                    def visit_BinOp(self, node):
                        self.generic_visit(node)
                        self.show_node(node)

                    def visit_Name(self, node):
                        self.generic_visit(node)
                        self.show_node(node)

                    def visit_Call(self, node):
                        self.generic_visit(node)
                        self.show_node(node)

                    def show_node(self, node):
                        import codegen
                        # print '\ncall node', node, node.func, node.args, node.kwargs, node.starargs
                        print '\n node', node, codegen.to_source(node)
                        res = eval(compile(ast.Expression(node), '<string>', mode='eval'), eval_globals)
                        print 'eval:', res

                print 'gonna eval: '
                print "\"" * 3
                print kpi_db.formula
                print "\"" * 3
            if True:
                d = {}
                exec(kpi_db.formula, eval_globals, d)
                print 'kpi', d
                print_tree(d['kpi'])
            else:
                kpi_ast = ast.parse(kpi_db.formula, mode='exec')
                print 'before visit'
                MyNV().visit(kpi_ast)
                print '\nast dump:', astdump(kpi_ast)

            """
            """
            print 'chil'
            for i in ast.iter_fields(kpi_ast):
                print i
            """
