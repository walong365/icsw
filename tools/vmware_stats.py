#
# Copyright (C) 2016 Gregor Kaufmann, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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

from pyVim import connect
from pyVmomi import vim

import argparse
import ssl
import datetime




def get_args():
    """
   Supports the command-line arguments listed below.
   """
    parser = argparse.ArgumentParser(
        description='Process args for retrieving all the Virtual Machines')
    parser.add_argument('-s', '--host', required=True, action='store',
                        help='Remote host name to connect to')
    parser.add_argument('-n', '--port', type=int, default=443, action='store',
                        help='Port')
    parser.add_argument('-u', '--user', required=True, action='store',
                        help='User name')
    parser.add_argument('-p', '--password', required=True, action='store',
                        help='Password')
    args = parser.parse_args()
    return args


def main():
    args = get_args()

    #Disable SSL verification
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_context.verify_mode = ssl.CERT_NONE

    service_instance = connect.SmartConnect(host=args.host,
                                            user=args.user,
                                            pwd=args.password,
                                            port=int(args.port),
                                            sslContext=ssl_context)

    content = service_instance.RetrieveContent()

    objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                      [vim.Datastore],
                                                      True)

    datastores = objview.view
    objview.Destroy()

    perfManager = content.perfManager
    #print perfManager.perfCounter
    #return

    # print "* DataStores"
    # for datastore in datastores:
    #     print datastore.summary.datastore
    #
    #     print "\tName: %s" % datastore.summary.name
    #     print "\tSize: %2.f MB" % (datastore.summary.capacity / (1024.0 * 1024.0))
    #     print "\tFreeSpace: %2.f MB" % (datastore.summary.freeSpace / (1024.0 * 1024.0))
    #     print "\tType: %s" % (datastore.summary.type)
    #     print "\tAttached VMS:"
    #     for vm in datastore.vm:
    #         print "\t\t%s" % vm
    #
    objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                          [vim.VirtualMachine],
                                                          True)

    print
    print "* Vms"
    virtual_machines = objview.view
    objview.Destroy()

    for vm in virtual_machines:
        print vm.summary

    # objview = content.viewManager.CreateContainerView(content.rootFolder,
    #                                                           [vim.HostSystem],
    #                                                           True)
    #
    #
    # print
    # print "* Host System"
    # host_systems = objview.view
    # objview.Destroy()
    #
    # for host_system in host_systems:
    #     print host_system
    #     # counterId=1 --> AVERAGE Cpu usage during interval (max_interval = 20s?)
    #     metricId = vim.PerformanceManager.MetricId(counterId=1, instance="")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     print "CPU usage as a percentage during the interval: %.2f" % (q[0].value[0].value[0] / 10000.0)
    #
    #     # counterId=5 --> AVERAGE cpu frequency during interval (max_interval = 20s?)
    #     # displayed frequency is doubled, trippled, etc for each core on the machine
    #     metricId = vim.PerformanceManager.MetricId(counterId=5, instance="")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #
    #     print "CPU Frequency (average) during the interval: %.2f" % (q[0].value[0].value[0])
    #
    #
    #     # counterId=655360 --> AVERAGE number of read commands per datastorage instance
    #     metricId = vim.PerformanceManager.MetricId(counterId=655360, instance="*")
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     for datastore in q[0].value:
    #         #print datastore.id.instance
    #         print "Average number of read commands issued per second for datastore %s: %s" % (datastore.id.instance, datastore.value[0])
    #
    #     # counterId=655361 --> AVERAGE number of write commands per datastorage instance
    #     metricId = vim.PerformanceManager.MetricId(counterId=655361, instance="*")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     for datastore in q[0].value:
    #         #print datastore.id.instance
    #         print "Average number of write commands issued per second for datastore %s: %s" % (datastore.id.instance, datastore.value[0])
    #
    #     # counterId=655362 --> AVERAGE rate of reading (in kb/s) to datastore
    #     metricId = vim.PerformanceManager.MetricId(counterId=655362, instance="*")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     for datastore in q[0].value:
    #         #print datastore.id.instance
    #         print "Rate of reading data from the datastore %s: %s" % (datastore.id.instance, datastore.value[0])
    #
    #     # counterId=655363 --> AVERAGE rate of writing (in kb/s) to datastore
    #     metricId = vim.PerformanceManager.MetricId(counterId=655363, instance="*")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     for datastore in q[0].value:
    #         #print datastore.id.instance
    #         print "Rate of writing data from the datastore %s: %s" % (datastore.id.instance, datastore.value[0])
    #
    #     # counterId=655364 --> AVERAGE time to read from a datastore
    #     metricId = vim.PerformanceManager.MetricId(counterId=655364, instance="*")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     for datastore in q[0].value:
    #         #print datastore.id.instance
    #         print "Average time to read from the datastore %s: %s" % (datastore.id.instance, datastore.value[0])
    #
    #     # counterId=655365 --> AVERAGE time to write to a datastore
    #     metricId = vim.PerformanceManager.MetricId(counterId=655365, instance="*")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #
    #     for datastore in q[0].value:
    #         #print datastore.id.instance
    #         print "Average time to write to the datastore %s: %s" % (datastore.id.instance, datastore.value[0])
    #
    #     # counterId=196618 --> AVERAGE amount of data received per second
    #     metricId = vim.PerformanceManager.MetricId(counterId=196618, instance="")
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #     print "AVERAGE amount of data received per second: %.2f" % (q[0].value[0].value[0])
    #
    #     # counterId=196619 --> AVERAGE amount of data sent per second
    #     metricId = vim.PerformanceManager.MetricId(counterId=196619, instance="")
    #     startTime = datetime.datetime.now() - datetime.timedelta(minutes=1)
    #     endTime = datetime.datetime.now()
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #     print "AVERAGE amount of data sent per second: %.2f" % (q[0].value[0].value[0])
    #
    #     # counterId=262144 --> uptime (in seconds)
    #     metricId = vim.PerformanceManager.MetricId(counterId=262144, instance="")
    #     startTime = datetime.datetime.now() - datetime.timedelta(minutes=1)
    #     endTime = datetime.datetime.now()
    #
    #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
    #                                              entity=host_system,
    #                                              metricId=[metricId])
    #     q = perfManager.QueryPerf(querySpec=[query])
    #     print "Uptime: %.2f hours" % (q[0].value[0].value[0] / (60.0 * 60.0))

if __name__ == "__main__":
   main()
