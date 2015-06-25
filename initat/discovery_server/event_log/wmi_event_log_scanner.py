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


__all__ = [
    'get_wmic_cmd',
    'WmiLogEntryWorker',
]


class _WmiWorkerBase(object):

    WMI_USERNAME_VARIABLE_NAME = "WMI_USERNAME"
    WMI_PASSWORD_VARIABLE_NAME = "WMI_PASSWORD"

    def __init__(self, log, db, target_device, target_ip):
        self.log = log
        self.db = db
        self.target_device = target_device
        self.target_ip = target_ip

        self.username = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.WMI_USERNAME_VARIABLE_NAME)
        if not self.username:
            raise RuntimeError(
                "For WMI event log scanning, the device {} must have a device variable " +
                "called \"{}\" which contains the user name for WMI on this device".format(
                    self.target_device, self.WMI_USERNAME_VARIABLE_NAME
                )
            )
        self.password = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.WMI_PASSWORD_VARIABLE_NAME)
        if not self.password:
            raise RuntimeError(
                "For WMI event log scanning, the device {} must have a device variable " +
                "called \"{}\" which contains the user name for WMI on this device".format(
                    self.target_device, self.WMI_PASSWORD_VARIABLE_NAME
                )
            )

        self.ext_com = None  # always contains currently running command of phase in case it is shared

    def start(self):
        # we start on first periodic_check
        pass

    def _handle_stderr(self, stderr_out, context):
        self.log("wmic command yielded errors in {}:".format(context), logging_tools.LOG_LEVEL_ERROR)
        for line in stderr_out.split("\n"):
            self.log(line, logging_tools.LOG_LEVEL_ERROR)
        self.log("end of errors", logging_tools.LOG_LEVEL_ERROR)

    def __eq__(self, other):
        if not isinstance(other, _WmiWorkerBase):
            return False
        return self.target_device == other.target_device and self.target_ip == other.target_ip


class WmiLogFileWorker(_WmiWorkerBase):

    def __init__(self, *args, **kwargs):
        super(WmiLogFileWorker, self).__init__(*args, **kwargs)
        self.logfile_com = None

    def __unicode__(self):
        return u"WmiLogFileWorker(dev={}, ip={})".format(self.target_device, self.target_ip)

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

        self.logfile_com = ExtCom(self.log, cmd, shell=False)  # shell=False since args must not be parsed again
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
        return isinstance(other, WmiLogFileWorker) and super(WmiLogFileWorker, self).__eq__(other)


