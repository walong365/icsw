# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# this file is part of discovery-server
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
import tempfile
import django.utils.timezone
from initat.tools import logging_tools
from initat.cluster.backbone.models import device_variable
from initat.discovery_server.discovery_struct import ExtCom
from initat.discovery_server.wmi_struct import WmiUtils

from .event_log_scanner_base import EventLogPollerJobBase


__all__ = [
    'get_wmic_cmd',
    'WmiLogEntryJob',
]


class _WmiJobBase(EventLogPollerJobBase):

    WMI_USERNAME_VARIABLE_NAME = "WMI_USERNAME"
    WMI_PASSWORD_VARIABLE_NAME = "WMI_PASSWORD"

    def __init__(self, log, db, target_device, target_ip):
        super(_WmiJobBase, self).__init__(log, db, target_device, target_ip)

        self.username = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.WMI_USERNAME_VARIABLE_NAME)
        if not self.username:
            raise RuntimeError(
                "For WMI event log scanning, the device {} must have a device variable "
                "called \"{}\" which contains the user name for WMI on this device".format(
                    self.target_device, self.WMI_USERNAME_VARIABLE_NAME
                )
            )
        self.password = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.WMI_PASSWORD_VARIABLE_NAME)
        if not self.password:
            raise RuntimeError(
                "For WMI event log scanning, the device {} must have a device variable "
                "called \"{}\" which contains the user name for WMI on this device".format(
                    self.target_device, self.WMI_PASSWORD_VARIABLE_NAME
                )
            )
        self.ext_com = None  # always contains currently running command of phase in case it is shared

    def _handle_stderr(self, stderr_out, context):
        self.log("wmic command yielded error output in {}:".format(context), logging_tools.LOG_LEVEL_ERROR)
        for line in stderr_out.split("\n"):
            self.log(line, logging_tools.LOG_LEVEL_ERROR)
        self.log("end of errors", logging_tools.LOG_LEVEL_ERROR)


class WmiLogFileJob(_WmiJobBase):
    """Job to retrieve list of log files from wmi server"""

    def __init__(self, *args, **kwargs):
        super(WmiLogFileJob, self).__init__(*args, **kwargs)
        self.logfile_com = None

    def __unicode__(self):
        return u"WmiLogFileJob(dev={}, ip={})".format(self.target_device, self.target_ip)

    __repr__ = __unicode__

    def start(self):
        cmd = WmiUtils.get_wmic_cmd(
            username=self.username,
            password=self.password,
            target_ip=self.target_ip,
            columns=["LogfileName"],
            table="Win32_NTEventlogFile",
        )

        print 'doing log file scanning'

        self.logfile_com = ExtCom(self.log, cmd, debug=True,
                                  shell=False)  # shell=False since args must not be parsed again
        self.logfile_com.run()

    def periodic_check(self):
        do_continue = True
        if self.logfile_com.finished() is not None:
            do_continue = False
            stdout_out, stderr_out = self.logfile_com.communicate()

            if stderr_out:
                self._handle_stderr(stderr_out, "scanning for wmi log files")

            if self.logfile_com.finished() != 0:
                raise RuntimeError("Scanning for wmi log files failed with code {}".format(
                    self.logfile_com.finished())
                )
            else:
                parsed = WmiUtils.parse_wmic_output(stdout_out)
                logfiles = []
                for entry in parsed:
                    if 'LogfileName' not in entry:
                        self.log("Invalid entry in log file scanning: {}".format(entry), logging_tools.LOG_LEVEL_WARN)
                    else:
                        logfiles.append(entry['LogfileName'])

                # logfiles = ["Application"]
                self.log("Detected {} wmi logfiles for {}".format(len(logfiles), self.target_device))

                self.db.wmi_logfile.update_one(
                    filter={'device_pk': self.target_device.pk},
                    update={
                        '$set': {
                            'device_pk': self.target_device.pk,
                            'date': django.utils.timezone.now(),
                            'logfiles': logfiles,
                        }
                    },
                    upsert=True)

                print 'feeding db ', {
                    'date': django.utils.timezone.now(),
                    'logfiles': logfiles,
                    'device_pk': self.target_device.pk,
                }

        return do_continue

    def __eq__(self, other):
        return isinstance(other, WmiLogFileJob) and super(WmiLogFileJob, self).__eq__(other)


