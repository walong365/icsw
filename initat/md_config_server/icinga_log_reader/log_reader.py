# Copyright (C) 2014-2015,2017 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
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

import bz2
import codecs
import collections
import datetime
import glob
import os
import tempfile
import time
from collections import namedtuple, defaultdict

import psutil
import pytz

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, mon_check_command, \
    mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data, mon_icinga_log_file, \
    mon_icinga_log_last_read, mon_icinga_log_raw_service_flapping_data, \
    mon_icinga_log_raw_service_notification_data, cluster_timezone, \
    mon_icinga_log_raw_host_notification_data, mon_icinga_log_raw_host_flapping_data, \
    mon_icinga_log_raw_base, mon_icinga_log_full_system_dump, \
    mon_icinga_log_raw_host_downtime_data, mon_icinga_log_raw_service_downtime_data
from initat.md_config_server.config import global_config
from initat.md_config_server.icinga_log_reader.log_aggregation import icinga_log_aggregator
from initat.tools import threading_tools, logging_tools
# separated to enable flawless import from webfrontend

from initat.md_config_server.icinga_log_reader.log_reader_utils import host_service_id_util

__all__ = [
    "IcingaLogReader",
    "host_service_id_util",
]


class IcingaLogReader(threading_tools.process_obj):
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
        icinga_service_downtime_alert = 'SERVICE DOWNTIME ALERT'

        icinga_host_alert = 'HOST ALERT'
        icinga_current_host_state = 'CURRENT HOST STATE'
        icinga_initial_host_state = 'INITIAL HOST STATE'
        icinga_host_notification = 'HOST NOTIFICATION'
        icinga_host_flapping_alert = 'HOST FLAPPING ALERT'
        icinga_host_downtime_alert = 'HOST DOWNTIME ALERT'

        always_collect_warnings = True

    #
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

        self.register_timer(self.update, 30 if global_config["DEBUG"] else 300, instant=False)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def update(self):
        """ Called periodically. Only method to be called from outside of this class """
        if global_config["ENABLE_ICINGA_LOG_PARSING"]:
            self._historic_service_map = {
                description.replace(" ", "_").lower(): pk for (pk, description) in mon_check_command.objects.all().values_list('pk', 'description')
            }
            self._historic_host_map = {
                entry.full_name: entry.pk for entry in device.objects.all().prefetch_related('domain_tree_node')
            }

            # logs might contain ids which are not present any more.
            # we discard such data (i.e. ids not present in these sets:)
            self._valid_service_ids = frozenset(mon_check_command.objects.all().values_list('pk', flat=True))
            self._valid_host_ids = frozenset(device.objects.all().values_list('pk', flat=True))

            parse_start_time = time.time()
            self._update_raw_data()
            self.log("parsing took {}".format(logging_tools.get_diff_time_str(time.time() - parse_start_time)))

            aggr_start_time = time.time()
            # prof_file_name = "/tmp/prof.out.{}".format(time.time())
            # self.log("profiling to {}".format(prof_file_name))
            # import cProfile
            # cProfile.runctx("self._icinga_log_aggregator.update()", globals(), locals(), prof_file_name)
            icinga_log_aggregator(self).update()
            self.log("aggregation took {}".format(logging_tools.get_diff_time_str(time.time() - aggr_start_time)))

    def _update_raw_data(self):
        self.log("checking icinga log")

        # collect warnings for not spamming in release mode
        self._warnings = defaultdict(lambda: 0)

        # check where we last have read for log rotation
        last_read = mon_icinga_log_last_read.objects.get_last_read()
        if last_read:
            self.log("last icinga read until: {}".format(self._parse_timestamp(last_read.timestamp)))
        else:
            self.log("no earlier icinga log read, reading archive")
            files = glob.glob(
                os.path.join(
                    IcingaLogReader.get_icinga_log_archive_dir(),
                    "{}*".format(global_config['MD_TYPE'])
                )
            )
            last_read_timestamp = self.parse_archive_files(files)
            if last_read_timestamp:
                last_read = self._update_last_read(0, last_read_timestamp)
                # this is a duplicate update, but ensures that we have a valid value here
            else:
                self.log("no earlier icinga log read and no archive data")
                # there was no earlier read and we weren't able to read anything from the archive,
                # so assume there is none
                last_read = mon_icinga_log_last_read()
                # safe time in past, but not too far cause we check logs of each day
                last_read.timestamp = int(
                    ((datetime.datetime.now() - datetime.timedelta(days=1)) - datetime.datetime(1970, 1, 1)).total_seconds()
                )
                last_read.position = 0

        try:
            logfile = codecs.open(self.get_icinga_log_file(), "r", "utf-8", errors='replace')
        except IOError as e:
            self.log("Failed to open log file {} : {}".format(self.get_icinga_log_file(), e),
                     logging_tools.LOG_LEVEL_ERROR)
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
                    # self.log("cur line timestamp {}, last read timestamp {}".format(
                    # cur_line.timestamp, last_read.timestamp))
                    # self.log("cur line timestamp {}, last read timestamp {}".format(
                    # self._parse_timestamp(cur_line.timestamp), self._parse_timestamp(last_read.timestamp)))

            if same_logfile_as_last_read:
                self.log("continuing to read in current icinga log file")
                # no log rotation, continue reading current file
                # the current position of the file must be the next byte to read!
                self.parse_log_file(logfile)
            else:
                self.log("detected icinga log rotation")
                # cur log file does not correspond to where we last read.
                # we have to check the archive for whatever we have missed.
                last_read_date = datetime.datetime.utcfromtimestamp(last_read.timestamp)
                today_datetime = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
                missed_timedelta = today_datetime - last_read_date

                files_to_check = []

                # get days by filename
                for day_missed in range(missed_timedelta.days + 1):  # include last
                    missed_log_day = last_read_date + datetime.timedelta(days=day_missed)

                    format_num = lambda num: "{:02d}".format(num)

                    day_files = glob.glob(
                        os.path.join(
                            IcingaLogReader.get_icinga_log_archive_dir(),
                            "{}-{}-{}-{}-*".format(
                                global_config['MD_TYPE'],
                                format_num(missed_log_day.month),
                                format_num(missed_log_day.day),
                                format_num(missed_log_day.year)
                            )
                        )
                    )
                    files_to_check.extend(day_files)

                # read archive
                self.parse_archive_files(files_to_check, start_at=last_read.timestamp)
                if not self["exit_requested"]:
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
                self._create_icinga_down_entry(cluster_timezone.localize(datetime.datetime.now()), msg, None, save=True)

        if self.constants.always_collect_warnings or not global_config["DEBUG"]:
            if self._warnings:
                self.log("warnings while parsing:")
                for warning, multiplicity in self._warnings.items():
                    self.log("{} ({})".format(warning, multiplicity), logging_tools.LOG_LEVEL_WARN)
                self.log("end of warnings while parsing:")

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
        host_downtimes = []
        service_states = []
        service_flapping_states = []
        service_notifications = []
        service_downtimes = []
        full_system_dump_times = set()

        cur_line = None
        for line_raw in logfile:
            line_num += 1
            # check for special entry
            try:
                timestamp, msg = self._parse_line(line_raw.rstrip("\n"), only_parse_timestamp=True)
                if msg.startswith("Successfully shutdown"):
                    # self.log("detected icinga shutdown by log")
                    # create alerts for all devices: indeterminate (icinga not running)
                    # note: this relies on the fact that on startup, icinga writes a status update on start
                    host_entry, service_entry, host_flapping_entry, service_flapping_entry = \
                        self._create_icinga_down_entry(self._parse_timestamp(timestamp), msg, logfile_db, save=False)
                    host_states.append(host_entry)
                    service_states.append(service_entry)
                    host_flapping_states.append(host_flapping_entry)
                    service_flapping_states.append(service_flapping_entry)

            except self.malformed_icinga_log_entry as e:
                self._handle_warning(e, logfilepath, cur_line.line_no if cur_line else None)

            # check for regular log entry
            try:
                cur_line = self._parse_line(line_raw.rstrip("\n"), line_num if is_archive_logfile else None)
                # only know line no for archive files
                # we want to discard older (reread) entries if start_at is given,
                # except for current states (these are at the beginning of each log file)
                # (we don't need the initial states here because they don't occur at turnovers)
                if start_at is None or (cur_line.timestamp > start_at or
                                        cur_line.kind in (self.constants.icinga_current_host_state,
                                                          self.constants.icinga_current_service_state)):

                    if cur_line.kind in\
                            (self.constants.icinga_current_host_state, self.constants.icinga_current_service_state,
                             self.constants.icinga_initial_host_state, self.constants.icinga_initial_service_state):
                        full_system_dump_times.add(cur_line.timestamp)
                    if cur_line.kind in\
                            (self.constants.icinga_service_alert, self.constants.icinga_current_service_state,
                             self.constants.icinga_initial_service_state):
                        entry = self.create_service_alert_entry(
                            cur_line,
                            cur_line.kind == self.constants.icinga_current_service_state,
                            cur_line.kind == self.constants.icinga_initial_service_state,
                            logfilepath,
                            logfile_db
                        )
                        if entry:
                            stats['service alerts'] += 1
                            service_states.append(entry)
                    elif cur_line.kind in (self.constants.icinga_host_alert, self.constants.icinga_current_host_state,
                                           self.constants.icinga_initial_host_state):
                        entry = self.create_host_alert_entry(
                            cur_line,
                            cur_line.kind == self.constants.icinga_current_host_state,
                            cur_line.kind == self.constants.icinga_initial_host_state,
                            logfilepath,
                            logfile_db
                        )
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
                    elif cur_line.kind == self.constants.icinga_host_downtime_alert:
                        entry = self.create_host_downtime_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['host downtime alert'] += 1
                            host_downtimes.append(entry)
                    elif cur_line.kind == self.constants.icinga_service_downtime_alert:
                        entry = self.create_service_downtime_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['service downtime alert'] += 1
                            service_downtimes.append(entry)
                    else:
                        pass  # line_raw is not of interest to us
                else:
                    old_ignored += 1

            except self.malformed_icinga_log_entry as e:
                self._handle_warning(e, logfilepath, cur_line.line_no if cur_line else None)

        self.log(
            "created from {}: {} ".format(
                logfilepath if logfilepath else "cur icinga log file",
                ", ".join(
                    [
                        "{} ({:d})".format(key, value) for key, value in stats.items()
                    ]
                ) or "nothing",
            )
        )

        # there can be really many host and service entries (up to 1000000),
        # so we save them in several stages
        def save_in_small_batches(model, entries, limit=1000):
            for i in range(0, len(entries), limit):
                model.objects.bulk_create(entries[i:i + limit])

        save_in_small_batches(mon_icinga_log_raw_host_alert_data, host_states)
        save_in_small_batches(mon_icinga_log_raw_service_alert_data, service_states)

        mon_icinga_log_raw_service_flapping_data.objects.bulk_create(service_flapping_states)
        mon_icinga_log_raw_host_flapping_data.objects.bulk_create(host_flapping_states)

        save_in_small_batches(mon_icinga_log_raw_service_notification_data, service_notifications)
        save_in_small_batches(mon_icinga_log_raw_host_notification_data, host_notifications)

        mon_icinga_log_raw_host_downtime_data.objects.bulk_create(host_downtimes)
        mon_icinga_log_raw_service_downtime_data.objects.bulk_create(service_downtimes)

        for timestamp in full_system_dump_times:
            try:
                mon_icinga_log_full_system_dump.objects.get_or_create(date=self._parse_timestamp(timestamp))
            except mon_icinga_log_full_system_dump.MultipleObjectsReturned:
                # There really is no way how this can happen. However, it now has been
                # observed twice. Ignore it since this isn't actually a problem
                self.log("Detected multiple objects for time {}, ignoring".format(
                    self._parse_timestamp(timestamp)
                ))
        self.log("read {} lines, ignored {} old ones".format(line_num, old_ignored))

        if cur_line:  # if at least something has been read
            position = 0 if is_archive_logfile else logfile.tell() - len(line_raw)  # start of last line read
            self._update_last_read(position, cur_line.timestamp)
            return cur_line.timestamp
        return None

    def _update_last_read(self, position, timestamp):
        """Keep track of which data was read. May be called with older timestamp (will be discarded)."""
        last_read = mon_icinga_log_last_read.objects.get_last_read()
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
                logfilepath = os.path.join(IcingaLogReader.get_icinga_log_archive_dir(), logfilepath)
                logfiles_date_data.append((year, month, day, hour, logfilepath))

        retval = None

        (unused, tempfilepath) = tempfile.mkstemp("icinga_log_decompress")
        for unused1, unused2, unused3, unused4, logfilepath in sorted(logfiles_date_data):

            if logfilepath.lower().endswith('bz2'):
                # it seems to be hard to get bz2 to return unicode
                # hence we decompress to a temporary file which then should be
                # binary-equivalent to original file and then open it in a
                # unicode-aware manner

                f = open(tempfilepath, "w")
                f.write(bz2.BZ2File(logfilepath).read())
                f.close()
                actual_logfilepath = tempfilepath

            else:
                actual_logfilepath = logfilepath

            try:
                logfile = codecs.open(actual_logfilepath, "r", "utf-8", errors='replace')
            except IOError as e:
                self.log(
                    "failed to open archive log file {} : {}".format(logfilepath, e),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                last_read_timestamp = self.parse_log_file(logfile, logfilepath, start_at)
                if retval is None:
                    retval = last_read_timestamp
                else:
                    retval = max(retval, last_read_timestamp)
                # check if we are supposed to die
                self.step()
                if self["exit_requested"]:
                    self.log("exit requested")
                    break
        os.remove(tempfilepath)

        return retval

    def _handle_warning(self, exception, logfilepath, cur_line_no):
        if self.constants.always_collect_warnings or not global_config["DEBUG"]:
            # in release mode, we don't want spam so we collect the errors and log each according to the multiplicity
            self._warnings[str(exception)] += 1
        else:
            # log right away
            self.log(
                "in file {} line {}: {}".format(logfilepath, cur_line_no, exception),
                logging_tools.LOG_LEVEL_WARN
            )

    def create_host_alert_entry(self, cur_line, log_rotation_state, initial_state, logfilepath, logfile_db=None):
        retval = None
        try:
            host, state, state_type, msg = self._parse_host_alert(cur_line)
        except self.unknown_host_error as e:
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_host_alert_data(
                date=self._parse_timestamp(cur_line.timestamp),
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
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_service_alert_data(
                date=self._parse_timestamp(cur_line.timestamp),
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
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_service_flapping_data(
                date=self._parse_timestamp(cur_line.timestamp),
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
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_host_flapping_data(
                date=self._parse_timestamp(cur_line.timestamp),
                device_id=host,
                flapping_state=flapping_state,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_service_notification_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            user, host, (service, service_info), state, notification_type, msg =\
                self._parse_service_notification(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_service_notification_data(
                date=self._parse_timestamp(cur_line.timestamp),
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
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_host_notification_data(
                date=self._parse_timestamp(cur_line.timestamp),
                device_id=host,
                state=state,
                user=user,
                notification_type=notification_type,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_host_downtime_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            host, state, msg = self._parse_host_downtime_alert(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_host_downtime_data(
                date=self._parse_timestamp(cur_line.timestamp),
                device_id=host,
                downtime_state=state,
                msg=msg,
                logfile=logfile_db,
            )
        return retval

    def create_service_downtime_entry(self, cur_line, logfilepath, logfile_db):
        retval = None
        try:
            host, (service, service_info), state, msg = self._parse_service_downtime_alert(cur_line)
        except (self.unknown_host_error, self.unknown_service_error) as e:
            self._handle_warning(e, logfilepath, cur_line.line_no)
        else:
            retval = mon_icinga_log_raw_service_downtime_data(
                date=self._parse_timestamp(cur_line.timestamp),
                device_id=host,
                service_id=service,
                service_info=service_info,
                downtime_state=state,
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

        state = mon_icinga_log_raw_host_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[1], None)  # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed state entry: {} (error #3) {} {} ".format(info))

        state_type = {"SOFT": "S", "HARD": "H"}.get(data[2], None)  # format as in db table
        if not state_type:
            raise self.malformed_icinga_log_entry("Malformed host entry: {} (error #4)".format(info))

        msg = data[4]

        return host, state, state_type, msg

    def _parse_host_service(self, host_spec, service_spec):
        # used for service and service flapping alerts as well as service notifications

        # primary method: check special service description
        host, service, service_info = host_service_id_util.parse_host_service_description(service_spec, self.log)

        if host not in self._valid_host_ids:
            host = None  # host has been properly logged, but doesn't exist any more
        if service not in self._valid_service_ids:
            service = None  # service has been properly logged, but doesn't exist any more

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

        flapping_state = {"STARTED": mon_icinga_log_raw_base.START,
                          "STOPPED": mon_icinga_log_raw_base.STOP}.get(data[2], None)  # format as in db table
        if not flapping_state:
            raise self.malformed_icinga_log_entry("Malformed flapping state entry: {} (error #7)".format(info))

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
        flapping_state = {"STARTED": mon_icinga_log_raw_base.START,
                          "STOPPED": mon_icinga_log_raw_base.STOP}.get(data[1], None)  # format as in db table
        if not flapping_state:
            raise self.malformed_icinga_log_entry("Malformed flapping state entry: {} (error #7)".format(info))
        msg = data[2]
        return host, flapping_state, msg

    def _parse_service_downtime_alert(self, cur_line):
        # format is:
        # host;service;(STARTED|STOPPED);msg
        info = cur_line.info
        data = info.split(";", 3)
        if len(data) != 4:
            raise self.malformed_icinga_log_entry("Malformed service downtime entry: {} (error #1)".format(info))

        host, service, service_info = self._parse_host_service(data[0], data[1])

        state = {
            "STARTED": mon_icinga_log_raw_base.START,
            "STOPPED": mon_icinga_log_raw_base.STOP
        }.get(data[2], None)  # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed service downtime state entry: {} (error #2)".format(info))

        msg = data[3]

        return host, (service, service_info), state, msg

    def _parse_host_downtime_alert(self, cur_line):
        # format is:
        # host;(STARTED|STOPPED);msg
        # msg is autogenerated (something like 'host has exited from downtime'), collect it anyway
        info = cur_line.info
        data = info.split(";", 2)
        if len(data) != 3:
            raise self.malformed_icinga_log_entry("Malformed host downtime entry: {} (error #1)".format(info))
        host = self._resolve_host(data[0])
        state = {
            "STARTED": mon_icinga_log_raw_base.START,
            "STOPPED": mon_icinga_log_raw_base.STOP
        }.get(data[1], None)  # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed host downtime state entry: {} (error #2)".format(info))
        msg = data[2]

        return host, state, msg

    def _parse_service_notification(self, cur_line):
        # format is:
        # user;host;service;($service_state);notification_type,msg
        info = cur_line.info
        data = info.split(";", 5)
        if len(data) != 6:
            raise self.malformed_icinga_log_entry("Malformed service notification entry: {} (error #1)".format(info))

        user = data[0]
        host, service, service_info = self._parse_host_service(data[1], data[2])
        state = mon_icinga_log_raw_service_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[3], None)
        # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed state in entry: {} (error #6)".format(info))
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
        state = mon_icinga_log_raw_host_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[2], None)
        # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed state in entry: {} (error #6)".format(info))
        notification_type = data[3]
        msg = data[4]
        return user, host, state, notification_type, msg

    def _parse_service_alert(self, cur_line):
        '''
        :return (int, str, str, str)
        '''
        # format is:
        # host;service;(OK|WARNING|UNKNOWN|CRITICAL);(SOFT|HARD);???;msg
        info = cur_line.info
        data = info.split(";", 5)
        if len(data) != 6:
            raise self.malformed_icinga_log_entry("Malformed service entry: {} (error #1)".format(info))

        host, service, service_info = self._parse_host_service(data[0], data[1])

        state = mon_icinga_log_raw_service_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[2], None)
        # format as in db table
        if not state:
            raise self.malformed_icinga_log_entry("Malformed state entry: {} (error #6)".format(info))

        state_type = {
            "SOFT": "S",
            "HARD": "H"
        }.get(data[3], None)  # format as in db table
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
        #         self.log("host lookup for current host {} failed," +
        #                  "this should not happen".format(host_spec), logging_tools.LOG_LEVEL_WARN)
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
        #         self.log("service lookup for current service {} failed," +
        #                  "this should not happen".format(service_spec), logging_tools.LOG_LEVEL_WARN)
        # else:
        retval = (self._resolve_service_historic(service_spec), service_spec)
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
            flapping_state=mon_icinga_log_raw_base.STOP,
            device_independent=True,
            msg=msg,
            logfile=logfile_db,
        )
        service_flapping_entry = mon_icinga_log_raw_service_flapping_data(
            date=when,
            device_id=None,
            service_id=None,
            service_info=None,
            flapping_state=mon_icinga_log_raw_base.STOP,
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

    def _parse_timestamp(self, timestamp):
        return datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
