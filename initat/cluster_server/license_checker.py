# Copyright (C) 2015-2016 Bernhard Mallinger, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <mallinger@init.at>
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
import time

import zmq

from initat.cluster.backbone import db_tools
from initat.host_monitoring import hm_classes
from initat.md_config_server.config import global_config
from initat.tools import threading_tools, logging_tools, process_tools, server_command


class LicenseChecker(threading_tools.process_obj):
    def process_init(self):
        global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        db_tools.close_connection()

        # can be triggered
        # self.register_func("check_license_violations", self._check_from_command)

        # and is run periodically
        self._update_interval = 30 * 60
        self.register_timer(self.periodic_update, self._update_interval, instant=True)

        self._init_network()

    def _init_network(self):
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
        vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def periodic_update(self):
        # actual check
        license_usages = self.check(self.log)

        # also report usage value as rrd
        self.report_usage_values(license_usages)

    def report_usage_values(self, license_usages):
        drop_com = server_command.srv_command(command="set_vector")
        _bldr = drop_com.builder()
        license_usage_vector = _bldr("values")
        valid_until = int(time.time()) + self._update_interval
        for license, usage in license_usages.iteritems():
            for param_name, value in usage.iteritems():
                license_usage_vector.append(
                    hm_classes.mvect_entry(
                        "license_usage.{}.{}".format(license.name, param_name.name),
                        info="Usage of {} for {}".format(
                            logging_tools.get_plural(param_name.name, num=2, show_int=False),
                            license.name,
                        ),
                        unit="1",
                        base="1",
                        v_type="i",
                        factor="1",
                        value=unicode(value),
                        valid_until=valid_until,
                    ).build_xml(_bldr)
                )
        drop_com['license_usage_vector'] = license_usage_vector
        drop_com['license_usage_vector'].attrib['type'] = 'vector'

        self.vector_socket.send_unicode(unicode(drop_com))

