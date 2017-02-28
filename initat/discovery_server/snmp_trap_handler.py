# Copyright (C) 2016-2017 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of icsw-server-server
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
""" report-server, report part """

import asyncio
import netifaces
import subprocess

from threading import Thread

from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
#from pysnmp.smi import builder, view

from pysnmp.proto.rfc1902 import ObjectName
from pyasn1.type.univ import ObjectIdentifier

from initat.cluster.backbone.models import net_ip, DeviceLogEntry
from initat.cluster.backbone import db_tools
from initat.tools import logging_tools, threading_tools
from .config import global_config



class SNMPTrapHandlerProcess(threading_tools.icswProcessObj):

    PROCESS_NAME = 'snmp_trap_handler'

    def process_init(self):
        global_config.enable_pm(self)
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            context=self.zmq_context
        )
        db_tools.close_connection()

        # run in background to allow signal handler(s) to work
        def t_fun(asyncio_loop):
            asyncio.set_event_loop(asyncio_loop)
            SNMPTrapHandlerProcess.init_snmp_trap_handler()
            asyncio_loop.run_forever()

        Thread(target=t_fun, args=(asyncio.get_event_loop(),)).start()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    @staticmethod
    def init_snmp_trap_handler():
        snmpEngine = engine.SnmpEngine()

        udp_domain_name_index = 0
        for netif in netifaces.interfaces():
            addresses = netifaces.ifaddresses(netif)
            if netifaces.AF_INET in addresses:
                for address in addresses[netifaces.AF_INET]:
                    address = address['addr']

                    udp_domain_name_index += 1
                    config.addTransport(
                        snmpEngine,
                        udp.domainName + (udp_domain_name_index,),
                        udp.UdpTransport().openServerMode((address, 162))
                    )

        config.addV1System(snmpEngine, 'public', 'public')

        # mibBuilder = builder.MibBuilder()
        # mibView = view.MibViewController(mibBuilder)

        # todo replace this with a pysnmp implementation
        def get_translation(obj):
            if type(obj) == ObjectName or type(obj) == ObjectIdentifier:
                try:
                    return subprocess.check_output(["/usr/bin/snmptranslate", str(obj)]).decode().strip()
                except Exception as e:
                    _ = e
            return str(obj)

        def callback_function(snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
            transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(state_reference)

            for net_ip_obj in net_ip.objects.filter(ip = transportAddress[0]):
                print(net_ip_obj.netdevice.device)

                for name, val in var_binds:
                    name_str = get_translation(name)
                    val_str = get_translation(val)

                    info_str = '%s = %s' % (name_str, val_str)
                    print(info_str)

                    DeviceLogEntry.new(
                        device=net_ip_obj.netdevice.device,
                        source=global_config["LOG_SOURCE_IDX"],
                        level=logging_tools.LOG_LEVEL_OK,
                        text=info_str
                    )


        ntfrcv.NotificationReceiver(snmpEngine, callback_function)

