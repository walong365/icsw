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
import ssl

from initat.cluster.backbone.models import device

import traceback

class VmMachine:
    def __init__(self, name):
        self.name = name


class _VmHost:
    def __init__(self, name):
        self.name = name
        self.vmmachines = {}
        self.counter_name_rollup_key_dict = {}

    def add_vm_host(self, vmmachine):
        self.vmhosts[vmmachine.name] = vmmachine

    def __genenerate_counter_name_rollup_key_dict(self, counters):
        for counter in counters:
            counter_name = counter.nameInfo.key
            rollup = counter.rollupType
            key = counter.key

            if counter_name not in self.counter_name_rollup_key_dict:
                self.counter_name_rollup_key_dict[counter_name] = {}

            self.counter_name_rollup_key_dict[counter_name][rollup] = key


class Collector:
    def __init__(self):
        self.counter_name_rollup_key_dict = {}

        self.vmhosts = {}

    def __genenerate_counter_name_rollup_key_dict(self, counters):
        self.counter_name_rollup_key_dict = {}
        for counter in counters:
            counter_name = counter.nameInfo.key
            rollup = counter.rollupType
            key = counter.key

            if counter_name not in self.counter_name_rollup_key_dict:
                self.counter_name_rollup_key_dict[counter_name] = {}

            self.counter_name_rollup_key_dict[counter_name][rollup] = key


    def __get_vms(self, content):
        objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                          [vim.VirtualMachine],
                                                          True)
        virtual_machines = objview.view
        objview.Destroy()
        return virtual_machines

    def collect_call(self):
        devices = device.objects.all()
        for _device in devices:
            username = None
            password = None
            usernames = _device.device_variable_set.filter(name="vsphere_username")
            if usernames:
                username = usernames[0].value
            passwords = _device.device_variable_set.filter(name="vsphere_password")
            if passwords:
                password = passwords[0].value

            vsphere_port = 443
            vsphere_ports = _device.device_variable_set.filter(name="vsphere_port")
            if vsphere_ports:
                vsphere_port = int(vsphere_ports[0].value)


            if username and password:
                # Found VMWare/vsphere capable hypervisor, perform checks
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                ssl_context.verify_mode = ssl.CERT_NONE

                service_instance = connect.SmartConnect(host=_device.all_ips()[0],
                                                        user=username,
                                                        pwd=password,
                                                        port=vsphere_port,
                                                        sslContext=ssl_context)
                content = service_instance.RetrieveContent()
                perfManager = content.perfManager

                objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                                  [vim.HostSystem],
                                                                  True)


                host_systems = objview.view
                objview.Destroy()

                self.__genenerate_counter_name_rollup_key_dict(content.perfManager.perfCounter)
                for host_system in host_systems:
                    ## DYNAMIC/ALL counters
                    for counter_name in self.counter_name_rollup_key_dict.keys():
                        for rollup_type in self.counter_name_rollup_key_dict[counter_name]:
                            counter_id = self.counter_name_rollup_key_dict[counter_name][rollup_type]

                            metricId = vim.PerformanceManager.MetricId(counterId=counter_id, instance="*")

                            query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                                     entity=host_system,
                                                                     metricId=[metricId])
                            q = perfManager.QueryPerf(querySpec=[query])



                            if q:
                                try:
                                    print "counter_name: %s | rollup: %s" % (counter_name, rollup_type)
                                    for value in q[0].value:
                                        instance = value.id.instance
                                        if not instance:
                                            instance = ""
                                        print "\tinstance: %s | value: %s" % (instance, value.value[0])
                                except Exception as e:
                                    traceback.print_exc()

                    #Selection of counters ++ a bit of formatting
                    # counterId=1 --> AVERAGE Cpu usage during interval (max_interval = 20s?)
                    metricId = vim.PerformanceManager.MetricId(counterId=1, instance="")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    print "CPU usage as a percentage during the interval: %.2f" % (q[0].value[0].value[0] / 10000.0)

                    # counterId=5 --> AVERAGE cpu frequency during interval (max_interval = 20s?)
                    # displayed frequency is doubled, trippled, etc for each core on the machine
                    metricId = vim.PerformanceManager.MetricId(counterId=5, instance="")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    print "CPU Frequency (average) during the interval: %.2f" % (q[0].value[0].value[0])

                    # counterId=655360 --> AVERAGE number of read commands per datastorage instance
                    metricId = vim.PerformanceManager.MetricId(counterId=655360, instance="*")
                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    for datastore in q[0].value:
                        # print datastore.id.instance
                        print "Average number of read commands issued per second for datastore %s: %s" % (
                        datastore.id.instance, datastore.value[0])

                    # counterId=655361 --> AVERAGE number of write commands per datastorage instance
                    metricId = vim.PerformanceManager.MetricId(counterId=655361, instance="*")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    for datastore in q[0].value:
                        # print datastore.id.instance
                        print "Average number of write commands issued per second for datastore %s: %s" % (
                        datastore.id.instance, datastore.value[0])

                    # counterId=655362 --> AVERAGE rate of reading (in kb/s) to datastore
                    metricId = vim.PerformanceManager.MetricId(counterId=655362, instance="*")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    for datastore in q[0].value:
                        # print datastore.id.instance
                        print "Rate of reading data from the datastore %s: %s" % (
                        datastore.id.instance, datastore.value[0])

                    # counterId=655363 --> AVERAGE rate of writing (in kb/s) to datastore
                    metricId = vim.PerformanceManager.MetricId(counterId=655363, instance="*")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    for datastore in q[0].value:
                        # print datastore.id.instance
                        print "Rate of writing data from the datastore %s: %s" % (
                        datastore.id.instance, datastore.value[0])

                    # counterId=655364 --> AVERAGE time to read from a datastore
                    metricId = vim.PerformanceManager.MetricId(counterId=655364, instance="*")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    for datastore in q[0].value:
                        # print datastore.id.instance
                        print "Average time to read from the datastore %s: %s" % (
                        datastore.id.instance, datastore.value[0])

                    # counterId=655365 --> AVERAGE time to write to a datastore
                    metricId = vim.PerformanceManager.MetricId(counterId=655365, instance="*")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])

                    for datastore in q[0].value:
                        # print datastore.id.instance
                        print "Average time to write to the datastore %s: %s" % (
                        datastore.id.instance, datastore.value[0])

                    # counterId=196618 --> AVERAGE amount of data received per second
                    metricId = vim.PerformanceManager.MetricId(counterId=196618, instance="")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])
                    print "AVERAGE amount of data received per second: %.2f" % (q[0].value[0].value[0])

                    # counterId=196619 --> AVERAGE amount of data sent per second
                    metricId = vim.PerformanceManager.MetricId(counterId=196619, instance="")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])
                    print "AVERAGE amount of data sent per second: %.2f" % (q[0].value[0].value[0])

                    # counterId=262144 --> uptime (in seconds)
                    metricId = vim.PerformanceManager.MetricId(counterId=262144, instance="")

                    query = vim.PerformanceManager.QuerySpec(maxSample=1,
                                                             entity=host_system,
                                                             metricId=[metricId])
                    q = perfManager.QueryPerf(querySpec=[query])
                    print "Uptime: %.2f hours" % (q[0].value[0].value[0] / (60.0 * 60.0))

                    objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                                      [vim.VirtualMachine],
                                                                      True)
                print
                print "* Vms"
                objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                                  [vim.VirtualMachine],
                                                                  True)
                virtual_machines = objview.view
                objview.Destroy()

                for vm in virtual_machines:
                    print "VM_NAME: %s" % vm.config.name
                    print "Committed %.2f" % (vm.summary.storage.committed / (1024.0 * 1024.0))
                    print "Uncommited %.2f" % (vm.summary.storage.uncommitted / (1024.0 * 1024.0))
                    print "Unshared %.2f" % (vm.summary.storage.unshared / (1024.0 * 1024.0))

                    objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                                      [vim.Datastore],
                                                                      True)

                datastores = objview.view
                objview.Destroy()

                print "* DataStores"
                for datastore in datastores:
                    print datastore.summary.datastore

                    print "\tName: %s" % datastore.summary.name
                    print "\tSize: %2.f MB" % (datastore.summary.capacity / (1024.0 * 1024.0))
                    print "\tFreeSpace: %2.f MB" % (datastore.summary.freeSpace / (1024.0 * 1024.0))
                    print "\tType: %s" % (datastore.summary.type)
                    print "\tAttached VMS:"
                    for vm in datastore.vm:
                        print "\t\t%s" % vm
        # return
        #
        #
        #
        #
        # ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        # ssl_context.verify_mode = ssl.CERT_NONE
        #
        # service_instance = connect.SmartConnect(host=HOST,
        #                                         user=USERNAME,
        #                                         pwd=PASSWD,
        #                                         port=PORT,
        #                                         sslContext=ssl_context)
        #
        # content = service_instance.RetrieveContent()
        #
        # hosts = VmHost.objects.filter(name=HOST)
        # assert (len(hosts) < 2)
        #
        # if hosts:
        #     vmhost = hosts[0]
        #
        # else:
        #     vmhost = VmHost(name=HOST)
        #     vmhost.save()
        #     vms = self.__get_vms(content)
        #     for vm in vms:
        #         sub_device = VmSubDevice(name=vm.summary.config.name, vm_host=vmhost)
        #         sub_device.save()
        #
        # objview = content.viewManager.CreateContainerView(content.rootFolder,
        #                                                   [vim.Datastore],
        #                                                   True)
        #
        # datastores = objview.view
        # objview.Destroy()
        #
        # perfManager = content.perfManager
        # # print perfManager.perfCounter
        # # return
        #
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
        # objview = content.viewManager.CreateContainerView(content.rootFolder,
        #                                                           [vim.VirtualMachine],
        #                                                           True)
        # print
        # print "* Vms"
        # virtual_machines = objview.view
        # objview.Destroy()
        #
        # for vm in virtual_machines:
        #     print vm.summary
        # #     print vm.summary.storage
        # #     print "Committed %.2f" % (vm.summary.storage.committed / (1024.0 * 1024.0))
        # #     print "Uncommited %.2f" % (vm.summary.storage.uncommitted / (1024.0 * 1024.0))
        # #     print "Unshared %.2f" % (vm.summary.storage.unshared / (1024.0 * 1024.0))
        # #
        # objview = content.viewManager.CreateContainerView(content.rootFolder,
        #                                                           [vim.HostSystem],
        #                                                           True)
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
        #
        #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
        #                                              entity=host_system,
        #                                              metricId=[metricId])
        #     q = perfManager.QueryPerf(querySpec=[query])
        #     print "AVERAGE amount of data sent per second: %.2f" % (q[0].value[0].value[0])
        #
        #     # counterId=262144 --> uptime (in seconds)
        #     metricId = vim.PerformanceManager.MetricId(counterId=262144, instance="")
        #
        #     query = vim.PerformanceManager.QuerySpec(maxSample=1,
        #                                              entity=host_system,
        #                                              metricId=[metricId])
        #     q = perfManager.QueryPerf(querySpec=[query])
        #     print "Uptime: %.2f hours" % (q[0].value[0].value[0] / (60.0 * 60.0))
        #
        #
        # self.__genenerate_counter_name_rollup_key_dict(content.perfManager.perfCounter)
        # for host_system in host_systems:
        #     for counter_name in self.counter_name_rollup_key_dict.keys():
        #         for rollup_type in self.counter_name_rollup_key_dict[counter_name]:
        #             counter_id = self.counter_name_rollup_key_dict[counter_name][rollup_type]
        #
        #
        #             metricId = vim.PerformanceManager.MetricId(counterId=counter_id, instance="*")
        #
        #             query = vim.PerformanceManager.QuerySpec(maxSample=1,
        #                                                      entity=host_system,
        #                                                      metricId=[metricId])
        #             q = perfManager.QueryPerf(querySpec=[query])
        #
        #             if q:
        #                 try:
        #                     print "counter_name: %s | rollup: %s" % (counter_name, rollup_type)
        #                     for value in q[0].value:
        #                         instance = value.id.instance
        #                         if not instance:
        #                             instance = ""
        #                         print "\tinstance: %s | value: %s" % (instance, value.value[0])
        #                 except Exception as e:
        #                     traceback.print_exc()

