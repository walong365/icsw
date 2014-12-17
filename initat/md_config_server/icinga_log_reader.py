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

import logging_tools
import os
import datetime
import glob
import itertools
import pprint  # @UnusedImport
from collections import namedtuple

from initat.md_config_server.config import global_config
from initat.cluster.backbone.models.monitoring import mon_check_command,\
    mon_icinga_log_raw_host_data, mon_icinga_log_raw_service_data, mon_icinga_log_file,\
    mon_icinga_log_last_read
from initat.cluster.backbone.models import device
from initat.md_config_server.build import host_service_map
from django.db import connection


class icinga_log_reader(object):
    class malformed_icinga_log_entry(RuntimeError):
        pass

    class unknown_host_error(RuntimeError):
        pass

    class unknown_service_error(RuntimeError):
        pass

    @staticmethod
    def get_icinga_log_archive_dir():
        # TODO: can use value from main_config?
        return os.path.join(global_config['MD_BASEDIR'], 'var', 'archives')

    @staticmethod
    def get_icinga_log_file():
        # TODO: can use value from main_config?
        return os.path.join(global_config['MD_BASEDIR'], 'var', '{}.log'.format(global_config['MD_TYPE']))

    class constants(object):
        icinga_service_alert = 'SERVICE ALERT'
        icinga_current_service_state = 'CURRENT SERVICE STATE'
        icinga_host_alert = 'HOST ALERT'
        icinga_current_host_state = 'CURRENT Host STATE'

    def __init__(self, log):
        self.log = log
        self._historic_service_map = {description.replace(" ", "_").lower(): pk
                                      for (pk, description) in mon_check_command.objects.all().values_list('pk', 'description')}
        self._historic_host_map = {entry.full_name: entry.pk for entry in device.objects.all()}
        # pprint.pprint(self._historic_service_map)

    def update(self):
        '''Called periodically'''
        # check for log rotation
        connection.close()
        self._current_host_service_data = host_service_map.get_mapping(self.log)

        if mon_icinga_log_last_read.objects.all():
            last_read = mon_icinga_log_last_read.objects.all()[0]
            self.log("last icinga read until: {}".format(datetime.datetime.fromtimestamp(last_read.timestamp)))
        else:
            self.log("no earlier icinga log read, reading archive")
            files = os.listdir(icinga_log_reader.get_icinga_log_archive_dir())
            last_read_timestamp = self.parse_archive(files)
            if last_read_timestamp:
                last_read = self._update_last_read(0, last_read_timestamp)
            else:
                self.log("no earlier icinga log read and no archive data")
                # there was no earlier read and we weren't able to read anything from the archive, so assume there is none
                last_read = mon_icinga_log_last_read()
                last_read.timestamp = datetime.datetime.now() - datetime.timedelta(days=1)  # safe time in past, but not too far cause we check logs of each day
                last_read.position = 0

        try:
            logfile = open(self.get_icinga_log_file(), "r")
        except OSError as e:
            self.log(u"Failed to open log file {} : {}".format(self.get_icinga_log_file(), e))
        else:
            logfile.seek(last_read.position)

            last_read_line = logfile.readline()

            file_position_valid = False
            if last_read_line:  # empty string (=False) means end, else we at least have '\n'
                cur_line = self._parse_line((None, last_read_line))
                file_position_valid = cur_line.timestamp == last_read.timestamp

            if file_position_valid:
                self.log("continuing to read in current icinga log file")
                # no log rotation, continue reading current file
                self.parse_current_log_file(logfile)
            else:
                self.log("detected icinga log rotation")
                # cur log file does not correspond to where we last read.
                # we have to check the archive for whatever we have missed.
                last_read_date = datetime.date.fromtimestamp(last_read.timestamp)
                missed_timedelta = datetime.date.today() - last_read_date

                files_to_check = []

                # get days by filename
                for day_missed in xrange(missed_timedelta.days+1):  # include last
                    missed_log_day = last_read_date + datetime.timedelta(days=day_missed)

                    day_files = glob.glob(os.path.join(icinga_log_reader.get_icinga_log_archive_dir(),
                                                       "*-{}-{}-{}-*.log".format(missed_log_day.month, missed_log_day.day, missed_log_day.year)))
                    files_to_check.extend(day_files)

                # read archive
                last_read_timestamp = self.parse_archive(files_to_check, last_read.timestamp)
                self._update_last_read(0, last_read_timestamp)

                self.log("finished catching up with archive, continuing with current icinga log file")
                # start reading new file
                logfile.seek(0)
                self.parse_current_log_file(logfile)

    def parse_current_log_file(self, logfile):
        '''
        :param file logfile: Parsing starts at position of logfile. Must be the main icinga log file.
        '''
        # TODO: if we want the line number here, we would have to save it in last_read

        host_states = []
        service_states = []
        cur_line = None
        for line in (i.rstrip("\n") for i in logfile):
            cur_line = self._parse_line((None, line))
            if cur_line.kind in (self.constants.icinga_service_alert, self.constants.icinga_current_service_state):
                entry = self.create_service_entry(cur_line, cur_line.kind == self.constants.icinga_current_service_state, None)
                if entry:
                    service_states.append(entry)
            elif cur_line.kind in (self.constants.icinga_host_alert, self.constants.icinga_current_host_state):
                entry = self.create_host_entry(cur_line, cur_line.kind == self.constants.icinga_current_host_state, None)
                if entry:
                    host_states.append(entry)
            else:
                pass  # line is not of interest to us

        mon_icinga_log_raw_host_data.objects.bulk_create(host_states)
        mon_icinga_log_raw_service_data.objects.bulk_create(service_states)
        self.log("created {} host state entries, {} service state entries for the current icinga log file".format(len(host_states), len(service_states)))

        if cur_line:
            self._update_last_read(logfile.tell(), cur_line.timestamp)

        # TODO: make malformed and unresolvable errors non-critical

    def _update_last_read(self, position, timestamp):
        """Keep track of which data was read. May be called with older timestamp (will be discarded)"""
        if mon_icinga_log_last_read.objects.all():
            last_read = mon_icinga_log_last_read.objects.all()[0]
            if last_read.timestamp > timestamp:
                return  # tried to update with older timestamp
        else:
            last_read = mon_icinga_log_last_read()
        self.log("updating last read icinga log to pos: {} time: {}".format(position, timestamp))
        last_read.timestamp = timestamp
        last_read.position = position
        last_read.save()
        return last_read

    def parse_archive(self, files, start_at=None):
        '''
        :param list files: list of files to consider (will be sorted here)
        :param int start_at: only consider entries older than start_at
        :param int start_at: only consider entries older than start_at
        :return int: last read timestamp
        '''
        last_read_timestamp = None
        # sort
        logfiles_date_data = []
        for logfilepath in files:
            unused, month, day, year, hour = logfilepath.split("-")
            logfilepath = os.path.join(icinga_log_reader.get_icinga_log_archive_dir(), logfilepath)
            logfiles_date_data.append((year, month, day, hour, logfilepath))

        for unused1, unused2, unused3, unused4, logfilepath in sorted(logfiles_date_data):
            with open(logfilepath, 'r') as logfile:
                cur_line = None  # just for nicer error handling below
                logfile_db = mon_icinga_log_file(filepath=logfilepath)
                logfile_db.save()
                host_states = []
                service_states = []
                try:
                    print 'reading ', logfilepath
                    self.log("reading log file {}".format(logfilepath))
                    # strip '\n'
                    lines = enumerate(line.rstrip("\n") for line in logfile)

                    line_iter = iter(lines)

                    #
                    # check if header is ok
                    first_line_data = next(line_iter)
                    second_line_data = next(line_iter)

                    if self._parse_line(first_line_data).kind != "LOG ROTATION" or self._parse_line(second_line_data).kind != "LOG VERSION":
                        self.log("First lines of log file {} do not match pattern".format(logfilepath), logging_tools.LOG_LEVEL_WARN)
                        # treat it as data
                        line_iter = itertools.chain([first_line_data[1], second_line_data[2]], line_iter)

                    self.log("a")
                    #
                    # next comes the current host state
                    cur_line = self._parse_line(next(line_iter))
                    while cur_line.kind == self.constants.icinga_current_host_state:
                        if not start_at or cur_line.timestamp > start_at:
                            entry = self.create_host_entry(cur_line, True, logfilepath, logfile_db)
                            if entry:
                                host_states.append(entry)

                        cur_line = self._parse_line(next(line_iter))

                    self.log("b")
                    #
                    # next comes the current service state
                    while cur_line.kind == self.constants.icinga_current_service_state:
                        if not start_at or cur_line.timestamp > start_at:
                            entry = self.create_service_entry(cur_line, True, logfilepath, logfile_db)
                            if entry:
                                service_states.append(entry)

                        cur_line = self._parse_line(next(line_iter))

                    #
                    # from now on, we heave service and host alerts

                    while True:  # run until StopIteration

                        self.log(cur_line.info)
                        if not start_at or cur_line.timestamp > start_at:
                            if cur_line.kind == self.constants.icinga_service_alert:
                                entry = self.create_service_entry(cur_line, False, logfilepath, logfile_db)
                                if entry:
                                    service_states.append(entry)
                            elif cur_line.kind == self.constants.icinga_host_alert:
                                entry = self.create_host_entry(cur_line, False, logfilepath, logfile_db)
                                self.log('host_DEBUG'+str( entry))
                                if entry:
                                    host_states.append(entry)
                            else:
                                pass  # line is not of interest to us
                                self.log("uninteresting kind: "+str(cur_line.kind))

                        # this throws to end the iteration
                        cur_line = self._parse_line(next(line_iter))

                except self.malformed_icinga_log_entry as e:
                    # TODO: this shouldn't be critical in the final version
                    raise self.malformed_icinga_log_entry(
                        "In {} line {}: {}".format(logfilepath, cur_line.line_no if cur_line else None, e.message)
                        )
                except StopIteration:
                    # we are done
                    mon_icinga_log_raw_host_data.objects.bulk_create(host_states)
                    mon_icinga_log_raw_service_data.objects.bulk_create(service_states)
                    self.log("created {} host state entries, {} service state entries from icinga log file {}".format(
                             len(host_states), len(service_states), logfilepath))

                    if cur_line:
                        last_read_timestamp = cur_line.timestamp
        return last_read_timestamp

    def create_host_entry(self, cur_line, full_system_state_entry, logfilepath, logfile_db=None):
        retval = None
        try:
            host, state, state_type, msg = self._parse_host_alert(cur_line)
        except self.unknown_host_error as e:
            self.log("In file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_host_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                state_type=state_type,
                state=state,
                full_system_state_entry=full_system_state_entry,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_service_entry(self, cur_line, full_system_state_entry, logfilepath, logfile_db=None):
        retval = None
        try:
            host, service, state, state_type, msg = self._parse_service_alert(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self.log("In file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_service_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                service_id=service,
                state_type=state_type,
                state=state,
                full_system_state_entry=full_system_state_entry,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

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

    def _parse_host_alert(self, cur_line):
        '''
        :return (int, str, str, str)
        '''
        # format is:
        # host;(DOWN|UP);(SOFT|HARD);???;msg
        info = cur_line.info

        data = info.split(";", 4)
        if len(data) != 5:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #1)".format(info))

        host = self._resolve_host(data[0], cur_line.timestamp)
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

    def _parse_service_alert(self, cur_line):
        '''
        :return (int, int, str, str, str)
        '''
        # format is:
        # host;service;(OK|WARNING|UNKNOWN|CRITICAL);(SOFT|HARD);???;msg
        info = cur_line.info
        data = info.split(";", 5)
        if len(data) != 6:
            raise self.malformed_icinga_log_entry("Malformed service entry: {} (error #1)".format(info))

        host = self._resolve_host(data[0], cur_line.timestamp)
        if not host:
            # can't use data without host
            raise self.unknown_host_error("Failed to resolve host: {} (error #2)".format(data[0]))

        service = self._resolve_service(data[1], cur_line.timestamp)
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

    def _resolve_host(self, host_spec, timestamp):
        '''
        @return int: pk of host or None
        '''
        if self._current_host_service_data and timestamp >= self._current_host_service_data.timestamp:
            # use map for data created with this map, guess for earlier ones (see below)
            retval = self._current_host_service_data.hosts.get(host_spec, None)
            if not retval:
                self.log("Service lookup for current service {} failed, this should not happen".format(host_spec), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = self._resolve_host_historic(host_spec)
        return retval

    def _resolve_host_historic(self, host_spec):
        '''
        @return int: pk of host or None
        '''
        retval = self._historic_host_map.get(host_spec, None)
        if not retval and self._current_host_service_data:
            # try also last map
            retval = self._current_host_service_data.hosts.get(host_spec, None)
        return retval

    def _resolve_service(self, service_spec, timestamp):
        # TODO: special services?
        if self._current_host_service_data and timestamp >= self._current_host_service_data.timestamp:
            # use map for data created with this map, guess for earlier ones (see below)
            retval = self._current_host_service_data.services.get(service_spec, None)
            if not retval:
                self.log("Service lookup for current service {} failed, this should not happen".format(service_spec), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = self._resolve_service_historic(service_spec)
        return retval

    def _resolve_service_historic(self, service_spec):
        '''
        @return int: pk of mon_check_command or None
        '''
        # we can't really know which services have been defined in the past, so we just check
        # the check command description. This works only for check commands with 1 service, so
        # excludes all special commands and cluster commands.
        retval = self._historic_service_map.get(service_spec.replace(" ", "_").lower(), None)
        # try also last map if available
        if not retval and self._current_host_service_data:
            retval = self._current_host_service_data.services.get(service_spec, None)
        return retval
