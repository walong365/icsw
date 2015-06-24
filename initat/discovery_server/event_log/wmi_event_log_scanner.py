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
from enum import enum
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

    # PAGINATION_LIMIT = 10000
    PAGINATION_LIMIT = 1000

    class _Phases(enum.Enum):
        find_out_maximum = 1
        retrieve = 2

    def __init__(self, log, target_device, target_ip, last_known_record_number=None):
        self.target_device = target_device
        self.target_ip = target_ip
        self.log = log
        self.last_known_record_number = last_known_record_number
        self.current_retrieve_lower_number = None
        self.phase = self._Phases.find_out_maximum

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

    def scan(self):

        # maximal_record_number = 952103

        if self.last_known_record_number is not None:
            where_clause = "WHERE RecordNumber > {}".format(self.last_known_record_number)
        else:
            where_clause = ''

        cmd = WmiUtils.get_wmic_cmd(
            username=self.username,
            password=self.password,
            target_ip=self.target_ip,
            columns=["RecordNumber"],
            table="Win32_NTLogEvent",
            where_clause=where_clause,
        )

        print 'doing big query'

        ext_com = ExtCom(self.log, cmd, shell=False)  # shell=False since args must not be parsed again
        ext_com.run()
        ext_com.popen.wait()

        print 'code', ext_com.finished()

        print 'stdout len', len(ext_com.communicate()[0])
        print ' stderr'
        import pprint
        pprint.pprint(ext_com.communicate()[1])

        # begin phase 2
        parsed = WmiUtils.parse_wmic_output(ext_com.communicate()[0])
        print 'len', len(parsed)
        print 'fst', parsed[0]

        # the last entry might be invalid since error messages are written to stdout as well
        # hence 'RecordNumber' may not be present in all entries
        maximal_record_number = max(entry.get('RecordNumber', -1) for entry in parsed)
        print 'max', maximal_record_number

        # usually, you get after less then 100k
        # [wmi/wmic.c:212:main()] ERROR: Retrieve result data.
        # NTSTATUS: NT code 0x8004106c - NT code 0x8004106c

        self.log("last record number for {} is {}, new maximal one is {}".format(self.target_device,
                                                                                 self.last_known_record_number,
                                                                                 maximal_record_number))

        if self.last_known_record_number is None or maximal_record_number > self.last_known_record_number:
            self.retrieve_events(self.last_known_record_number, maximal_record_number)

    def retrieve_events(self, from_number, to_number):
        # columns=["Category", "CategoryString", "ComputerName", "Data", "EventCode", "EventIdentifier", "EventType", "InsertionStrings", "Logfile", "Message", "RecordNumber", "SourceName", "TimeGenerated", "TimeWritten", "Type", "User"],

        if from_number is None:
            from_number = 0
            # 1 is the first RecordNumber

        if self.current_retrieve_lower_number is None:
            self.current_retrieve_lower_number = from_number

        while self.current_retrieve_lower_number < to_number:
            # TODO: loop as check functions called later

            cmd = WmiUtils.get_wmic_cmd(
                username=self.username,
                password=self.password,
                target_ip=self.target_ip,
                columns=["RecordNumber, Message"],
                table="Win32_NTLogEvent",
                where_clause="WHERE RecordNumber > {} and RecordNumber <= {}".format(
                    self.current_retrieve_lower_number,
                    self.current_retrieve_lower_number + self.__class__.PAGINATION_LIMIT,
                )
            )
            print 'call from ', self.current_retrieve_lower_number

            ext_com = ExtCom(self.log, cmd, debug=True, shell=False)  # shell=False since args must not be parsed again
            ext_com.run()
            ext_com.popen.wait()

            # TODO exit code check everywhere

            print 'code', ext_com.finished()

            _, tmpfilename = tempfile.mkstemp()
            f = open(tmpfilename, 'w')
            f.write(ext_com.communicate()[0])
            f.flush()
            print 'stdout len', len(ext_com.communicate()[0]), tmpfilename
            print ' stderr'
            import pprint
            pprint.pprint(ext_com.communicate()[1])

            parsed = WmiUtils.parse_wmic_output(ext_com.communicate()[0])
            print 'len', len(parsed)
            if parsed:
                print 'fst', parsed[0]
                for entry in parsed:
                    if 'RecordNumber' not in entry:
                        print 'not in 2 ', entry

                maximal_record_number = max(entry.get('RecordNumber', -1) for entry in parsed)
                print 'max', maximal_record_number

            self.current_retrieve_lower_number += self.__class__.PAGINATION_LIMIT