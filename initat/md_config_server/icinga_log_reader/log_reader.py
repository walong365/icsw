# Copyright (C) 2014-2015,2017 Bernhard Mallinger, init.at
#
# this file is part of icsw-server-server
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
import time
from collections import defaultdict

import psutil
import pytz

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, mon_check_command, \
    mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data, mon_icinga_log_file, \
    MonIcingaLastRead, mon_icinga_log_raw_service_flapping_data, \
    mon_icinga_log_raw_service_notification_data, cluster_timezone, \
    mon_icinga_log_raw_host_notification_data, mon_icinga_log_raw_host_flapping_data, \
    mon_icinga_log_raw_base, mon_icinga_log_full_system_dump, \
    mon_icinga_log_raw_host_downtime_data, mon_icinga_log_raw_service_downtime_data
from initat.tools import threading_tools, logging_tools, process_tools
from .constants import ILRParserEnum, IcingaLogLine
from .exceptions import *
from .log_aggregation import IcingaLogAggregator
from .log_reader_utils import HostServiceIDUtil
from ..config import global_config

__all__ = [
    "IcingaLogReader",
    "HostServiceIDUtil",
]


class IcingaLogReader(threading_tools.icswProcessObj):
    @classmethod
    def get_icinga_var_dir(cls):
        return os.path.join(
            global_config['MD_BASEDIR'],
            'var',
        )

    @classmethod
    def get_icinga_log_archive_dir(cls):
        return os.path.join(
            cls.get_icinga_var_dir(),
            'archives'
        )

    @classmethod
    def get_icinga_log_file(cls):
        return os.path.join(
            cls.get_icinga_var_dir(),
            '{}.log'.format(global_config['MD_TYPE'])
        )

    def process_init(self):
        global_config.enable_pm(self)
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            context=self.zmq_context,
        )
        # some global flags
        self.always_collect_warnings = True
        db_tools.close_connection()

        self.register_timer(
            self.update,
            30 if global_config["DEBUG"] else 300,
            instant=False,
            first_timeout=5,
        )

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def update(self):
        """ Called periodically. Only method to be called from outside of this class """
        if global_config["ENABLE_ICINGA_LOG_PARSING"]:
            self._service_map = {}
            for mcc in mon_check_command.objects.all():
                self._service_map[mcc.description.replace(" ", "_").lower()] = mcc.idx
                self._service_map[mcc.uuid] = mcc.idx
                self._service_map[mcc.idx] = mcc.idx

            self._historic_host_map = {
                entry.full_name: entry.pk for entry in device.objects.all().prefetch_related(
                    'domain_tree_node'
                )
            }
            self._valid_host_ids = frozenset(device.objects.all().values_list('pk', flat=True))

            # logs might contain ids which are not present any more.
            # we discard such data (i.e. ids not present in these sets:)

            parse_start_time = time.time()
            self._update_raw_data()
            parse_end_time = time.time()
            self.log(
                "parsing took {}".format(
                    logging_tools.get_diff_time_str(parse_end_time - parse_start_time)
                )
            )

            aggr_start_time = time.time()
            # prof_file_name = "/tmp/prof.out.{}".format(time.time())
            # self.log("profiling to {}".format(prof_file_name))
            # import cProfile
            # cProfile.runctx("self._icinga_log_aggregator.update()", globals(), locals(), prof_file_name)
            if True:
                IcingaLogAggregator(self).update()
            aggr_end_time = time.time()
            self.log(
                "aggregation took {}".format(
                    logging_tools.get_diff_time_str(aggr_end_time - aggr_start_time)
                )
            )

    def _update_raw_data(self):
        self.log("checking icinga log")

        # collect warnings for not spamming in release mode
        self._warnings = defaultdict(lambda: 0)

        # check where we last have read for log rotation
        last_read = MonIcingaLastRead.get_last_read()
        if last_read:
            self.log(
                "last icinga read until: {}".format(
                    self._parse_timestamp(last_read.timestamp)
                )
            )
        else:
            _arch_dir = IcingaLogReader.get_icinga_log_archive_dir()
            self.log(
                "no earlier icinga log read, reading archive ({})".format(
                    _arch_dir,
                )
            )
            # print("***", _arch_dir)
            files = glob.glob(
                os.path.join(
                    _arch_dir,
                    "{}*".format(global_config['MD_TYPE'])
                )
            )
            last_read_element = self.parse_archive_files(files)
            if last_read_element:
                # store from archive but with empty position and line_number
                last_read = self._update_last_read(0, last_read_element.timestamp, last_read_element.inode, 0)
                # this is a duplicate update, but ensures that we have a valid value here
            else:
                self.log("no earlier icinga log read and no archive data")
                # there was no earlier read and we weren't able to read anything from the archive,
                # so assume there is none
                last_read = MonIcingaLastRead()
                # safe time in past, but not too far cause we check logs of each day
                last_read.timestamp = int(
                    (
                        (
                            datetime.datetime.now() - datetime.timedelta(days=1)
                        ) - datetime.datetime(1970, 1, 1)
                    ).total_seconds()
                )
                last_read.position = 0
                last_read.inode = 0
                last_read.line_number = 1

        try:
            logfile = codecs.open(self.get_icinga_log_file(), "r", "utf-8", errors='replace')
        except IOError:
            self.log(
                "Failed to open log file {} : {}".format(
                    self.get_icinga_log_file(),
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            # check for log rotation
            logfile.seek(last_read.position)
            cur_inode = os.stat(self.get_icinga_log_file()).st_ino
            same_logfile_as_last_read = cur_inode == last_read.inode
            self.log(
                "Inode check: current={:d}, last={:d}, {}".format(
                    cur_inode,
                    last_read.inode,
                    "same" if same_logfile_as_last_read else "file changed",
                )
            )
            if same_logfile_as_last_read:
                self.log("continuing to read in current icinga log file")
                # no log rotation, continue reading current file
                # the current position of the file must be the next byte to read!
                self.parse_log_file(logfile, self.get_icinga_log_file(), last_read.line_number)
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
                    self.log(
                        "finished catching up with archive, continuing with current icinga log file"
                    )
                    # start reading cur file
                    logfile.seek(0)
                    self.parse_log_file(logfile, self.get_icinga_log_file(), 1)

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

        if self.always_collect_warnings or not global_config["DEBUG"]:
            if self._warnings:
                self.log("warnings while parsing:")
                for warning, multiplicity in self._warnings.items():
                    self.log(
                        "    {} ({})".format(warning, multiplicity),
                        logging_tools.LOG_LEVEL_WARN
                    )
                self.log("end of warnings while parsing")

    def parse_log_file(self, logfile: object, logfilepath: str, line_num: int, start_at=None) -> object:
        '''
        :param file logfile: Parsing starts at position of logfile. Must be the main icinga log file.
        :param logfilepath: Path to logfile if it is an archive logfile, not the current one
        :param int start_at: only consider entries older than start_at
        :return object: last_read element
        '''
        inode = os.stat(logfilepath).st_ino
        is_archive_logfile = os.path.basename(logfilepath).count("-")
        self.log(
            "parsing file {} (inode={:d}, archive={})".format(
                logfilepath,
                inode,
                "yes" if is_archive_logfile else "no",
            )
        )
        logfile_db = None
        if is_archive_logfile:
            try:
                logfile_db = mon_icinga_log_file.objects.get(filepath=logfilepath)
            except mon_icinga_log_file.DoesNotExist:
                logfile_db = mon_icinga_log_file(filepath=logfilepath)
                logfile_db.save()

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

        # lines actually read
        lines_read = 0
        start_line_num = line_num
        cur_line = None
        for line_raw in logfile:
            # check for special entry
            try:
                timestamp, msg = self._parse_line_timestamp(line_raw.rstrip("\n"), line_num)
                if msg.startswith("Successfully shutdown"):
                    # self.log("detected icinga shutdown by log")
                    # create alerts for all devices: indeterminate (icinga not running)
                    # note: this relies on the fact that on startup, icinga writes a status update on start
                    host_entry, service_entry, host_flapping_entry, service_flapping_entry = self._create_icinga_down_entry(
                        self._parse_timestamp(timestamp), msg, logfile_db, save=False
                    )
                    host_states.append(host_entry)
                    service_states.append(service_entry)
                    host_flapping_states.append(host_flapping_entry)
                    service_flapping_states.append(service_flapping_entry)

            except ILRMalformedLogEntry as e:
                self._handle_warning(e, logfilepath, cur_line.line_no if cur_line else None)

            # check for regular log entry
            try:
                cur_line = self._parse_line(
                    line_raw.rstrip("\n"),
                    line_num,
                )
                # only know line number for archive files
                # we want to discard older (reread) entries if start_at is given,
                # except for current states (these are at the beginning of each log file)
                # (we don't need the initial states here because they don't occur at turnovers)
                if start_at is None or (
                    cur_line.timestamp > start_at or cur_line.kind in (
                        ILRParserEnum.icinga_current_host_state,
                        ILRParserEnum.icinga_current_service_state
                    )
                ):
                    if cur_line.kind in (
                        ILRParserEnum.icinga_current_host_state,
                        ILRParserEnum.icinga_current_service_state,
                        ILRParserEnum.icinga_initial_host_state,
                        ILRParserEnum.icinga_initial_service_state,
                    ):
                        full_system_dump_times.add(cur_line.timestamp)
                    if cur_line.kind in (
                        ILRParserEnum.icinga_service_alert,
                        ILRParserEnum.icinga_current_service_state,
                        ILRParserEnum.icinga_initial_service_state
                    ):
                        entry = self.create_service_alert_entry(
                            cur_line,
                            cur_line.kind == ILRParserEnum.icinga_current_service_state,
                            cur_line.kind == ILRParserEnum.icinga_initial_service_state,
                            logfilepath,
                            logfile_db
                        )
                        if entry:
                            stats['service alerts'] += 1
                            service_states.append(entry)
                    elif cur_line.kind in (
                        ILRParserEnum.icinga_host_alert,
                        ILRParserEnum.icinga_current_host_state,
                        ILRParserEnum.icinga_initial_host_state
                    ):
                        entry = self.create_host_alert_entry(
                            cur_line,
                            cur_line.kind == ILRParserEnum.icinga_current_host_state,
                            cur_line.kind == ILRParserEnum.icinga_initial_host_state,
                            logfilepath,
                            logfile_db
                        )
                        if entry:
                            stats['host alerts'] += 1
                            host_states.append(entry)
                    elif cur_line.kind == ILRParserEnum.icinga_service_flapping_alert:
                        entry = self.create_service_flapping_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['service flapping alerts'] += 1
                            service_flapping_states.append(entry)
                    elif cur_line.kind == ILRParserEnum.icinga_host_flapping_alert:
                        entry = self.create_host_flapping_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['host flapping alerts'] += 1
                            host_flapping_states.append(entry)
                    elif cur_line.kind == ILRParserEnum.icinga_service_notification:
                        entry = self.create_service_notification_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['service notification'] += 1
                            service_notifications.append(entry)
                    elif cur_line.kind == ILRParserEnum.icinga_host_notification:
                        entry = self.create_host_notification_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['host notification'] += 1
                            host_notifications.append(entry)
                    elif cur_line.kind == ILRParserEnum.icinga_host_downtime_alert:
                        entry = self.create_host_downtime_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['host downtime alert'] += 1
                            host_downtimes.append(entry)
                    elif cur_line.kind == ILRParserEnum.icinga_service_downtime_alert:
                        entry = self.create_service_downtime_entry(cur_line, logfilepath, logfile_db)
                        if entry:
                            stats['service downtime alert'] += 1
                            service_downtimes.append(entry)
                    else:
                        pass  # line_raw is not of interest to us
                else:
                    old_ignored += 1

            except ILRMalformedLogEntry as e:
                self._handle_warning(e, logfilepath, cur_line.line_no if cur_line else None)
            line_num += 1
            lines_read += 1

        if stats:
            num_inserts = sum(stats.values())
        else:
            num_inserts = 0
        num_inserts = max(1, num_inserts)
        self.log(
            "created: {}, starting db-update (total {:d} inserts)".format(
                ", ".join(
                    [
                        "{} ({:d})".format(key, value) for key, value in stats.items()
                    ]
                ) or "nothing",
                num_inserts,
            )
        )
        s_time = time.time()

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
                self.log(
                    "Detected multiple objects for time {}, ignoring".format(
                        self._parse_timestamp(timestamp)
                    )
                )
        e_time = time.time()
        self.log(
            "read {:d} lines [{:d}:{:d}], ignored {:d} old ones, db-update took {} ({} per entry)".format(
                lines_read,
                start_line_num,
                start_line_num + lines_read,
                old_ignored,
                logging_tools.get_diff_time_str(e_time - s_time),
                logging_tools.get_diff_time_str((e_time - s_time) / num_inserts),
            )
        )

        if cur_line:  # if at least something has been read
            if is_archive_logfile:
                position = 0
                line_num = 1
            else:
                position = logfile.tell()
            return self._update_last_read(position, cur_line.timestamp, inode, line_num)
        else:
            return None

    def _update_last_read(self, position: int, timestamp: int, inode: int, cur_line: int) -> MonIcingaLastRead:
        """
        Keep track of which data was read. May be called with older timestamp (will be discarded).
        """
        last_read = MonIcingaLastRead.get_last_read()
        if last_read:
            if last_read.timestamp > timestamp:
                # early return
                return last_read  # tried to update with older timestamp
        else:
            last_read = MonIcingaLastRead()
        last_read.timestamp = timestamp
        last_read.position = position
        last_read.inode = inode
        last_read.line_number = cur_line
        last_read.save()
        self.log(
            "updating last read icinga log to {}".format(
                str(last_read),
            )
        )
        return last_read

    def parse_archive_files(self, files: list, start_at=None):
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
                # filename not appropriate
                self.log(
                    "invalid filename encountered in parse_archive_fikles: {}".format(logfilepath),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                logfilepath = os.path.join(IcingaLogReader.get_icinga_log_archive_dir(), logfilepath)
                logfiles_date_data.append((year, month, day, hour, logfilepath))

        retval = None

        for unused1, unused2, unused3, unused4, logfilepath in sorted(logfiles_date_data):

            try:
                if logfilepath.lower().endswith('bz2'):
                    logfile = bz2.open(logfilepath, "rt", encoding="utf-8", errors="replace")
                else:
                    logfile = codecs.open(logfilepath, "r", "utf-8", errors='replace')
            except:
                self.log(
                    "failed to open archive log file {} : {}".format(
                        logfilepath,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                last_read_element = self.parse_log_file(logfile, logfilepath, 1, start_at)
                if retval is None:
                    retval = last_read_element
                else:
                    if last_read_element.timestamp > retval.timestamp:
                        retval = last_read_element
                logfile.close()
                # check if we are supposed to die
                self.step()
                if self["exit_requested"]:
                    self.log("exit requested")
                    break

        return retval

    def _handle_warning(self, exception, logfilepath, cur_line_no):
        if self.always_collect_warnings or not global_config["DEBUG"]:
            # in release mode, we don't want spam so we collect the errors and log each according to the multiplicity
            self._warnings[str(exception)] += 1
        else:
            # log right away
            self.log(
                "in file {} line {}: {}".format(
                    logfilepath,
                    cur_line_no,
                    exception,
                ),
                logging_tools.LOG_LEVEL_WARN
            )

    def create_host_alert_entry(self, cur_line, log_rotation_state, initial_state, logfilepath, logfile_db=None):
        retval = None
        try:
            host, state, state_type, msg = self._parse_host_alert(cur_line)
        except ILRUnknownHostError as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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
        except (ILRUnknownHostError, ILRUnknownServiceError) as e:
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

    @classmethod
    def _parse_line_timestamp(cls, line: str, line_no: int) -> tuple:
        '''
        :return parsed timestamp and info_raw
        '''
        # format is:
        # [timestamp] line_type: info
        data = line.split(" ", 1)
        if len(data) != 2:
            raise ILRMalformedLogEntry("Malformed line {:d}: {} (error #1)".format(line_no, line))
        timestamp_raw, info_raw = data

        try:
            timestamp = int(timestamp_raw[1:-1])  # remove first and last char
        except:
            raise ILRMalformedLogEntry(
                "Malformed line {}: {} (error #2)".format(line_no, line)
            )

        return timestamp, info_raw

    @classmethod
    def _parse_line(cls, line: str, line_no: int) -> tuple:
        """
        :param line: line as string
        :param line_no: optional
        :return: parsed line as namedtuple
        """
        timestamp, info_raw = cls._parse_line_timestamp(line, line_no)
        data2 = info_raw.split(": ", 1)
        _kind_str = data2[0]
        if len(data2) == 2 and _kind_str.upper() == _kind_str and not any(_kind_str.count(_chr) for _chr in {"[", "]"}):
            kind, info = data2
            try:
                kind_enum = ILRParserEnum(kind)
            except:
                print("-" * 20)
                print("*", line, line_no)
                print("X:", kind)
                raise
            _t_line = IcingaLogLine(timestamp, kind_enum, info, line_no)
        else:
            # no line formatted as we need it
            info = info_raw
            _t_line = IcingaLogLine(timestamp, None, info, line_no)
        return _t_line

    def _parse_host_alert(self, cur_line: str) -> tuple:
        '''
        :return (int, str, str, str)
        '''
        # format is:
        # host;(DOWN|UP|UNREACHABLE);(SOFT|HARD);???;msg
        info = cur_line.info

        data = info.split(";", 4)
        if len(data) != 5:
            raise ILRMalformedLogEntry("Malformed host entry: {} (error #1)".format(info))

        host = self._resolve_host(data[0])
        if not host:
            raise ILRUnknownHostError("Failed to resolve host: {} (error #2)".format(data[0]))

        state = mon_icinga_log_raw_host_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[1], None)  # format as in db table
        if not state:
            raise ILRMalformedLogEntry("Malformed state entry: {} (error #3) {} {} ".format(info))

        state_type = {"SOFT": "S", "HARD": "H"}.get(data[2], None)  # format as in db table
        if not state_type:
            raise ILRMalformedLogEntry("Malformed host entry: {} (error #4)".format(info))

        msg = data[4]

        return host, state, state_type, msg

    def _parse_host_service(self, host_spec, service_spec: str) -> tuple:
        # used for service and service flapping alerts as well as service notifications

        # primary method: check special service description
        host, service, service_info = HostServiceIDUtil.parse_host_service_description(service_spec, self.log)

        # print("S", service_spec)
        # print("***", host, service, service_info)
        if host not in self._valid_host_ids:
            host = None  # host has been properly logged, but doesn't exist any more
        # print("S=", service, service_spec)
        if service in self._service_map:
            # is a valid service uuid or pk (intermediate format) resolve to pk
            # print(service, self._uuid_to_pk_map[service])
            service = self._service_map[service]
        elif service_spec.replace(" ", "_").lower() in self._service_map:
            # historic description
            service = self._service_map[service_spec.replace(" ", "_").lower()]
        else:
            # service has been properly logged, but doesn't exist any more
            service = None
        # print("->", host, service)

        if not host:
            host = self._resolve_host(host_spec)
        if not host:
            # can't use data without host
            raise ILRUnknownHostError("Failed to resolve host: {} (error #2)".format(host_spec))

        # TODO: generalise to other services
        if not service:
            # raise ILRUnknownServiceError("Failed to resolve service : {} (error #3)".format(service_spec))
            # this is not an entry with new format and also not a uniquely identifiable one
            # however we want to keep the data, even if it's not nicely identifiable
            service = None
            service_info = service_spec
        # print(" -> ", host, service, service_info)
        # host and service should be pks
        # service_info is a string
        return host, service, service_info

    def _parse_service_flapping_alert(self, cur_line):
        # format is:
        # host;service;(STARTED|STOPPED);msg
        info = cur_line.info
        data = info.split(";", 3)
        if len(data) != 4:
            raise ILRMalformedLogEntry("Malformed service flapping entry: {} (error #1)".format(info))

        host, service, service_info = self._parse_host_service(data[0], data[1])

        flapping_state = {
            "STARTED": mon_icinga_log_raw_base.START,
            "STOPPED": mon_icinga_log_raw_base.STOP
        }.get(data[2], None)  # format as in db table
        if not flapping_state:
            raise ILRMalformedLogEntry("Malformed flapping state entry: {} (error #7)".format(info))

        msg = data[3]

        return host, (service, service_info), flapping_state, msg

    def _parse_host_flapping_alert(self, cur_line):
        # format is:
        # host;(STARTED|STOPPED);msg
        info = cur_line.info
        data = info.split(";", 2)
        if len(data) != 3:
            raise ILRMalformedLogEntry("Malformed host flapping entry: {} (error #1)".format(info))

        host = self._resolve_host(data[0])
        flapping_state = {
            "STARTED": mon_icinga_log_raw_base.START,
            "STOPPED": mon_icinga_log_raw_base.STOP
        }.get(data[1], None)  # format as in db table
        if not flapping_state:
            raise ILRMalformedLogEntry("Malformed flapping state entry: {} (error #7)".format(info))
        msg = data[2]
        return host, flapping_state, msg

    def _parse_service_downtime_alert(self, cur_line):
        # format is:
        # host;service;(STARTED|STOPPED);msg
        info = cur_line.info
        data = info.split(";", 3)
        if len(data) != 4:
            raise ILRMalformedLogEntry("Malformed service downtime entry: {} (error #1)".format(info))

        host, service, service_info = self._parse_host_service(data[0], data[1])

        state = {
            "STARTED": mon_icinga_log_raw_base.START,
            "STOPPED": mon_icinga_log_raw_base.STOP
        }.get(data[2], None)  # format as in db table
        if not state:
            raise ILRMalformedLogEntry("Malformed service downtime state entry: {} (error #2)".format(info))

        msg = data[3]

        return host, (service, service_info), state, msg

    def _parse_host_downtime_alert(self, cur_line):
        # format is:
        # host;(STARTED|STOPPED);msg
        # msg is autogenerated (something like 'host has exited from downtime'), collect it anyway
        info = cur_line.info
        data = info.split(";", 2)
        if len(data) != 3:
            raise ILRMalformedLogEntry("Malformed host downtime entry: {} (error #1)".format(info))
        host = self._resolve_host(data[0])
        state = {
            "STARTED": mon_icinga_log_raw_base.START,
            "STOPPED": mon_icinga_log_raw_base.STOP
        }.get(data[1], None)  # format as in db table
        if not state:
            raise ILRMalformedLogEntry("Malformed host downtime state entry: {} (error #2)".format(info))
        msg = data[2]

        return host, state, msg

    def _parse_service_notification(self, cur_line):
        # format is:
        # user;host;service;($service_state);notification_type,msg
        info = cur_line.info
        data = info.split(";", 5)
        if len(data) != 6:
            raise ILRMalformedLogEntry("Malformed service notification entry: {} (error #1)".format(info))

        user = data[0]
        host, service, service_info = self._parse_host_service(data[1], data[2])
        state = mon_icinga_log_raw_service_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[3], None)
        # format as in db table
        if not state:
            raise ILRMalformedLogEntry("Malformed state in entry: {} (error #6)".format(info))
        notification_type = data[4]
        msg = data[5]
        return user, host, (service, service_info), state, notification_type, msg

    def _parse_host_notification(self, cur_line):
        # format is:
        # user;host;($host_state);notification_type,msg
        info = cur_line.info
        data = info.split(";", 4)
        if len(data) != 5:
            raise ILRMalformedLogEntry("Malformed service notification entry: {} (error #1)".format(info))

        user = data[0]
        host = self._resolve_host(data[1])
        state = mon_icinga_log_raw_host_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[2], None)
        # format as in db table
        if not state:
            raise ILRMalformedLogEntry("Malformed state in entry: {} (error #6)".format(info))
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
            raise ILRMalformedLogEntry("Malformed service entry: {} (error #1)".format(info))

        host, service, service_info = self._parse_host_service(data[0], data[1])

        state = mon_icinga_log_raw_service_alert_data.STATE_CHOICES_REVERSE_MAP.get(data[2], None)
        # format as in db table
        if not state:
            raise ILRMalformedLogEntry("Malformed state entry: {} (error #6)".format(info))

        state_type = {
            "SOFT": "S",
            "HARD": "H"
        }.get(data[3], None)  # format as in db table
        if not state_type:
            raise ILRMalformedLogEntry("Malformed host entry: {} (error #5)".format(info))

        msg = data[5]

        return host, (service, service_info), state, state_type, msg

    def _resolve_host(self, host_spec: str) -> int:
        '''
        @return int: pk of host or None
        '''
        return self._historic_host_map.get(host_spec, None)

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
