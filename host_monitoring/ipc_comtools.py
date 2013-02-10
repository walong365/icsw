#!/usr/bin/python-init -Otu
#
# Copyright (C) 2008,2009,2010,2012,2013 Andreas Lang-Nevyjel init.at
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
""" ipc communication tools, now using 0MQ as communication layer """

import sys
import process_tools
import zmq
import time
import server_command

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
    send_conn_str = "%s" % (process_tools.get_zmq_ipc_name(
        kwargs.pop("process", "receiver"),
        s_name=server_name,
        connect_to_root_instance=True,
    ))
    recv_conn_str = "%s" % (process_tools.get_zmq_ipc_name(
        kwargs.pop("process", "sender"),
        s_name=server_name,
        connect_to_root_instance=True,
    ))
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

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    