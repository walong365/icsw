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

import logging_tools

import django.utils.timezone
from django.db import connection

from initat.cluster.backbone.available_licenses import LicenseEnum
from initat.cluster.backbone.models import LicenseUsage, License
from initat.cluster.backbone.models.license import LicenseViolation
from initat.tools import threading_tools, server_command
from initat.md_config_server.config import global_config


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
        self.register_func("check_license", self._check_from_command)

        # and is run periodically
        self.register_timer(self.check, 30 * 60, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _check_from_command(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        self.check()
        srv_com.set_result("worked")  # need some result, else there is a warning
        self.send_pool_message("send_command", src_id, unicode(srv_com))

    def check(self):
        self.log("starting license violation checking")
        for license in LicenseEnum:
            usage = LicenseUsage.get_license_usage(license)
            violated = False
            if usage:
                violated = not License.objects.has_valid_license(license, usage, ignore_violations=True)

            try:
                violation = LicenseViolation.objects.get(license=license.name)
                if not violated:
                    self.log("violation {} has ended".format(violation))
                    violation.delete()
                else:
                    # still violate, check if now grace period is violated too
                    if not violation.hard and django.utils.timezone.now() > violation.date + LicenseUsage.GRACE_PERIOD:
                        self.log("violation {} is transformed into a hard violation".format(violation))
                        violation.hard = True
                        violation.save()
            except LicenseViolation.DoesNotExist:
                if violated:
                    new_violation = LicenseViolation(license=license.name)
                    new_violation.save()
                    self.log("violation {} detected".format(new_violation))
