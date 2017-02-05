# Copyright (C) 2014-2015,2017 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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

"""
class for encoding and decoding icinga command names
separated to enable flawless import from webfrontend
"""

from initat.tools import logging_tools

__all__ = [
    "HostServiceIDUtil",
]


class HostServiceIDUtil(object):

    """
    NOTE: we could also encode hosts like this, but then we need to always use this host identification
          throughout all of the icinga config, which does not seem worth it as it then becomes hard to read.
    @classmethod
    def create_host_description(cls, host_pk):
        return "host:{}".format(host_pk)

    @classmethod
    def parse_host_description(cls, host_spec):
        data = host_spec.split(":")
        if len(data) == 2:
            if data[0] == 'host':
                return int(data[1])
        return None
    """

    @classmethod
    def create_host_service_description(cls, host_pk, s_check, info):
        '''
        Create a string by which we can identify the service. Used to write to icinga log file.
        Use create_host_service_description_direct if you don't have a check_command object
        :param s_check: initat.md_config_server.config.check_command.check_command
        '''
        return cls.create_host_service_description_direct(
            host_pk,
            s_check,
            info=info
        )

    @classmethod
    def create_host_service_description_direct(
        cls, host_pk, check_command, info=""
    ):
        if check_command is not None:
            # new format
            retval = "uuid_hc:{}:{}:{}".format(
                host_pk,
                check_command.uuid,
                info,
            )
        else:
            retval = "unstructured: {}".format(info)
        return retval

    @classmethod
    def parse_host_service_description(cls, service_spec, log=None):
        '''
        "Inverse" of create_host_service_description
        '''
        data = service_spec.split(':', 1)
        retval = (None, None, None)
        if len(data) == 2:
            if data[0] == "uuid_hc":
                # new format
                if data[1].count(":") >= 3:
                    service_data = data[1].split(":", 3)
                    host_pk, mc_uuid, info = service_data.split(":", 3)
                    retval = (int(host_pk), mc_uuid, info)
            elif data[0] == 'host_check':
                if data[1].count(":") >= 2:
                    service_data = data[1].split(":", 2)
                    host_pk, service_pk, info = service_data
                    retval = (int(host_pk), int(service_pk), info)
            elif data[0] == "s_host_check":
                if data[1].count(":") >= 3:
                    service_data = data[1].split(":", 3)
                    host_pk, service_pk, s_check_pk, info = service_data
                    retval = (int(host_pk), int(service_pk), info)
            elif data[0] == 'unstructured':
                pass
            else:
                if log:
                    log(
                        "invalid service description: {}".format(
                            service_spec
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
        if retval[0] is None:
            log(
                "error parsing service_spec '{}'".format(
                    service_spec
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        return retval
