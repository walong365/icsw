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
import time
from lxml import etree
from lxml.builder import E

import django.utils.timezone
from django.db import connection
import zmq
from initat.cluster.backbone.available_licenses import LicenseEnum
from initat.cluster.backbone.models import LicenseUsage, License
from initat.cluster.backbone.models.license import LicenseViolation
from initat.tools import threading_tools, logging_tools, uuid_tools, process_tools, server_command
from initat.md_config_server.config import global_config
from initat.host_monitoring import hm_classes


class LicenseChecker(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()

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

    @staticmethod
    def check(log):
        log("starting license violation checking")

        license_usages = {license: LicenseUsage.get_license_usage(license) for license in LicenseEnum}

        # violation checking
        for license, usage in license_usages.iteritems():
            violated = False

            if usage:  # only check for violation if there is actually some kind of usage
                violated = not License.objects.has_valid_license(license, usage, ignore_violations=True)

            try:
                violation = LicenseViolation.objects.get(license=license.name)
                if not violated:
                    log("violation {} has ended".format(violation))
                    violation.delete()
                else:
                    # still violate, check if now grace period is violated too
                    if not violation.hard and django.utils.timezone.now() > violation.date + LicenseUsage.GRACE_PERIOD:
                        log("violation {} is transformed into a hard violation".format(violation))
                        violation.hard = True
                        violation.save()
            except LicenseViolation.DoesNotExist:
                if violated:
                    new_violation = LicenseViolation(license=license.name)
                    new_violation.save()
                    log("violation {} detected".format(new_violation))

        log("finished license violation checking")
        return license_usages
