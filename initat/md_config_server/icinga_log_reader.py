# Copyright (C) 2014 Bernhard Mallinger, init.at
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

from django.db.models import Q
import logging_tools
import os
import datetime
import itertools
import pprint
from collections import namedtuple

from initat.md_config_server.config import global_config
from initat.cluster.backbone.models.monitoring import mon_check_command,\
    mon_icinga_log_raw_host_data, mon_icinga_log_raw_service_data
from initat.cluster.backbone.models import device


# TODO:
# first, implement historic data parsing
# then, implement parsing for current data, i.e. where we have a host_service_mapping and our new custom icinga log entries


class icinga_log_reader(object):
    class malformed_icinga_log_entry(RuntimeError):
        pass

    class unknown_host_error(RuntimeError):
        pass

    class unknown_service_error(RuntimeError):
        pass

    @staticmethod
    def get_icinga_log_archive_dir():
        return os.path.join(global_config['MD_BASEDIR'], 'var', 'archives')

    def __init__(self, log):
        self.log = log
        self._historic_service_map = {description.replace(" ", "_").lower(): pk
                                      for (pk, description) in mon_check_command.objects.all().values_list('pk', 'description')}
        self._historic_host_map = {entry.full_name: entry.pk for entry in device.objects.all()}
        # pprint.pprint(self._historic_service_map)
        self.parse_archive()

    def update(self):
        '''Called periodically'''

    def parse_archive(self):
        # sort
        logfiles_date_data = []
        for logfilepath in os.listdir(icinga_log_reader.get_icinga_log_archive_dir()):
            unused, month, day, year, num = logfilepath.split("-")
            logfilepath = os.path.join(icinga_log_reader.get_icinga_log_archive_dir(), logfilepath)
            logfiles_date_data.append((year, month, day, num, logfilepath))

        # TODO: logic what to read, what has been read
        for unused1, unused2, unused3, unused4, logfilepath in sorted(logfiles_date_data):
            with open(logfilepath, 'r') as logfile:
                cur_line = None  # just for nicer error handling below
                host_states = []
                service_states = []
                try:
                    print 'reading ', logfilepath
                    self.log("reading log file {}".format(logfilepath))
                    # strip '\n'
                    lines = enumerate((line[:-1] for line in logfile.readlines()))

                    line_iter = iter(lines)

                    #
                    # check if header is ok
                    first_line_data = next(line_iter)
                    second_line_data = next(line_iter)

                    # TODO: first start has other header
                    if self._parse_line(first_line_data).kind != "LOG ROTATION" or self._parse_line(second_line_data).kind != "LOG VERSION":
                        self.log("First lines of log file {} do not match pattern".format(logfilepath), logging_tools.LOG_LEVEL_WARN)
                        # treat it as data
                        line_iter = itertools.chain([first_line_data[1], second_line_data[2]], line_iter)

                    def create_host_entry(cur_line, full_system_state_entry):
                        # TODO: make this into a proper method if required by non-historic data parsing (only captured var is logfilepath)
                        try:
                            host, state, state_type, msg = self._parse_host_alert_historic(cur_line.info)
                        except self.unknown_host_error as e:
                            self.log("In file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
                            return None
                        else:
                            return (
                                mon_icinga_log_raw_host_data(
                                    date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                                    device_id=host,
                                    state_type=state_type,
                                    state=state,
                                    full_system_state_entry=full_system_state_entry,
                                    msg=msg
                                )
                            )

                    def create_service_entry(cur_line, full_system_state_entry):
                        # TODO: make this into a proper method if required by non-historic data parsing (only captured var is logfilepath)
                        try:
                            host, service, state, state_type, msg = self._parse_service_alert_historic(cur_line.info)
                        except (self.unknown_host_error, self.unknown_service_error) as e:
                            self.log("In file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
                        else:
                            service_states.append(
                                mon_icinga_log_raw_service_data(
                                    date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                                    device_id=host,
                                    service_id=service,
                                    state_type=state_type,
                                    state=state,
                                    full_system_state_entry=full_system_state_entry,
                                    msg=msg
                                )
                            )

                    #
                    # next comes the current host state
                    cur_line = self._parse_line(next(line_iter))
                    while cur_line.kind == 'CURRENT HOST STATE':
                        entry = create_host_entry(cur_line, True)
                        if entry:
                            host_states.append(entry)

                        cur_line = self._parse_line(next(line_iter))


                    #
                    # next comes the current service state
                    while cur_line.kind == 'CURRENT SERVICE STATE':
                        entry = create_service_entry(cur_line, True)
                        if entry:
                            service_states.append(entry)

                        cur_line = self._parse_line(next(line_iter))


                    #
                    # from now on, we heave service and host alerts

                    while True:  # run until StopIteration

                        if cur_line.kind == 'SERVICE ALERT':
                            entry = create_service_entry(cur_line, False)
                            if entry:
                                service_states.append(entry)

                        elif cur_line.kind == 'HOST ALERT':
                            entry = create_host_entry(cur_line, False)
                            if entry:
                                host_states.append(entry)

                        else:
                            pass  # line is not of interest to us

                        # this throws to end the iteration
                        cur_line = self._parse_line(next(line_iter))

                except self.malformed_icinga_log_entry as e:
                    raise self.malformed_icinga_log_entry(
                        "In {} line {}: {}".format(logfilepath, cur_line.line_no if cur_line else None, e.message)
                      )
                except StopIteration:
                    # we are done
                    mon_icinga_log_raw_host_data.objects.bulk_create(host_states)
                    mon_icinga_log_raw_service_data.objects.bulk_create(service_states)
                    self.log("created {} host state entries, {} service state entries".format(len(host_states), len(service_states)))

    icinga_log_line = namedtuple('icinga_log_line', ('timestamp', 'kind', 'info', 'line_no'))

    @classmethod
    def _parse_line(cls, line_data):
        '''
        :param (int, str) line_data:
        :return icinga_log_line
        '''
        line_no, line = line_data
        # format is:
        # [timestamp] line_type: info
        data = line.split(" ", 1)
        if len(data) != 2:
            raise cls.malformed_icinga_log_entry("Malformed line {}: {} (error #1)".format(line_no, line))
        timestamp_raw, info_raw = data

        try:
            timestamp = int(timestamp_raw[1:-1])  # remove first and last char
        except:
            raise cls.malformed_icinga_log_entry("Malformed line {}: {} (error #2)".format(line_no, line))

        data2 = info_raw.split(": ", 1)
        if len(data2) == 2:
            kind, info = data2
        else:
            # no line formatted as we need it
            kind = None
            info = info_raw

        return cls.icinga_log_line(timestamp, kind, info, line_no)

    def _parse_host_alert_historic(self, info):
        '''
        :return (int, str, str, str)
        '''
        # format is:
        # host;(DOWN|UP);(SOFT|HARD);???;msg

        data = info.split(";", 4)
        if len(data) != 5:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #1)".format(info))

        host = self._resolve_host_historic(data[0])
        if not host:
            raise self.unknown_host_error("Failed to resolve host: {} (error #2)".format(data[0]))

        state = {"DOWN": "D", "UP": "UP", "UNREACHABLE": "UR"}.get(data[1], None)  # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #3)".format(info))

        state_type = {"SOFT": "S", "HARD": "H"}.get(data[2], None)  # format as in db table
        if not state_type:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #4)".format(info))

        msg = data[4]

        return host, state, state_type, msg

    def _parse_service_alert_historic(self, info):
        '''
        :return (int, int, str, str, str)
        '''
        # format is:
        # host;service;(OK|WARNING|UNKNOWN|CRITICAL);(SOFT|HARD);???;msg
        data = info.split(";", 5)
        if len(data) != 6:
            raise self.malformed_icinga_log_entry("Malformed service entry: {} (error #1)".format(info))

        host = self._resolve_host_historic(data[0])
        if not host:
            raise self.unknown_host_error("Failed to resolve host: {} (error #2)".format(data[0]))

        service = self._resolve_service_historic(data[1])
        if not service:
            raise self.unknown_service_error("Failed to resolve service : {} (error #3)".format(data[1]))

        state = {"OK": "O", "WARNING": "W", "UNKNOWN": "U", "CRITICAL": "C"}.get(data[2], None)  # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed service entry: {} (error #4)".format(info))

        state_type = {"SOFT": "S", "HARD": "H"}.get(data[3], None)  # format as in db table
        if not state_type:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #5)".format(info))

        msg = data[5]

        return host, service, state, state_type, msg

    def _resolve_host_historic(self, host_spec):
        '''
        @return int: pk of host
        '''
        return self._historic_host_map.get(host_spec, None)

    def _resolve_service_historic(self, service_spec):
        '''
        @return int: ok of mon_check_command
        '''
        # we can't really know which services have been defined in the past, so we just check
        # the check command description. This works only for check commands with 1 service, so
        # excludes all special commands and cluster commands.
        return self._historic_service_map.get(service_spec.replace(" ", "_").lower(), None)







