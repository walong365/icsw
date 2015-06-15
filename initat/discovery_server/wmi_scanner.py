#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of icsw-server
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
import datetime

import pymongo
import pprint
import pytz
import wmi_client_wrapper


class WmiDataSource(object):
    def __init__(self, model, fields):
        self.model = model
        self.fields = fields

    def get_query(self):
        return "SELECT {} FROM {}".format(", ".join(self.fields), self.model)

    @classmethod
    def get_supported_data_sources(cls):
        # Win32_IP4RouteTable?
        return [
            WmiDataSource('Win32_Process', ['CreationDate', 'ExecutablePath', 'Description', 'Name', 'ProcessId',
                                            'ThreadCount', 'WorkingSetSize']),
            WmiDataSource('Win32_ComputerSystem', ['Caption', 'Description', 'InstallDate', 'Manufacturer', 'Model',
                                                   'Name', 'NumberOfLogicalProcessors', 'NumberOfProcessors',
                                                   'PCSystemType', 'Status', 'SystemType', 'TotalPhysicalMemory',
                                                   'Workgroup', 'Domain', 'DomainRole']),
            WmiDataSource('Win32_OperatingSystem', ['Caption', 'Description', 'Name', 'CountryCode', 'InstallDate',
                                                    'LastBootUpTime', 'Manufacturer', 'NumberOfProcesses',
                                                    'NumberOfUsers', 'OSProductSuite', 'Status', 'Version']),
            WmiDataSource('Win32_NetworkAdapterConfiguration', ['Caption', 'DefaultIPGateway', 'Description',
                                                                'DHCPServer', 'DNSDomain', 'DNSHostName', 'IPAddress',
                                                                'IPEnabled', 'IPSubnet', 'MACAddress', 'ServiceName']),
            # NetEnabled and NetConnectionStatus show which ones are 'active'
            WmiDataSource('Win32_NetworkAdapter', ['AdapterType', 'AdapterTypeID', 'Availability', 'Caption',
                                                   'Description', 'DeviceID', 'MACAddress', 'Manufacturer', 'Name',
                                                   'NetConnectionStatus', 'NetEnabled', 'PhysicalAdapter',
                                                   'ProductName', 'ServiceName', 'Speed', 'Status']),
            WmiDataSource('Win32_Product', ['Name', 'Caption', 'Description', 'PackageName', 'Version']),
        ]


if __name__ == '__main__':
    client = pymongo.MongoClient('localhost', 27017)

    db = client.my_test_db
    # print 'db', db

    t = db.table
    # t.insert_one({'id': 'foo', 'content': 'yay', 'num': 1, 'fl': 3.3, 'nest': {'a': 'b'}})
    # t.insert_one({'foo': ['bar', 42, 1]})

    # print 'found', t.find_one()
    # print 'all'
    # pprint.pprint(list(t.find()))
    # t.remove()
    print 'full contents'
    contents = list(t.find())
    pprint.pprint(contents)

    #compare(*contents[0:1])

    if False:
        pw = raw_input("pw:")
        print 'connecting'
        wmic = wmi_client_wrapper.WmiClientWrapper(
            username="Administrator",
            password=pw,
            host="192.168.1.43",
        )
        print 'connected'

        scan_result = {
            'scan_date': datetime.datetime.now(tz=pytz.utc)
        }
        for wmi_data_source in WmiDataSource.get_supported_data_sources():
            print 'querying', wmi_data_source.model
            scan_result[wmi_data_source.model] = wmic.query(wmi_data_source.get_query())

        t.insert(scan_result)