class WmiLogEntryWorker(_WmiWorkerBase):
    def __init__(self, log, db, target_device, target_ip, logfile_name, last_known_record_number=None):
        super(WmiLogEntryWorker, self).__init__(log, db, target_device, target_ip)

        self.logfile_name = logfile_name
        self.last_known_record_number = last_known_record_number
        self.current_retrieve_lower_number = None

        # this class instance manages the currently active phase
        self.current_phase = WmiLogEntryWorker.InitialPhase()

    def __unicode__(self):
        return u"WmiLogEntryWorker(dev={}, ip={}, logfile={})".format(self.target_device,
                                                                      self.target_ip,
                                                                      self.logfile_name)

    __repr__ = __unicode__

    def __eq__(self, other):
        if not isinstance(other, WmiLogEntryWorker):
            return False

        return self.logfile_name == other.logfile_name and super(WmiLogEntryWorker, self).__eq__(other)

    def periodic_check(self):
        do_continue = self.current_phase(self)
        if do_continue is None:
            self.log("phase {} returned None, did you forget to return the continue value?".format(self.current_phase),
                     logging_tools.LOG_LEVEL_WARN)
        return do_continue

    class InitialPhase(object):
        def __call__(self, worker):
            where_clause = "WHERE Logfile = '{}'".format(worker.logfile_name)
            if worker.last_known_record_number is not None:
                where_clause += "AND RecordNumber > {}".format(worker.last_known_record_number)

            cmd = WmiUtils.get_wmic_cmd(
                username=worker.username,
                password=worker.password,
                target_ip=worker.target_ip,
                columns=["RecordNumber"],
                table="Win32_NTLogEvent",
                where_clause=where_clause,
            )
            worker.log("Querying maximal entry for {} with last known record number {}".format(
                worker.logfile_name, worker.last_known_record_number)
            )

            worker.ext_com = ExtCom(worker.log, cmd, debug=True,
                                    shell=False)  # shell=False since args must not be parsed again
            worker.ext_com.run()

            worker.current_phase = WmiLogEntryWorker.FindOutMaximumPhase()
            return True

    class FindOutMaximumPhase(object):
        def __call__(self, worker):
            do_continue = True
            if worker.ext_com.finished() is not None:
                stdout_out, stderr_out = worker.ext_com.communicate()

                # here, we expect the exit code to be set to error for large outputs, so we don't check it
                if stderr_out:
                    worker._handle_stderr(stderr_out, "FindOutMaximum")

                print 'stdout len', len(stdout_out)
                print ' stderr'
                import pprint
                pprint.pprint(stderr_out)

                # begin phase 2
                parsed = WmiUtils.parse_wmic_output(stdout_out)
                if not parsed:
                    # we can't check error code, but we should check this
                    worker.log("No records found for {}".format(worker))
                    do_continue = False
                else:
                    print 'len', len(parsed)
                    print 'fst', parsed[0]
                    print 'lst', parsed[-1]

                    # the last entry might be invalid since error messages are written to stdout as well
                    # hence 'RecordNumber' may not be present in all entries
                    maximal_record_number = max(entry.get('RecordNumber', -1) for entry in parsed)
                    print 'max', maximal_record_number

                    # usually, you get after less then 100k
                    # [wmi/wmic.c:212:main()] ERROR: Retrieve result data.
                    # NTSTATUS: NT code 0x8004106c - NT code 0x8004106c

                    worker.log("last record number for {} is {}, new maximal one is {}".format(
                        worker.target_device, worker.last_known_record_number, maximal_record_number)
                    )

                    if worker.last_known_record_number is None or \
                            maximal_record_number > worker.last_known_record_number:
                        worker.current_phase = WmiLogEntryWorker.RetrieveEventsPhase(worker.last_known_record_number,
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

        def __call__(self, worker):
            do_continue = True

            com_finished = self.retrieve_ext_com is not None and self.retrieve_ext_com.finished() is not None
            is_initial = self.retrieve_ext_com is None
            if com_finished:
                # handle output

                stdout_out, stderr_out = self.retrieve_ext_com.communicate()

                if stderr_out:
                    worker._handle_stderr(stderr_out, "RetrieveEvents")

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

                parsed = WmiUtils.parse_wmic_output(stdout_out)
                print 'len', len(parsed)
                # `parsed` may be empty for RecordNumber-holes

                worker.log("Found {} log entries between {} and {} for {}".format(
                    len(parsed),
                    self.from_record_number,
                    self.from_record_number + self.__class__.PAGINATION_LIMIT,
                    worker,
                ))

                maximal_record_number = self.from_record_number + self.__class__.PAGINATION_LIMIT

                db_entry = {
                    'date': django.utils.timezone.now(),
                    'maximal_record_number': maximal_record_number,  # this entry may not actually be present
                    'logfile_name': worker.logfile_name,
                    'entries': parsed,
                    'device_pk': worker.target_device.pk,
                }
                worker.db.wmi_event_log.insert(db_entry)

                self.from_record_number = maximal_record_number

                worker.log("New maximal record number: {} (maximal to reach: {}) for {}".format(maximal_record_number,
                                                                                                self.to_record_number,
                                                                                                worker))

                self.retrieve_ext_com = None

            if com_finished or is_initial:
                # check whether to start next run
                if self.from_record_number >= self.to_record_number:
                    do_continue = False
                    worker.log("Reached maximal record number {} (by {}).".format(self.to_record_number,
                                                                                  self.from_record_number))
                else:
                    # start next run
                    cmd = WmiUtils.get_wmic_cmd(
                        username=worker.username,
                        password=worker.password,
                        target_ip=worker.target_ip,
                        columns=["RecordNumber, Message"],
                        table="Win32_NTLogEvent",
                        where_clause="WHERE Logfile = '{}' AND RecordNumber > {} and RecordNumber <= {}".format(
                            worker.logfile_name,
                            self.from_record_number,
                            self.from_record_number + self.__class__.PAGINATION_LIMIT,
                        )
                    )
                    worker.log("querying entries from {} to {} for {}".format(
                        self.from_record_number,
                        self.from_record_number + self.__class__.PAGINATION_LIMIT,
                        worker,
                    ))
                    print 'call from ', self.from_record_number

                    self.retrieve_ext_com = ExtCom(worker.log, cmd, debug=True,
                                                   shell=False)  # shell=False since args must not be parsed again
                    self.retrieve_ext_com.run()

            return do_continue