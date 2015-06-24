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
from initat.tools import logging_tools
from initat.cluster.backbone.models import device_variable
from initat.discovery_server.discovery_struct import ExtCom
from initat.discovery_server.wmi_struct import WmiUtils


__all__ = [
    'get_wmic_cmd',
    'WmiEventLogScanner',
]


class WmiEventLogScanner(object):

    WMI_USERNAME_VARIABLE_NAME = "WMI_USERNAME"
    WMI_PASSWORD_VARIABLE_NAME = "WMI_PASSWORD"

    def __init__(self, log, target_device, target_ip, last_known_record_number=None):
        self.target_device = target_device
        self.target_ip = target_ip
        self.log = log
        self.last_known_record_number = last_known_record_number
        self.current_retrieve_lower_number = None

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

        self.ext_com = None  # always contains currently running command of phase
        # this class instance manages the currently active phase
        self.current_phase = WmiEventLogScanner.InitialPhase()

    def periodic_check(self):
        self.current_phase(self)

    def _handle_stderr(self, stderr_out, context):
        self.log("wmic command yielded expected errors in {}:".format(context), logging_tools.LOG_LEVEL_ERROR)
        for line in stderr_out.split("\n"):
            self.log(line, logging_tools.LOG_LEVEL_ERROR)
        self.log("end of errors", logging_tools.LOG_LEVEL_ERROR)

    class InitialPhase(object):
        def __call__(self, scanner):
            if scanner.last_known_record_number is not None:
                where_clause = "WHERE RecordNumber > {}".format(scanner.last_known_record_number)
            else:
                where_clause = ''

            cmd = WmiUtils.get_wmic_cmd(
                username=scanner.username,
                password=scanner.password,
                target_ip=scanner.target_ip,
                columns=["RecordNumber"],
                table="Win32_NTLogEvent",
                where_clause=where_clause,
            )

            print 'doing big query'

            scanner.ext_com = ExtCom(scanner.log, cmd, shell=False)  # shell=False since args must not be parsed again
            scanner.ext_com.run()

            scanner.current_phase = WmiEventLogScanner.FindOutMaximumPhase()

    class FindOutMaximumPhase(object):
        def __call__(self, scanner):
            if scanner.ext_com.finished() is not None:
                stdout_out, stderr_out = scanner.ext_com.communicate()

                # here, we expect the exit code to be set to error for large outputs, so we don't check it
                if stderr_out:
                    scanner._handle_stderr(stderr_out, "FindOutMaximum")

                print 'stdout len', len(stdout_out)
                print ' stderr'
                import pprint
                pprint.pprint(stderr_out)

                # begin phase 2
                parsed = WmiUtils.parse_wmic_output(stdout_out)
                if not parsed:
                    # we can't check error code, but we should check this
                    raise RuntimeError("Failed to obtain wmic output in FindOutMaximumPhase")

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

                scanner.log("last record number for {} is {}, new maximal one is {}".format(
                    scanner.target_device, scanner.last_known_record_number, maximal_record_number)
                )

                if scanner.last_known_record_number is None or maximal_record_number > scanner.last_known_record_number:
                    scanner.current_phase = WmiEventLogScanner.RetrieveEventsPhase(scanner, maximal_record_number)
                else:
                    # TODO: bailout
                    pass

                # maximal_record_number = 952103

    class RetrieveEventsPhase(object):
        # PAGINATION_LIMIT = 10000
        PAGINATION_LIMIT = 1000

        def __init__(self, scanner, to_record_number):
            # this is increased in the process
            self.from_record_number =\
                scanner.last_known_record_number if scanner.last_known_record_number is not None else 0
            # 1 is the first RecordNumber

            self.to_record_number = to_record_number

            self.retrieve_ext_com = None

        def __call__(self, scanner):
            com_finished = self.retrieve_ext_com is not None and self.retrieve_ext_com.finished() is not None
            is_initial = self.retrieve_ext_com is None
            if com_finished:
                # handle output

                stdout_out, stderr_out = self.retrieve_ext_com.communicate()

                if stderr_out:
                    scanner._handle_stderr(stderr_out, "RetrieveEvents")

                if self.retrieve_ext_com.finished() != 0:
                    raise RuntimeError("RetrieveEvents wmi command failed with code {}".format(self.retrieve_ext_com.finished()))

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
                if parsed:  # this may be empty for RecordNumber-holes
                    print 'fst', parsed[0]
                    for entry in parsed:
                        if 'RecordNumber' not in entry:
                            print 'not in 2 ', entry

                    maximal_record_number = max(entry.get('RecordNumber', -1) for entry in parsed)
                    print 'max', maximal_record_number

                self.from_record_number += self.__class__.PAGINATION_LIMIT
                self.retrieve_ext_com = None

            if com_finished or is_initial:
                # check whether to start next run
                if self.from_record_number >= self.to_record_number:
                    # TODO: bailout, done
                else:
                    # start next run
                    cmd = WmiUtils.get_wmic_cmd(
                        username=scanner.username,
                        password=scanner.password,
                        target_ip=scanner.target_ip,
                        columns=["RecordNumber, Message"],
                        table="Win32_NTLogEvent",
                        where_clause="WHERE RecordNumber > {} and RecordNumber <= {}".format(
                            self.from_record_number,
                            self.from_record_number + self.__class__.PAGINATION_LIMIT,
                        )
                    )
                    print 'call from ', self.from_record_number

                    self.retrieve_ext_com = ExtCom(scanner.log, cmd, debug=True,
                                                   shell=False)  # shell=False since args must not be parsed again
                    self.retrieve_ext_com.run()
