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
import calendar
import glob
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
        icinga_current_host_state = 'CURRENT HOST STATE'

    def __init__(self, log):
        self.log = log
        self._historic_service_map = {description.replace(" ", "_").lower(): pk
                                      for (pk, description) in mon_check_command.objects.all().values_list('pk', 'description')}
        self._historic_host_map = {entry.full_name: entry.pk for entry in device.objects.all()}
        # pprint.pprint(self._historic_service_map)

    def update(self):
        '''Called periodically'''
        connection.close()

        self.log("checking icinga log")
        self._current_host_service_data = host_service_map.get_mapping(self.log)
        if self._current_host_service_data:
            self.log("using host service map from {}".format(datetime.datetime.fromtimestamp(self._current_host_service_data.timestamp)))

        # check for log rotation
        if mon_icinga_log_last_read.objects.all():
            last_read = mon_icinga_log_last_read.objects.all()[0]
            self.log("last icinga read until: {}".format(datetime.datetime.fromtimestamp(last_read.timestamp)))
        else:
            self.log("no earlier icinga log read, reading archive")
            files = os.listdir(icinga_log_reader.get_icinga_log_archive_dir())
            last_read_timestamp = self.parse_archive_files(files)
            if last_read_timestamp:
                last_read = self._update_last_read(0, last_read_timestamp)  # this is a duplicate update, but ensures that we have a valid value here
            else:
                self.log("no earlier icinga log read and no archive data")
                # there was no earlier read and we weren't able to read anything from the archive, so assume there is none
                last_read = mon_icinga_log_last_read()
                last_read.timestamp = calendar.timegm(datetime.datetime.now() - datetime.timedelta(days=1))  # safe time in past, but not too far cause we check logs of each day
                last_read.position = 0

        try:
            logfile = open(self.get_icinga_log_file(), "r")
        except OSError as e:
            self.log(u"Failed to open log file {} : {}".format(self.get_icinga_log_file(), e))
        else:
            logfile.seek(last_read.position)

            last_read_line = logfile.readline().rstrip("\n")
            self.log("last read line: {}".format(last_read_line))

            same_logfile_as_last_read = False
            if last_read_line:  # empty string (=False) means end, else we at least have '\n'
                cur_line = self._parse_line((None, last_read_line))
                same_logfile_as_last_read = cur_line.timestamp == last_read.timestamp
                self.log("cur line timestamp {}, last read timestamp {}".format(cur_line.timestamp, last_read.timestamp))
                self.log("cur line timestamp {}, last read timestamp {}".format(datetime.datetime.fromtimestamp(cur_line.timestamp),
                                                                                datetime.datetime.fromtimestamp(last_read.timestamp)))

            if same_logfile_as_last_read:
                self.log("continuing to read in current icinga log file")
                # no log rotation, continue reading current file
                self.parse_log_file(logfile)
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
                self.parse_archive_files(files_to_check, last_read.timestamp)

                self.log("finished catching up with archive, continuing with current icinga log file")
                # start reading new file
                logfile.seek(0)
                self.parse_log_file(logfile)

    def parse_log_file(self, logfile, logfilepath=None, start_at=None):
        '''
        :param file logfile: Parsing starts at position of logfile. Must be the main icinga log file.
        :param logfilepath: Path to logfile if it is an archive logfile, not the current one
        :param int start_at: only consider entries older than start_at
        :return int: last read timestamp or None
        '''
        is_archive_logfile = logfilepath is not None
        logfile_db = None
        if is_archive_logfile:
            try:
                logfile_db = mon_icinga_log_file.objects.get(filepath=logfilepath)
            except mon_icinga_log_file.DoesNotExist:
                logfile_db = mon_icinga_log_file(filepath=logfilepath)
                logfile_db.save()

        line_num = 0
        old_ignored = 0
        host_states = []
        service_states = []
        cur_line = None
        for line_raw in logfile:
            line_num += 1
            cur_line = self._parse_line((None, line_raw.rstrip("\n")))
            if start_at is None or cur_line.timestamp > start_at:
                if cur_line.kind in (self.constants.icinga_service_alert, self.constants.icinga_current_service_state):
                    entry = self.create_service_entry(cur_line, cur_line.kind == self.constants.icinga_current_service_state, logfilepath, logfile_db)
                    if entry:
                        service_states.append(entry)
                elif cur_line.kind in (self.constants.icinga_host_alert, self.constants.icinga_current_host_state):
                    entry = self.create_host_entry(cur_line, cur_line.kind == self.constants.icinga_current_host_state, logfilepath, logfile_db)
                    if entry:
                        host_states.append(entry)
                else:
                    pass  # line_raw is not of interest to us
            else:
                old_ignored += 1

            # TODO: make malformed and unresolvable errors non-critical
            #except self.malformed_icinga_log_entry as e:
            #    # TODO: this shouldn't be critical in the final version
            #    raise self.malformed_icinga_log_entry(
            #        "In {} line_raw {}: {}".format(logfilepath, cur_line.line_no if cur_line else None, e.message)
            #        )

        mon_icinga_log_raw_host_data.objects.bulk_create(host_states)
        mon_icinga_log_raw_service_data.objects.bulk_create(service_states)
        self.log("read {} lines, ignored {} old ones".format(line_num, old_ignored))
        self.log("created {} host state entries, {} service state entries from {}".format(len(host_states), len(service_states),
                                                                                          logfilepath if logfilepath else "cur icinga log file"))

        if cur_line:  # if at least something has been read
            position = 0 if is_archive_logfile else logfile.tell() - len(line_raw)
            self._update_last_read(position, cur_line.timestamp)
            return cur_line.timestamp
        return None

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

    def parse_archive_files(self, files, start_at=None):
        '''
        :param list files: list of files to consider (will be sorted here)
        :param int start_at: only consider entries older than start_at
        :return int: last read timestamp or None
        '''
        # sort
        logfiles_date_data = []
        for logfilepath in files:
            unused, month, day, year, hour = logfilepath.split("-")
            logfilepath = os.path.join(icinga_log_reader.get_icinga_log_archive_dir(), logfilepath)
            logfiles_date_data.append((year, month, day, hour, logfilepath))

        retval = None
        for unused1, unused2, unused3, unused4, logfilepath in sorted(logfiles_date_data):
            with open(logfilepath, 'r') as logfile:
                last_read_timestamp = self.parse_log_file(logfile, logfilepath, start_at)
                if retval is None:
                    retval = last_read_timestamp
                else:
                    retval = max(retval, last_read_timestamp)
        return retval

    def create_host_entry(self, cur_line, full_system_state_entry, logfilepath, logfile_db=None):
        retval = None
        try:
            host, state, state_type, msg = self._parse_host_alert(cur_line)
        except self.unknown_host_error as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
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
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
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
                self.log("host lookup for current host {} failed, this should not happen".format(host_spec), logging_tools.LOG_LEVEL_WARN)
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
                self.log("service lookup for current service {} failed, this should not happen".format(service_spec), logging_tools.LOG_LEVEL_WARN)
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