class WmiLogEntryJob(_WmiJobBase):
    """Job to retrieve entries from a single log file from a wmi server.

    This is a hard task since the wmi server stops sending data if it feels it has sent too much.
    We keep track of the last RecordNumber, which is unique in combination with logfile_name and device_pk
    (It identifies an entry in a logfile_name of a device).

    Retrieval works by logfile.
    First, we find out the maximum entry (by querying all entries and assuming that the latest ones are returned first).
    Then we retrieve the single entries in small batches.

    If too many queries a sent, the wmi server reaches some kind of quota and refuses to answer for a few minutes.
    """
    def __init__(self, log, db, target_device, target_ip, logfile_name, last_known_record_number=None):
        super(WmiLogEntryJob, self).__init__(log, db, target_device, target_ip)

        self.logfile_name = logfile_name
        self.last_known_record_number = last_known_record_number

        # this class instance manages the currently active phase
        self.current_phase = WmiLogEntryJob.InitialPhase()

    def __unicode__(self):
        return u"WmiLogEntryJob(dev={}, ip={}, logfile={}, rec_num={}, phase={})".format(
            self.target_device,
            self.target_ip,
            self.logfile_name,
            self.last_known_record_number,
            self.current_phase.__class__,
        )

    __repr__ = __unicode__

    def __eq__(self, other):
        if not isinstance(other, WmiLogEntryJob):
            return False

        return self.logfile_name == other.logfile_name and super(WmiLogEntryJob, self).__eq__(other)

    def periodic_check(self):
        do_continue = self.current_phase(self)
        if do_continue is None:
            self.log("phase {} returned None, did you forget to return the continue value?".format(self.current_phase),
                     logging_tools.LOG_LEVEL_WARN)
        return do_continue

    class InitialPhase(object):
        def __call__(self, job):
            where_clause = "WHERE Logfile = '{}'".format(job.logfile_name)
            if job.last_known_record_number is not None:
                where_clause += "AND RecordNumber > {}".format(job.last_known_record_number)

            cmd = WmiUtils.get_wmic_cmd(
                username=job.username,
                password=job.password,
                target_ip=job.target_ip,
                columns=["RecordNumber"],
                table="Win32_NTLogEvent",
                where_clause=where_clause,
            )
            job.log("Querying maximal entry for {} with last known record number {}".format(
                job.logfile_name, job.last_known_record_number)
            )

            job.ext_com = ExtCom(job.log, cmd, debug=True,
                                 shell=False)  # shell=False since args must not be parsed again
            job.ext_com.run()

            job.current_phase = WmiLogEntryJob.FindMaximumPhase()
            return True

    class FindMaximumPhase(object):
        def __call__(self, job):
            do_continue = True
            if job.ext_com.finished() is not None:
                stdout_out, stderr_out = job.ext_com.communicate()

                # here, we expect the exit code to be set to error for large outputs, so we don't check it
                if stderr_out:
                    job._handle_stderr(stderr_out, "FindMaximum")

                print 'stdout len', len(stdout_out)
                print ' stderr'
                import pprint
                pprint.pprint(stderr_out)

                # begin phase 2
                parsed = WmiUtils.parse_wmic_output(stdout_out)
                if not parsed:
                    # we can't check error code, but we should check this
                    job.log("No records found for {}".format(job))
                    do_continue = False
                else:
                    print 'len', len(parsed)
                    print 'fst', parsed[0]
                    print 'lst', parsed[-1]

                    # the last entry might be invalid since error messages are written to stdout as well
                    # hence 'RecordNumber' may not be present in all entries
                    def try_extract_record_number(entry):
                        try:
                            return int(entry.get('RecordNumber', -1))
                        except ValueError:
                            return -1
                    maximal_record_number = max(try_extract_record_number(entry) for entry in parsed)
                    print 'max', maximal_record_number

                    # usually, you get after less then 100k
                    # [wmi/wmic.c:212:main()] ERROR: Retrieve result data.
                    # NTSTATUS: NT code 0x8004106c - NT code 0x8004106c

                    job.log("last record number for {} is {}, new maximal one is {}".format(
                        job.target_device, job.last_known_record_number, maximal_record_number)
                    )

                    if job.last_known_record_number is None or \
                            maximal_record_number > job.last_known_record_number:
                        job.current_phase = WmiLogEntryJob.RetrieveEventsPhase(job.last_known_record_number,
                                                                               maximal_record_number)
                    else:
                        do_continue = False

                    # maximal_record_number = 952103
            return do_continue

    class RetrieveEventsPhase(object):
        PAGINATION_LIMIT = 10000

        def __init__(self, from_number, to_record_number):
            # this is increased in the process
            self.from_record_number = from_number if from_number is not None else 0
            # 1 is the first RecordNumber

            self.to_record_number = to_record_number

            self.retrieve_ext_com = None

        def get_next_upper_limit(self, lower_limit):
            return min(lower_limit + self.__class__.PAGINATION_LIMIT, self.to_record_number)

        def __call__(self, job):
            do_continue = True

            com_finished = self.retrieve_ext_com is not None and self.retrieve_ext_com.finished() is not None
            is_initial = self.retrieve_ext_com is None
            if com_finished:
                # handle output

                stdout_out, stderr_out = self.retrieve_ext_com.communicate()

                if stderr_out:
                    job._handle_stderr(stderr_out, "RetrieveEvents")

                if self.retrieve_ext_com.finished() != 0:
                    raise RuntimeError("RetrieveEvents wmi command failed with code {}".format(
                        self.retrieve_ext_com.finished())
                    )

                print 'code', self.retrieve_ext_com.finished()
                _, tmpfilename = tempfile.mkstemp()
                f = open(tmpfilename, 'w')
                f.write(stdout_out)
                f.flush()
                print 'stdout len', len(stdout_out), tmpfilename
                print ' stderr'
                import pprint
                pprint.pprint(stderr_out)

                parsed = WmiUtils.parse_wmic_output(stdout_out, try_handle_lists=True)
                print 'len', len(parsed)
                # `parsed` may be empty for RecordNumber-holes

                job.log("Found {} log entries between {} and {} for {}".format(
                    len(parsed),
                    self.from_record_number,
                    self.get_next_upper_limit(self.from_record_number),
                    job,
                ))

                maximal_record_number = self.get_next_upper_limit(self.from_record_number)

                db_entries = []
                date_now = django.utils.timezone.now()
                for log_entry in parsed:
                    record_number = log_entry.get('RecordNumber')
                    if record_number is None:
                        job.log("Warning: WMI log entry without record number, ignoring:", logging_tools.LOG_LEVEL_WARN)
                        job.log("{}".format(log_entry))
                    time_generated = log_entry.get('TimeGenerated')
                    if time_generated is None:
                        job.log("Warning: WMI log entry without TimeGenerated, ignoring:", logging_tools.LOG_LEVEL_WARN)
                        job.log("{}".format(log_entry))
                    else:
                        db_entries.append({
                            'time_generated': time_generated,
                            'logfile_name': job.logfile_name,
                            'entry': log_entry,
                            'record_number': record_number,
                            'device_pk': job.target_device.pk,
                        })
                job.db.wmi_event_log.insert_many(db_entries)

                job.db.wmi_logfile_maximal_record_number.update_one(
                    filter={
                        'device_pk': job.target_device.pk,
                        'logfile_name': job.logfile_name,
                    },
                    update={
                        '$set': {
                            'device_pk': job.target_device.pk,
                            'date': date_now,
                            'maximal_record_number': maximal_record_number,  # this entry may not actually be present
                        }
                    },
                    upsert=True,
                )

                self.from_record_number = maximal_record_number

                job.log("New maximal record number: {} (maximal to reach: {}) for {}".format(maximal_record_number,
                                                                                             self.to_record_number,
                                                                                             job))

                self.retrieve_ext_com = None

            if com_finished or is_initial:
                # check whether to start next run

                job.log("cond {}".format(self.from_record_number >= self.to_record_number))
                job.log("a {} {} b {} {}".format(self.from_record_number, type(self.from_record_number),
                                                 self.to_record_number, type(self.to_record_number)))
                if self.from_record_number >= self.to_record_number:
                    do_continue = False
                    job.log("Reached maximal record number {} (by {}).".format(self.to_record_number,
                                                                               self.from_record_number))
                else:
                    # start next run
                    cmd = WmiUtils.get_wmic_cmd(
                        username=job.username,
                        password=job.password,
                        target_ip=job.target_ip,
                        columns=["RecordNumber, Message, Category, CategoryString, ComputerName, EventCode, " +
                                 "EventIdentifier, InsertionStrings, SourceName, TimeGenerated, TimeWritten,  " +
                                 "Type, User"],
                        table="Win32_NTLogEvent",
                        where_clause="WHERE Logfile = '{}' AND RecordNumber > {} and RecordNumber <= {}".format(
                            job.logfile_name,
                            self.from_record_number,
                            self.get_next_upper_limit(self.from_record_number),
                        )
                    )
                    print 'start run', " ".join(cmd)
                    job.log("querying entries from {} to {} for {}".format(
                        self.from_record_number,
                        self.get_next_upper_limit(self.from_record_number),
                        job,
                    ))
                    print 'call from ', self.from_record_number

                    self.retrieve_ext_com = ExtCom(job.log, cmd, debug=True,
                                                   shell=False)  # shell=False since args must not be parsed again
                    self.retrieve_ext_com.run()

            return do_continue
