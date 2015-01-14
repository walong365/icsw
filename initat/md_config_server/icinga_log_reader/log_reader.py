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

import calendar
from collections import namedtuple
import collections
import datetime
import glob
import os
import pprint  # @UnusedImport

from django.db import connection
from initat.cluster.backbone.models import device
from initat.cluster.backbone.models.monitoring import mon_check_command, \
    mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data, mon_icinga_log_file, \
    mon_icinga_log_last_read, mon_icinga_log_raw_service_flapping_data, \
    mon_icinga_log_raw_service_notification_data, \
    mon_icinga_log_raw_host_notification_data, mon_icinga_log_raw_host_flapping_data, \
    mon_icinga_log_raw_base
from initat.md_config_server.config import global_config
import logging_tools
import psutil
import threading_tools

from initat.md_config_server.icinga_log_reader.aggregation import icinga_log_aggregator


__all__ = [
    "icinga_log_reader",
    "host_service_id_util",
]


class icinga_log_reader_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()

        self.icinga_log_reader = icinga_log_reader(self.log)

        self.register_timer(self._update, 30 if global_config["DEBUG"] else 300, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _update(self):
        self.icinga_log_reader.update()


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
        icinga_initial_service_state = 'INITIAL SERVICE STATE'
        icinga_service_flapping_alert = 'SERVICE FLAPPING ALERT'
        icinga_service_notification = 'SERVICE NOTIFICATION'

        icinga_host_alert = 'HOST ALERT'
        icinga_current_host_state = 'CURRENT HOST STATE'
        icinga_initial_host_state = 'INITIAL HOST STATE'
        icinga_host_notification = 'HOST NOTIFICATION'
        icinga_host_flapping_alert = 'HOST FLAPPING ALERT'

    def __init__(self, log):

        if False:
            log_orig = log

            def my_log(msg, level='debug'):
                log_orig(msg)

                with open("/tmp/myicingalog", "a") as f:
                    f.write("{}: {}\n".format(level, msg))

            log = my_log

        self.log = log
        self._historic_service_map = {description.replace(" ", "_").lower(): pk
                                      for (pk, description) in mon_check_command.objects.all().values_list('pk', 'description')}
        self._historic_host_map = {entry.full_name: entry.pk for entry in device.objects.all()}

        self._icinga_log_aggregator = icinga_log_aggregator(log)

    def update(self):
        '''Called periodically'''
        self._update_raw_data()

        # import cProfile; cProfile.runctx("self._icinga_log_aggregator.update()", globals(), locals(), "/tmp/prof.out")
        self._icinga_log_aggregator.update()

    def _update_raw_data(self):
        self.log("checking icinga log")

        # check where we last have read for log rotation
        last_read = mon_icinga_log_last_read.objects.get_last_read()  # @UndefinedVariable
        if last_read:
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
                # safe time in past, but not too far cause we check logs of each day
                last_read.timestamp = calendar.timegm(datetime.datetime.now() - datetime.timedelta(days=1))
                last_read.position = 0

        try:
            logfile = open(self.get_icinga_log_file(), "r")
        except OSError as e:
            self.log(u"Failed to open log file {} : {}".format(self.get_icinga_log_file(), e), logging_tools.LOG_LEVEL_ERROR)
        else:
            # check for log rotation
            logfile.seek(last_read.position)

            last_read_line = logfile.readline().rstrip("\n")
            self.log("last read line: {}".format(last_read_line))

            same_logfile_as_last_read = False
            if last_read_line:  # empty string (=False) means end, else we at least have '\n'
                try:
                    cur_line = self._parse_line(last_read_line)
                except self.malformed_icinga_log_entry:
                    pass
                else:
                    same_logfile_as_last_read = cur_line.timestamp == last_read.timestamp
                    self.log("cur line timestamp {}, last read timestamp {}".format(cur_line.timestamp, last_read.timestamp))
                    self.log("cur line timestamp {}, last read timestamp {}".format(datetime.datetime.fromtimestamp(cur_line.timestamp),
                                                                                    datetime.datetime.fromtimestamp(last_read.timestamp)))

            if same_logfile_as_last_read:
                self.log("continuing to read in current icinga log file")
                # no log rotation, continue reading current file
                # the current position of the file must be the next byte to read!
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
                self.parse_archive_files(files_to_check, start_at=last_read.timestamp)

                self.log("finished catching up with archive, continuing with current icinga log file")
                # start reading cur file
                logfile.seek(0)
                self.parse_log_file(logfile)

        # check if icinga is even running
        # (we do this after parsing to have events in proper order in db, which is nice)
        icinga_lock_file_name = os.path.join(global_config["MD_BASEDIR"], "var", global_config["MD_LOCK_FILE"])
        try:
            pid = int(open(icinga_lock_file_name, "r").read().strip())
        except:
            pass  # can't really tell if icinga is running this way
        else:
            try:
                psutil.Process(pid=pid)
            except psutil.NoSuchProcess:
                # assume not running
                msg = "icinga process (pid: {}) is not running".format(pid)
                self.log(msg)
                self._create_icinga_down_entry(datetime.datetime.now(), msg, None, save=True)

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
        stats = collections.defaultdict(lambda: 0)

        host_states = []
        host_flapping_states = []
        host_notifications = []
        service_states = []
        service_flapping_states = []
        service_notifications = []

        cur_line = None
        for line_raw in logfile:
            line_num += 1
            # check for special entry
            try:
                timestamp, msg = self._parse_line(line_raw.rstrip("\n"), only_parse_timestamp=True)
                if msg.startswith("Successfully shutdown"):
                    self.log("detected icinga shutdown by log")
                    # create alerts for all devices: indeterminate (icinga not running)
                    # note: this relies on the fact that on startup, icinga writes a status update on start
                    host_entry, service_entry, host_flapping_entry, service_flapping_entry = \
                        self._create_icinga_down_entry(datetime.datetime.fromtimestamp(timestamp), msg, logfile_db, save=False)
                    host_states.append(host_entry)
                    service_states.append(service_entry)
                    host_flapping_states.append(host_flapping_entry)
                    service_flapping_states.append(service_flapping_entry)

            except self.malformed_icinga_log_entry as e:
                self.log("in {} line {}: {}".format(logfilepath, cur_line.line_no if cur_line else None, e.message), logging_tools.LOG_LEVEL_WARN)

            # check for regular log entry
            try:
                cur_line = self._parse_line(line_raw.rstrip("\n"), line_num if is_archive_logfile else None)  # only know line no for archive files
                if start_at is None or cur_line.timestamp > start_at:
                    if cur_line.kind in (self.constants.icinga_service_alert, self.constants.icinga_current_service_state,
                                         self.constants.icinga_initial_service_state):
                        entry = self.create_service_alert_entry(cur_line, cur_line.kind == self.constants.icinga_current_service_state,
                                                                cur_line.kind == self.constants.icinga_initial_service_state, logfilepath, logfile_db)
                        if entry:
                            stats['service alerts'] += 1
                            service_states.append(entry)
                    elif cur_line.kind in (self.constants.icinga_host_alert, self.constants.icinga_current_host_state,
                                           self.constants.icinga_initial_host_state):
                        entry = self.create_host_alert_entry(cur_line, cur_line.kind == self.constants.icinga_current_host_state,
                                                             cur_line.kind == self.constants.icinga_initial_host_state, logfilepath, logfile_db)
                        if entry:
                            stats['host alerts'] += 1
                            host_states.append(entry)
                    elif cur_line.kind == self.constants.icinga_service_flapping_alert:
                        entry = self.create_service_flapping_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['service flapping alerts'] += 1
                            service_flapping_states.append(entry)
                    elif cur_line.kind == self.constants.icinga_host_flapping_alert:
                        entry = self.create_host_flapping_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['host flapping alerts'] += 1
                            host_flapping_states.append(entry)
                    elif cur_line.kind == self.constants.icinga_service_notification:
                        entry = self.create_service_notification_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['service notification'] += 1
                            service_notifications.append(entry)
                    elif cur_line.kind == self.constants.icinga_host_notification:
                        entry = self.create_host_notification_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['host notification'] += 1
                            host_notifications.append(entry)
                    else:
                        pass  # line_raw is not of interest to us
                else:
                    old_ignored += 1

            except self.malformed_icinga_log_entry as e:
                self.log("in {} line {}: {}".format(logfilepath, cur_line.line_no if cur_line else None, e.message), logging_tools.LOG_LEVEL_WARN)

        self.log("created from {}: {} ".format(logfilepath if logfilepath else "cur icinga log file", stats.items()))
        mon_icinga_log_raw_host_alert_data.objects.bulk_create(host_states)
        mon_icinga_log_raw_service_alert_data.objects.bulk_create(service_states)
        mon_icinga_log_raw_service_flapping_data.objects.bulk_create(service_flapping_states)
        mon_icinga_log_raw_host_flapping_data.objects.bulk_create(host_flapping_states)
        mon_icinga_log_raw_service_notification_data.objects.bulk_create(service_notifications)
        mon_icinga_log_raw_host_notification_data.objects.bulk_create(host_notifications)
        self.log("read {} lines, ignored {} old ones".format(line_num, old_ignored))

        if cur_line:  # if at least something has been read
            position = 0 if is_archive_logfile else logfile.tell() - len(line_raw)  # start of last line read
            self._update_last_read(position, cur_line.timestamp)
            return cur_line.timestamp
        return None

    def _update_last_read(self, position, timestamp):
        """Keep track of which data was read. May be called with older timestamp (will be discarded)."""
        last_read = mon_icinga_log_last_read.objects.get_last_read()  # @UndefinedVariable
        if last_read:
            if last_read.timestamp > timestamp:
                return last_read  # tried to update with older timestamp
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
            try:
                unused, month, day, year, hour = logfilepath.split("-")
            except ValueError:
                pass  # filename not appropriate
            else:
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

    def create_host_alert_entry(self, cur_line, log_rotation_state, initial_state, logfilepath, logfile_db=None):
        retval = None
        try:
            host, state, state_type, msg = self._parse_host_alert(cur_line)
        except self.unknown_host_error as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_host_alert_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                state_type=state_type,
                state=state,
                log_rotation_state=log_rotation_state,
                initial_state=initial_state,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_service_alert_entry(self, cur_line, log_rotation_state, initial_state, logfilepath, logfile_db=None):
        retval = None
        try:
            host, (service, service_info), state, state_type, msg = self._parse_service_alert(cur_line)
            # TODO: need to generalize for other service types
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_service_alert_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                service_id=service,
                service_info=service_info,
                state_type=state_type,
                state=state,
                log_rotation_state=log_rotation_state,
                initial_state=initial_state,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_service_flapping_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            host, (service, service_info), flapping_state, msg = self._parse_service_flapping_alert(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_service_flapping_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                service_id=service,
                service_info=service_info,
                flapping_state=flapping_state,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_host_flapping_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            host, flapping_state, msg = self._parse_host_flapping_alert(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_host_flapping_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                flapping_state=flapping_state,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_service_notification_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            user, host, (service, service_info), state, notification_type, msg = self._parse_service_notification(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_service_notification_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                service_id=service,
                service_info=service_info,
                state=state,
                user=user,
                notification_type=notification_type,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_host_notification_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            user, host, state, notification_type, msg = self._parse_host_notification(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self.log("in file {} line {}: {}".format(logfilepath, cur_line.line_no, e), logging_tools.LOG_LEVEL_WARN)
        else:
            retval = mon_icinga_log_raw_host_notification_data(
                date=datetime.datetime.fromtimestamp(cur_line.timestamp),
                device_id=host,
                state=state,
                user=user,
                notification_type=notification_type,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    icinga_log_line = namedtuple('icinga_log_line', ('timestamp', 'kind', 'info', 'line_no'))

    @classmethod
    def _parse_line(cls, line, line_no=None, only_parse_timestamp=False):
        '''
        :return icinga_log_line
        '''
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

        if only_parse_timestamp:
            return timestamp, info_raw

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
        # host;(DOWN|UP|UNREACHABLE);(SOFT|HARD);???;msg
        info = cur_line.info

        data = info.split(";", 4)
        if len(data) != 5:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #1)".format(info))

        host = self._resolve_host(data[0])
        if not host:
            raise self.unknown_host_error("Failed to resolve host: {} (error #2)".format(data[0]))

        state = mon_icinga_log_raw_host_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[1], None)  # format as in db table @UndefinedVariable
        if not state:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #3) {} {} ".format(info))

        state_type = {"SOFT": "S", "HARD": "H"}.get(data[2], None)  # format as in db table
        if not state_type:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #4)".format(info))

        msg = data[4]

        return host, state, state_type, msg

    def _parse_host_service(self, host_spec, service_spec):
        # used for service and service flapping alerts as well as service notifications

        # primary method: check special service description
        host, service, service_info = host_service_id_util.parse_host_service_description(service_spec, self.log)

        if not host:
            host = self._resolve_host(host_spec)
        if not host:
            # can't use data without host
            raise self.unknown_host_error("Failed to resolve host: {} (error #2)".format(host_spec))

        if not service:
            service, service_info = self._resolve_service(service_spec)
        # TODO: generalise to other services
        if not service:
            # raise self.unknown_service_error("Failed to resolve service : {} (error #3)".format(service_spec))
            # this is not an entry with new format and also not a uniquely identifiable one
            # however we want to keep the data, even if it's not nicely identifiable
            service = None
            service_info = service_spec

        return host, service, service_info

    def _parse_service_flapping_alert(self, cur_line):
        # format is:
        # host;service;(STARTED|STOPPED);msg
        info = cur_line.info
        data = info.split(";", 3)
        if len(data) != 4:
            raise self.malformed_icinga_log_entry("Malformed service flapping entry: {} (error #1)".format(info))

        host, service, service_info = self._parse_host_service(data[0], data[1])

        flapping_state = {"STARTED": mon_icinga_log_raw_base.FLAPPING_START, "STOPPED": mon_icinga_log_raw_base.FLAPPING_STOP}.get(data[2], None)  # format as in db table

        msg = data[3]

        return host, (service, service_info), flapping_state, msg

    def _parse_host_flapping_alert(self, cur_line):
        # format is:
        # host;(STARTED|STOPPED);msg
        info = cur_line.info
        data = info.split(";", 2)
        if len(data) != 3:
            raise self.malformed_icinga_log_entry("Malformed host flapping entry: {} (error #1)".format(info))

        host = self._resolve_host(data[0])
        flapping_state = {"STARTED": mon_icinga_log_raw_base.FLAPPING_START, "STOPPED": mon_icinga_log_raw_base.FLAPPING_STOP}.get(data[1], None)  # format as in db table
        msg = data[2]
        return host, flapping_state, msg

    def _parse_service_notification(self, cur_line):
        # format is:
        # user;host;service;($service_state);notification_type,msg
        info = cur_line.info
        data = info.split(";", 5)
        if len(data) != 6:
            raise self.malformed_icinga_log_entry("Malformed service notification entry: {} (error #1)".format(info))

        user = data[0]
        host, service, service_info = self._parse_host_service(data[1], data[2])
        state = mon_icinga_log_raw_service_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[3], None)  # format as in db table @UndefinedVariable
        notification_type = data[4]
        msg = data[5]
        return user, host, (service, service_info), state, notification_type, msg

    def _parse_host_notification(self, cur_line):
        # format is:
        # user;host;($host_state);notification_type,msg
        info = cur_line.info
        data = info.split(";", 4)
        if len(data) != 5:
            raise self.malformed_icinga_log_entry("Malformed service notification entry: {} (error #1)".format(info))

        user = data[0]
        host = self._resolve_host(data[1])
        state = mon_icinga_log_raw_host_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[2], None)  # format as in db table @UndefinedVariable
        notification_type = data[3]
        msg = data[4]
        return user, host, state, notification_type, msg

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

        host, service, service_info = self._parse_host_service(data[0], data[1])

        state = mon_icinga_log_raw_service_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[2], None)  # format as in db table @UndefinedVariable
        if not state:
            raise self.malformed_icinga_log_entry("Malformed service entry: {} (error #4)".format(info))

        state_type = {"SOFT": "S", "HARD": "H"}.get(data[3], None)  # format as in db table
        if not state_type:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #5)".format(info))

        msg = data[5]

        return host, (service, service_info), state, state_type, msg

    def _resolve_host(self, host_spec):
        '''
        @return int: pk of host or None
        '''
        # if self._current_host_service_data and timestamp >= self._current_host_service_data.timestamp:
        #     # use map for data created with this map, guess for earlier ones (see below)
        #     retval = self._current_host_service_data.hosts.get(host_spec, None)
        #     if not retval:
        #         self.log("host lookup for current host {} failed, this should not happen".format(host_spec), logging_tools.LOG_LEVEL_WARN)
        # else:

        retval = self._resolve_host_historic(host_spec)

        return retval

    def _resolve_host_historic(self, host_spec):
        '''
        @return int: pk of host or None
        '''
        return self._historic_host_map.get(host_spec, None)

    def _resolve_service(self, service_spec):
        # TODO: need to generalize for other service types
        # if self._current_host_service_data and timestamp >= self._current_host_service_data.timestamp:
        #     # use map for data created with this map, guess for earlier ones (see below)
        #     retval = (self._current_host_service_data.services.get(service_spec, None), None)
        #     if not retval[0]:
        #         self.log("service lookup for current service {} failed, this should not happen".format(service_spec), logging_tools.LOG_LEVEL_WARN)
        # else:
        retval = (self._resolve_service_historic(service_spec), None)
        return retval

    def _resolve_service_historic(self, service_spec):
        '''
        @return int: pk of mon_check_command or None
        '''
        # we can't really know which services have been defined in the past, so we just check
        # the check command description. This works only for check commands with 1 service, so
        # excludes all special commands and cluster commands.
        return self._historic_service_map.get(service_spec.replace(" ", "_").lower(), None)

    def _create_icinga_down_entry(self, when, msg, logfile_db, save):
        host_entry = mon_icinga_log_raw_host_alert_data(
            date=when,
            device=None,
            device_independent=True,
            state_type=mon_icinga_log_raw_base.STATE_UNDETERMINED,
            state=mon_icinga_log_raw_base.STATE_UNDETERMINED,
            msg=msg,
            logfile=logfile_db,
        )
        service_entry = mon_icinga_log_raw_service_alert_data(
            date=when,
            device=None,
            service=None,
            service_info=None,
            device_independent=True,
            state_type=mon_icinga_log_raw_base.STATE_UNDETERMINED,
            state=mon_icinga_log_raw_base.STATE_UNDETERMINED,
            msg=msg,
            logfile=logfile_db,
        )
        host_flapping_entry = mon_icinga_log_raw_host_flapping_data(
            date=when,
            device_id=None,
            flapping_state=mon_icinga_log_raw_base.FLAPPING_STOP,
            device_independent=True,
            msg=msg,
            logfile=logfile_db,
        )
        service_flapping_entry = mon_icinga_log_raw_service_flapping_data(
            date=when,
            device_id=None,
            service_id=None,
            service_info=None,
            flapping_state=mon_icinga_log_raw_base.FLAPPING_STOP,
            device_independent=True,
            msg=msg,
            logfile=logfile_db,
        )

        if save:
            host_entry.save()
            service_entry.save()
            host_flapping_entry.save()
            service_flapping_entry.save()

        return host_entry, service_entry, host_flapping_entry, service_flapping_entry


class host_service_id_util(object):

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
        '''
        retval = None
        if s_check.check_command_pk is not None:
            # regular service check
            # format is: service_check:${mon_check_command_pk}:$info
            # since a mon_check_command_pk can have multiple actual service checks, we add the info string to identify it
            # as the services are created dynamically, we don't have a nice db pk
            retval = "host_check:{}:{}:{}".format(host_pk, s_check.check_command_pk, info)
        else:
            retval = "unstructured:" + info
        return retval

    @classmethod
    def parse_host_service_description(cls, service_spec, log=None):
        '''
        "Inverse" of create_host_service_description
        '''
        data = service_spec.split(':', 1)
        retval = (None, None, None)
        if len(data) == 2:
            if data[0] == 'host_check':
                service_data = data[1].split(":")
                if len(service_data) == 3:
                    host_pk, service_pk, info = service_data
                    retval = (int(host_pk), int(service_pk), info)
            elif data[0] == 'unstructured':
                pass
            else:
                if log:
                    log("invalid service description: {}".format(service_spec))
        return retval
