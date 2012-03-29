#!/usr/bin/python-init -Otu
#
# Copyright (C) 2008,2009,2010,2012 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" ipc communication tools """

try:
    import pyipc
except:
    pyipc = None
import sys
import struct
import os
import process_tools
import zmq
import time
import server_command

long_size = struct.calcsize("@l")
int_size  = struct.calcsize("@i")

def send_and_receive_zmq(target_host, command, *args, **kwargs):
    identity_str = process_tools.zmq_identity_str(kwargs.pop("identity_string", "ipc_com"))
    zmq_context = kwargs.pop("zmq_context")
    cur_timeout = kwargs.pop("timeout", 20)
    client_send = zmq_context.socket(zmq.PUSH)
    client_recv = zmq_context.socket(zmq.SUB)
    #client_send.setsockopt(zmq.IDENTITY, identity_str)
    client_send.setsockopt(zmq.LINGER, cur_timeout * 2)
    client_recv.setsockopt(zmq.SUBSCRIBE, identity_str)
    # kwargs["server"] : collrelay or snmprelay
    server_name = kwargs.pop("server")
    send_conn_str = "%s" % (process_tools.get_zmq_ipc_name(kwargs.pop("process", "receiver"), s_name=server_name))
    recv_conn_str = "%s" % (process_tools.get_zmq_ipc_name(kwargs.pop("process", "sender"), s_name=server_name))
    client_send.connect(send_conn_str)
    client_recv.connect(recv_conn_str)
    srv_com = server_command.srv_command(command=command, identity=identity_str)
    srv_com["host"] = target_host
    srv_com["raw"] = "True"
    srv_com["arg_list"] = " ".join(args)
    # add additional keys
    for key, value in kwargs.iteritems():
        srv_com[key] = "%d" % (value) if type(value) in [int, long] else value
    s_time = time.time()
    client_send.send_unicode(unicode(srv_com))
    client_send.close()
    s_time = time.time()
    if client_recv.poll(cur_timeout * 1000):
        id_str = client_recv.recv()
    else:
        id_str = None
    if id_str and client_recv.getsockopt(zmq.RCVMORE):
        e_time = time.time()
        if client_recv.poll((cur_timeout - (e_time - s_time)) * 1000):
            recv_str = client_recv.recv()
        else:
            recv_str = None
    else:
        recv_str = None
    client_recv.close()
    e_time = time.time()
    if recv_str and id_str:
        try:
            srv_reply = server_command.srv_command(source=recv_str)
        except:
            srv_reply = None
            raise
    else:
        srv_reply = None
        raise SystemError, "timeout (%d seconds) exceeded" % (cur_timeout)
    return srv_reply
    
def send_and_receive(target_host, command, **kwargs):
    return 2, "error deprecated call"
    ipc_key = kwargs.get("ipc_key", 100)
    if type(ipc_key) == type(""):
        ipc_key = int(file(ipc_key, "r").read().strip())
    msg_q = pyipc.MessageQueue(ipc_key,
                               kwargs.get("ipc_mode", 0666))
    mode = kwargs.get("mode", "host-relay")
    my_pid = os.getpid()
    if mode == "host-relay":
        # host-relay mode
        send_data = struct.pack("@l6i%ds%ds" % (len(target_host),
                                                len(command)),
                                1,
                                my_pid,
                                kwargs["target_port"],
                                kwargs.get("direct", 1),
                                0,
                                len(target_host),
                                len(command),
                                target_host,
                                command)
        header_len = long_size + 6 * int_size
    else:
        # snmp-relay mode
        snmp_community = kwargs.get("snmp_community", "public")
        send_data = struct.pack("@l5i%ds%ds%ds" % (len(target_host),
                                                   len(command),
                                                   len(snmp_community)),
                                1,
                                my_pid,
                                kwargs.get("snmp_version", 2),
                                len(target_host),
                                len(command),
                                len(snmp_community),
                                target_host,
                                command,
                                snmp_community)
        header_len = long_size + 3 * int_size
    msg_q.send(send_data)
    ret_str = ""
    while True:
        result = msg_q.receive(my_pid, 0)
        if mode == "host-relay":
            check_pid, f0, f1, cont, f2, ret_state, str_len = struct.unpack("@l6i", result[0:header_len])
        else:
            check_pid, ret_state, cont, str_len = struct.unpack("@l3i", result[0:header_len])
        act_str = struct.unpack("%ds" % (str_len), result[header_len:])[0]
        ret_str = "%s%s" % (ret_str, act_str)
        if not cont:
            break
    if kwargs.get("decode", False):
        if ret_str.startswith("ok"):
            ret_str = process_tools.net_to_sys(ret_str[3:])
        else:
            try:
                decoded = process_tools.net_to_sys(ret_str)
            except:
                pass
            else:
                ret_str = decoded
    return ret_state, ret_str

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    