#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006,2007,2009,2010,2011,2012,2013 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of python-modules-base
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
""" network middleware """

import sys
import os
import socket
import select
import logging_tools
import threading
import time
import icmp
import ip
import zmq
import server_command
import operator

SHOW_DEL = False

# flags for report_problem
NET_EMPTY_READ         = 1
NET_TIMEOUT            = 2
NET_POLL_ERROR         = 4
NET_NOT_CONNECTED      = 8
NET_CONNECTION_REFUSED = 16
NET_EMPTY_SEND         = 32
NET_MESSAGE_TOO_LONG   = 64

# copy from process_tools
def get_except_info(exc_info=None):
    if not exc_info:
        exc_info = sys.exc_info()
    return "%s (%s)" % (str(exc_info[0]),
                        str(exc_info[1]))

def net_flag_to_str(flag):
    return {NET_EMPTY_READ         : "NET_EMPTY_READ",
            NET_TIMEOUT            : "NET_TIMEOUT",
            NET_POLL_ERROR         : "NET_POLL_ERROR",
            NET_NOT_CONNECTED      : "NET_NOT_CONNECTED",
            NET_CONNECTION_REFUSED : "NET_CONNECTION_REFUSED",
            NET_EMPTY_SEND         : "NET_EMPTY_SEND",
            NET_MESSAGE_TOO_LONG   : "NET_MESSAGE_TOO_LONG"}[flag]

class zmq_connection(object):
    def __init__(self, identity_str, **kwargs):
        if "context" in kwargs:
            self.context = kwargs["context"]
        else:
            self.context = zmq.Context()
        # linger time in msecs
        self.__linger_time = kwargs.get("linger", 500)
        self.__timeout = kwargs.get("timeout", 5)
        self.identity = identity_str
        self.poller = zmq.Poller()
        self.poller_handler = {}
        self.__results = {}
        self.__pending = set()
        self.__add_list = []
        self.__socket_dict = {}
        self.__registered = set()
    def register_poller(self, zmq_socket, sock_fd, poll_type, callback):
        self.poller_handler.setdefault(zmq_socket, {})[poll_type] = callback
        if sock_fd in self.__registered:
            self.poller.modify(zmq_socket, operator.ior(*self.poller_handler[zmq_socket].keys()))
        else:
            self.poller.register(zmq_socket, poll_type)
            self.__registered.add(sock_fd)
    def unregister_poller(self, zmq_socket):
        if type(zmq_socket) == type(0):
            zmq_socket = self.__socket_dict[zmq_socket]
        del self.poller_handler[zmq_socket]
        self.poller.unregister(zmq_socket)
    def add_connection(self, conn_str, command, **kwargs):
        new_sock = self.context.socket(zmq.DEALER)
        new_sock.setsockopt(zmq.LINGER, self.__linger_time)
        new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
        new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        #print new_sock.getsockopt(zmq.NOBLOCK)
        #new_sock.setsockopt(zmq.NOBLOCK, 1)
        #print new_sock.getsockopt(zmq.NOBLOCK)
        new_sock.setsockopt(zmq.IDENTITY, self.identity)
        new_sock.connect(conn_str)
        if isinstance(command, server_command.srv_command):
            c_type = "sc"
        else:
            c_type = None
        #self.register_poller(new_sock, zmq.POLLOUT, self.__show)
        sock_fd = new_sock.getsockopt(zmq.FD)
        self.register_poller(new_sock, sock_fd, zmq.POLLIN, self.__receive)
        #self.register_poller(new_sock, sock_fd, zmq.POLLERR, self.__show)
        self.__socket_dict[sock_fd] = new_sock
        self.__results[sock_fd] = None
        self.__pending.add(sock_fd)
        self.__add_list.append((sock_fd, c_type))
        new_sock.send_unicode(unicode(command))
        if not kwargs.get("multi", False):
            return self.loop()[0]
    def loop(self):
        start_time = time.time()
        while True:
            socks = self.poller.poll(timeout=max(self.__timeout, 1) * 1000)
            for sock, c_type in socks:
                try:
                    cur_cb = self.poller_handler[sock][c_type]
                except KeyError:
                    print "unknown key for loop(): (%s, %d)" % (str(sock),
                                                                c_type)
                else:
                    cur_cb(sock)
            cur_time = time.time()
            if abs(cur_time - start_time) >= self.__timeout:
                # need list to avoid 'object has changed ...' error
                for sock_fd in list(self.__pending):
                    self._close_socket(sock_fd)
            if not self.__pending:
                break
        #self.context.term()
        return [self._interpret_result(com_type, self.__results[cur_fd]) for cur_fd, com_type in self.__add_list]
    def __show(self, sock_fd):
        print sock_fd
    def _close_socket(self, sock_fd):
        self.unregister_poller(sock_fd)
        self.__socket_dict[sock_fd].close()
        del self.__socket_dict[sock_fd]
        self.__pending.remove(sock_fd)
    def _interpret_result(self, in_type, in_bytes):
        if in_bytes is not None:
            if in_type == "sc":
                in_bytes = server_command.srv_command(source=in_bytes)
        return in_bytes
    def __receive(self, sock):
        sock_fd = sock.getsockopt(zmq.FD)
        self.__results[sock_fd] = sock.recv()
        self._close_socket(sock_fd)

class icmp_host(object):
    def __init__(self, icmp_handler, h_name, timeout, flood_ping, fast_mode, send_rate):
        self.__handler = icmp_handler
        self.name = h_name
        self.__flood_ping = flood_ping
        self.__fast_mode  = fast_mode
        self.__send_rate = send_rate
        try:
            fq_name, aliases, ip_list = socket.gethostbyname_ex(h_name)
        except:
            raise ValueError, "Unable to resolve host"
        else:
            self.ip = ip_list[0]
        self.__packets = []
        self.__timeout = timeout
        self.__last_send = 0
    def __del__(self):
        if SHOW_DEL:
            print "**del icmp_host"
    def generate_packets(self, sock, num, c_id):
        self.__num_packets, self.__packets_send, self.__packets_received, self.__packets_timeout = (num, 0, 0, 0)
        self.__send_times, self.__packet_times = ([], [])
        for idx in xrange(num):
            self.__packets.append(sock.generate_icmp_packet(c_id))
        self.__first_send = None
    def get_next_packet(self, act_time):
        self.__packets_send += 1
        act_time = time.time()
        self.__send_times.append(act_time)
        if self.__first_send is None:
            self.__first_send = act_time
        self.__last_send = act_time
        return self.__packets.pop(0)
    def packets_left(self):
        return self.__packets and True or False
    def reply_received(self):
        #print "recv from", self.ip
        self.__packets_received += 1
        if self.__send_times:
            # keep packet-time
            self.__packet_times.append(abs(time.time() - self.__send_times.pop(0)))
            if self.__fast_mode or (self.__packets_timeout + self.__packets_received == self.__num_packets):
                # all received
                self.__packets = []
                self._host_finished()
    def check_for_timeout(self, act_time):
        if self.__first_send and abs(act_time - self.__first_send) > self.__timeout:
            # timeout
            self.__packets_timeout = self.__num_packets - self.__packets_received
            self._host_finished()
            return 1000. * self.__timeout
        else:
            #print self.__send_times
            while self.__send_times:
                if abs(act_time - self.__send_times[0]) > self.__timeout:
                    self.__packets_timeout += 1
                    self.__send_times.pop(0)
                    if self.__packets_timeout + self.__packets_received == self.__num_packets:
                        # all received
                        self._host_finished()
                        break
                else:
                    break
            if self.__send_times:
                #print "TO", (abs(self.__timeout - abs(act_time - self.__send_times[0])))
                rv = 1000. * min([abs(self.__timeout - abs(act_time - self.__send_times[0])), self.__send_rate])
            else:
                rv = 1000. * min([self.__timeout, self.__send_rate])
            if self.__packets and self.__handler:
                if abs(act_time - self.__last_send) >= self.__send_rate:
                    self.__handler.ready_to_send(self)
                elif self.__flood_ping:
                    self.__handler.ready_to_send(self)
            return rv
    def rate_ok(self, act_time):
        return abs(self.__last_send - act_time) >= self.__send_rate
    def _host_finished(self):
        r_dict = {"send"     : self.__packets_send,
                  "received" : self.__packets_received,
                  "timeout"  : self.__packets_timeout}
        if self.__packet_times:
            r_dict["min_time"], r_dict["max_time"], r_dict["mean_time"] = (min(self.__packet_times),
                                                                           max(self.__packet_times),
                                                                           sum(self.__packet_times) / len(self.__packet_times))
        if self.__handler:
            self.__handler.host_finished(self, r_dict)
            self.__handler = None
    def _remove_host(self):
        r_dict = {"send"     : self.__packets_send,
                  "received" : self.__packets_received,
                  "timeout"  : self.__packets_timeout}
        if self.__packet_times:
            r_dict["min_time"], r_dict["max_time"], r_dict["mean_time"] = (min(self.__packet_times),
                                                                           max(self.__packet_times),
                                                                           sum(self.__packet_times) / len(self.__packet_times))
        self.__handler = None
        
class icmp_client(object):
    def __init__(self, **args):
        self.socket = None
        self.set_host_parameters(**args)
    def __del__(self):
        if SHOW_DEL:
            print "**del icmp_client"
    def set_host_parameters(self, **args):
        self.__h_list = args["host_list"]
        self.__timeout = args.get("timeout", 5)
        self.__num_ping = args.get("num_ping", 3)
        self.__flood_ping = args.get("flood_ping", False)
        # fast mode means one ok-packet is enough per IP
        self.__fast_mode = args.get("fast_mode", False)
        # any_host_ok, for broadcast_pings from mother
        self.__any_host_ok = args.get("any_host_ok", False)
        self.__finish_call = args.get("finish_call", None)
        self.__send_rate = args.get("send_rate", 0.1)
        self.__add_data = args.get("add_data", None)
    def get_add_data(self):
        return self.__add_data
    def link_socket(self, sock, c_id):
        self.c_id = c_id
        self.socket = sock
    def remove_socket(self):
        self.socket = None
    def get_client_id(self):
        return self.c_id
    def register_packets_to_send(self, num):
        self.socket.register_packets_to_send(self, num)
    def setup_done(self):
        self.__host_results = {}
        # resolve hosts, inv_lut
        self.__host_lut, self.__inv_host_lut, self.__hosts_to_work = ({}, {}, {})
        num_ok_hosts = 0
        for host in self.__h_list:
            try:
                ic_host = icmp_host(self, host, self.__timeout, self.__flood_ping, self.__fast_mode, self.__send_rate)
            except ValueError, why:
                self.__host_results[host] = str(why)
            else:
                if ic_host.ip in self.__inv_host_lut:
                    self.__inv_host_lut[ic_host.ip].append(ic_host.name)
                    self.__host_lut[ic_host.name] = ic_host.ip
                else:
                    num_ok_hosts += 1
                    self.__host_lut[ic_host.name] = ic_host.ip
                    self.__inv_host_lut[ic_host.ip] = [ic_host.name]
                    self.__hosts_to_work[ic_host.ip] = ic_host
                    ic_host.generate_packets(self.socket, self.__num_ping, self.get_client_id())
        if num_ok_hosts:
            self.__packets_to_send = num_ok_hosts * self.__num_ping
            self.register_packets_to_send(num_ok_hosts * self.__num_ping)
        else:
            self.socket.remove_icmp_client(self)
            if self.__finish_call:
                self.__finish_call(self)
        self.__send_ips = self.__inv_host_lut.keys()
    def packets_to_send(self):
        return self.__packets_to_send
    def _get_packet(self):
        act_time = time.time()
        # further packets to send after this batch ?
        f_t_s = False
        ret_p = []
        if self.__packets_to_send:
            for d_ip in self.__send_ips:
                act_h = self.__hosts_to_work[d_ip]
                send_p = False
                if self.__flood_ping and act_h.packets_left():
                    send_p = True
                elif not self.__flood_ping and (act_h.packets_left() and act_h.rate_ok(act_time)):
                    send_p = True
                else:
                    send_p = False
                if send_p:
                    ret_p.append((act_h.ip,
                                  act_h.get_next_packet(act_time)))
                    self.__packets_to_send -= 1
                if self.__flood_ping and act_h.packets_left():
                    f_t_s = True
        self.__f_t_s = f_t_s
        return ret_p
    def further_packets_to_send(self):
        return self.__f_t_s
    def ready_to_send(self, ic_host):
        self.socket.ready_to_send()
    def host_finished(self, ic_host, result):
        self.__send_ips.remove(ic_host.ip)
        for host in self.__inv_host_lut[ic_host.ip]:
            self.__host_results[host] = result
        del self.__hosts_to_work[ic_host.ip]
        if self.__any_host_ok and result["received"]:
            # we are done with one host, skip the rest
            for host_ip in self.__hosts_to_work.keys():
                for h_name in self.__inv_host_lut[host_ip]:
                    self.__host_results[h_name] = self.__hosts_to_work[host_ip]._remove_host()
                del self.__hosts_to_work[host_ip]
            self.__send_ips = []
        #self.__host_results[
        if not self.__send_ips:
            self.socket.remove_icmp_client(self)
            # remove icmp_hosts 
            del self.__hosts_to_work
            if self.__finish_call:
                self.__finish_call(self)
    def check_for_timeout(self, act_time):
        # returns timeout until the next packet has to be received
        return min([1000. * self.__timeout] + [h.check_for_timeout(act_time) for h in self.__hosts_to_work.values()])
    def reply_received(self, src_host):
        if src_host in self.__hosts_to_work:
            self.__hosts_to_work[src_host].reply_received()
    def get_result(self):
        return self.__host_results
    def is_flood_ping(self):
        return self.__flood_ping
    
def ping_hosts(h_list, num_ping, timeout):
    def _log(what, level):
        pass
    #print h_list, num_ping, timeout
    ping_s = network_send(timeout=1, log_hook=_log)
    try:
        ping_obj = icmp_bind(exit_on_finish=True)
    except:
        return {}
    else:
        ping_s.add_object(ping_obj)
        my_c = icmp_client(host_list=h_list, num_ping=num_ping, timeout=timeout, fast_mode=True)
        ping_obj.add_icmp_client(my_c)
        while not ping_s.exit_requested():
            ping_s.step()
        return my_c.get_result()

def check_for_proto_1_header(in_str):
    if in_str[0:8].isdigit() and len(in_str) - 8 == int(in_str[0:8]):
        return True, in_str[8:]
    else:
        return False, in_str

def add_proto_1_header(what, p1_head=True):
    # add str() cast for server_command structs
    if p1_head:
        return "%08d%s" % (len(what), str(what))
    else:
        return str(what)
    
class buffer_object(object):
    def __init__(self):
        #print "Init buffer object"
        self.in_buffer, self.out_buffer = ("", "")
        self.socket = None
        self.init_time = time.time()
        self.__lock = threading.Lock()
    def lock(self, blocking=True):
        return self.__lock.acquire(blocking)
    def unlock(self):
        self.__lock.release()
    def __del__(self):
        if SHOW_DEL:
            print "deleting buffer_object"
    def link_socket(self, sock):
        self.socket = sock
    def unlink_socket(self):
        if self.socket:
            self.socket = None
    def add_to_in_buffer(self, what):
        print "Please override me (add_to_in_buffer)"
        self.in_buffer += what
        self.add_to_out_buffer("ok")
    def add_to_out_buffer(self, what):
        #print "add_to_out_buffer skel", what
        # not thread safe
        self.out_buffer += what
        if self.out_buffer:
            self.socket.ready_to_send()
    def get_out_buffer(self):
        return self.out_buffer
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def report_problem(self, flags, what):
        print "problem (report_problem call, class buffer_object), flags=%d, what=%s" % (flags, what)
        print "init_time = %s, act_time = %s" % (time.ctime(self.init_time), time.ctime())
        print "in_buffer = '%s', out_buffer = '%s'" % (self.in_buffer, self.out_buffer)
        self.close()
    def delete(self):
        self.socket.delete()
        self.close()
    def close(self):
        #print "Closing buffer object"
        self.lock()
        self.socket.close()
        self.unlock()
    def setup_done(self):
        pass

POLL_IN  = select.POLLIN | select.POLLPRI
POLL_OUT = select.POLLOUT
POLL_ERR = select.POLLERR | select.POLLHUP | select.POLLNVAL

def poll_flag_to_str(flags):
    f_str = [s for f, s in [(select.POLLIN  , "POLLIN"  ),
                            (select.POLLPRI , "POLLPRI" ),
                            (select.POLLOUT , "POLLOUT" ),
                            (select.POLLERR , "POLLERR" ),
                            (select.POLLHUP , "POLLHUP" ),
                            (select.POLLNVAL, "POLLNVAL")] if flags & f]
    return f_str and "|".join(f_str) or "<none set>"

class buffer_object_p1(buffer_object):
    # reference implementation for a simple protocoll-1 receiver / sender
    def __init__(self, work_queue):
        buffer_object.__init__(self)
        self.__work_queue = work_queue
        self.__header_ok, self.__body_len = (False, 0)
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        proc = True
        while proc:
            if not self.__header_ok:
                if len(self.in_buffer) > 8:
                    try:
                        recv_len = int(self.in_buffer[0:8])
                    except:
                        pass
                    else:
                        self.__body_len = recv_len
                        self.__header_ok = True
                        self.in_buffer = self.in_buffer[8:]
            if len(self.in_buffer) >= self.__body_len:
                self.in_buffer = self.in_buffer[self.__body_len:]
                self.__work_queue.put(("R", self))
                #self.send_if_connected("ok")
                self.__header_ok = False
            else:
                proc = False
    def send_if_connected(self, what):
        # check if socket still exists
        self.lock()
        if self.socket:
            suc = True
            self.add_to_out_buffer("%08d%s" % (len(what), what))
        else:
            suc = False
        self.unlock()
        return suc
            #send_str = "ok"
            #self.add_to_out_buffer("%08d%s" % (len(send_str), send_str))

class poll_object(object):
    def __init__(self, **args):
        self.__log_handle = args.get("log_handle", None)
        self.__poll_object = select.poll()
        self.__poll_type_dict = {}
        self.__poll_inv_type_dict = {}
        self.set_verbose(args.get("poll_verbose", False))
    def set_verbose(self, vb=False):
        self.__verbose = vb
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__verbose:
            if self.__log_handle:
                self.__log_handle(what, lev)
            else:
                print "poll_object().log (%d): %s" % (lev, what)
    def poll_register(self, fd, pt):
        self.__poll_object.register(fd, pt)
        self.__poll_type_dict.setdefault(pt, []).append(fd)
        self.__poll_inv_type_dict[fd] = pt
        self.log("registering fd %d to type %d (%s)" % (fd, pt, poll_flag_to_str(pt)))
    def poll_check_registered(self, fd):
        return self.__poll_inv_type_dict.get(fd, 0)
    def poll_unregister(self, fd):
        if fd in self.__poll_inv_type_dict:
            try:
                self.__poll_object.unregister(fd)
            except KeyError:
                self.log("error trying to unregister fd %d from poll_object" % (fd), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.__poll_type_dict[self.__poll_inv_type_dict[fd]].remove(fd)
                del self.__poll_inv_type_dict[fd]
                self.log("unregistered fd %d from poll_object" % (fd))
        else:
            self.log("unknown fd %d for poll_unregister" % (fd), logging_tools.LOG_LEVEL_ERROR)
    def register_handle(self, handle, ht):
        if handle:
            if handle in self.__poll_inv_type_dict.keys():
                if self.__poll_inv_type_dict[handle] != ht:
                    self.poll_unregister(handle)
                    self.poll_register(handle, ht)
            else:
                self.poll_register(handle, ht)
    def get_registered_handles(self):
        return self.__poll_inv_type_dict.keys()
    def poll(self, to):
        do_poll = True
        while do_poll:
            try:
                p_res = self.__poll_object.poll(to)
            except select.error, (err_num, err_str):
                # catch select error
                self.log("select.error (%d): %s" % (err_num, err_str), logging_tools.LOG_LEVEL_ERROR)
            else:
                do_poll = False
        return p_res

class epoll_object(object):
    def __init__(self, **kwargs):
        self.__log_handle = kwargs.get("log_handle", None)
        self.__epoll_object = select.epoll()
        self.__epoll_type_dict = {}
        self.__epoll_inv_type_dict = {}
        self.verbose = kwargs.get("verbose", False)
        self.__lock = threading.RLock()
    @property
    def verbose(self):
        return self.__verbose
    @verbose.setter
    def verbose(self, vb):
        self.__verbose = vb
    def lock(self, blocking=True):
        return self.__lock.acquire(blocking)
    def unlock(self):
        self.__lock.release()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__verbose:
            if self.__log_handle:
                self.__log_handle(what, lev)
            else:
                print "epoll_object().log (%d): %s" % (lev, what)
    def unregister(self, fd):
        self.lock()
        if fd in self.__epoll_inv_type_dict:
            try:
                self.__epoll_object.unregister(fd)
            except KeyError:
                epoll_object.log(self, "error trying to unregister fd %d from epoll_object" % (fd), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.__epoll_type_dict[self.__epoll_inv_type_dict[fd]].remove(fd)
                del self.__epoll_inv_type_dict[fd]
                epoll_object.log(self, "unregistered fd %d from epoll_object" % (fd))
        else:
            epoll_object.log(self, "unknown fd %d for epoll_unregister" % (fd), logging_tools.LOG_LEVEL_ERROR)
        self.unlock()
    def register(self, handle, ht):
        self.lock()
        if handle:
            if handle in self.__epoll_inv_type_dict:
                if self.__epoll_inv_type_dict[handle] != ht:
                    self.unregister(handle)
                    self._register(handle, ht)
            else:
                self._register(handle, ht)
        self.unlock()
    def _register(self, fd, pt):
        self.__epoll_object.register(fd, pt)
        self.__epoll_type_dict.setdefault(pt, []).append(fd)
        self.__epoll_inv_type_dict[fd] = pt
        epoll_object.log(self, "registering fd %d to type %d (%s)" % (fd, pt, poll_flag_to_str(pt)))
    def poll(self, timeout):
        while True:
            try:
                p_res = self.__epoll_object.poll(timeout / 1000.)
            except select.error, (err_num, err_str):
                # catch select error
                epoll_object.log(self, "select.error (%d): %s" % (err_num, err_str), logging_tools.LOG_LEVEL_ERROR)
            else:
                break
        return p_res
        
class uds_con_object(socket.socket):
    def __init__(self, udomain_send_call, **args):
        self.__server = None
        socket.socket.__init__(self, socket.AF_UNIX, socket.SOCK_DGRAM)
        self.setblocking(0)
        self.__target_name = args["socket"]
        self.__timeout = args.get("timeout", None)
        # default of bind_state is ok
        self.__bind_retries_sv, self.__bind_ok, self.__rebind_wait_time = (args.get("bind_retries", 5),
                                                                           True,
                                                                           args.get("rebind_wait_time", 5))
        self.__send_error_timeout = args.get("send_error_timeout", 100)
        self.__connect_state_call = args.get("connect_state_call", self._dummy_connect_state_call)
        self.__report_problem_call = args.get("report_problem_call", self._dummy_report_problem_call)
        self.__unix_domain_send_call = udomain_send_call
        self.__buffer = None
        self.set_init_time()
    def _dummy_report_problem_call(self, flags, what):
        print "*** _dummy_report_problem_call ***", flags, what
    def _dummy_connect_state_call(self, **args):
        print args
    def get_server(self):
        return self.__server
    def register(self, server, act_poll_object):
        self.__server = server
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        self.__poll_object = act_poll_object
        self.__poll_object.register_handle(self.fileno(), POLL_OUT)
        self._step = self._open
    def try_to_reopen(self, server):
        if not self.__server:
            # add to server if necessary
            server.add_object(self, True)
        self.set_init_time()
        self.__poll_object.register_handle(self.fileno(), POLL_OUT)
        self._step = self._open
    def unregister(self):
        self.__poll_object.poll_unregister(self.fileno())
        self.__poll_object = None
        self.__server = None
        #print "Uds server clear"
    def delete(self):
        # to be called before del
        self.__connect_state_call = None
        self.__unix_domain_send_call = None
        self.__report_problem_call = None
        self.__target_name = None
        # remove self-reference
        self._step = None
        #print "-"*40
        #print "\n".join(["%-40s %-100s: %d" % (z, str(x), sys.getrefcount(x)) for x, z in [(getattr(self, y), y) for y in dir(self)]])
        #print "-"*40
    def __del__(self):
        if SHOW_DEL:
            print "*del uds_con_object"
        socket.socket.close(self)
    def check_for_timeout(self, act_time, set_activity=False):
        if not self.__bind_ok:
            diff_msec = self.__rebind_wait_time - abs(act_time - self.__bind_error)
            if diff_msec < 2:
                self.__poll_object.register_handle(self.fileno(), POLL_OUT)
            else:
                return 1000 * abs(diff_msec)
        else:
            idle_time = act_time - self.__last_activity
            if set_activity:
                self.__last_activity = act_time
            if idle_time >= self.__timeout:
                if self.__buffer:
                    self.__buffer.report_problem(NET_TIMEOUT, "timeout")
                else:
                    self.__report_problem_call(NET_TIMEOUT, "timeout")
                return 0
            else:
                self.__poll_object.register_handle(self.fileno(), POLL_OUT)
                return min(1000 * (self.__timeout - idle_time), self.__send_error_timeout)
    def set_init_time(self):
        # initialisation time
        self.__init_time = time.time()
        self.__last_activity = self.__init_time
        self.__bind_retries = self.__bind_retries_sv
    def ready_to_send(self):
        # called from buffer
        self.__poll_object.register_handle(self.fileno(), POLL_OUT)
        self.__server.trigger()
    def send_done(self):
        # called from buffer
        self.__poll_object.unregister(self.fileno())
    def close(self):
        # called from buffer
        if self.__server:
            self.__server.remove_object(self, True)
        self.unlink_buffer()
    def link_buffer(self, buff_obj):
        # called from server
        self.__buffer = buff_obj
        self.__buffer.link_socket(self)
    def unlink_buffer(self):
        # called from self (self.close())
        if self.__buffer:
            self.__buffer.unlink_socket()
            del self.__buffer
            self.__buffer = None
    def __call__(self, what):
        return self._step(what)
    def _open(self, dummy_arg):
        try:
            self.connect(self.__target_name)
        except socket.error, val:
            self.__bind_ok = False
            self.__poll_object.poll_unregister(self.fileno())
            self.__bind_error = time.time()
            if self.__bind_retries:
                self.__connect_state_call(state="warn", log_level=logging_tools.LOG_LEVEL_WARN, socket=self.__target_name, type="uds")
                self.__bind_retries -= 1
            else:
                self.__connect_state_call(state="error", log_level=logging_tools.LOG_LEVEL_ERROR, socket=self.__target_name, type="uds")
                self.close()
            return 1000 * self.__rebind_wait_time
        else:
            self.__bind_ok = True
            self.__connect_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, socket=self.__target_name, type="uds") 
            self._step = self._send
            new_buffer = self.__unix_domain_send_call(self)
            self.link_buffer(new_buffer)
            new_buffer.setup_done()
            return None
    def _send(self, what):
        # report structure
        rep_struct = self.__buffer or self
        if self.check_for_timeout(time.time()):
            try:
                diff_send = self.send(self.__buffer.get_out_buffer()[:8192])
            except socket.error, val:
                try:
                    errno, what = val
                except:
                    errno, what = (0, str(val))
                if errno == 11:
                    self.__poll_object.poll_unregister(self.fileno())
                    return self.__send_error_timeout
                elif errno == 90:
                    self.__poll_object.poll_unregister(self.fileno())
                    rep_struct.report_problem(NET_MESSAGE_TOO_LONG, "message to long")
                elif errno == 111:
                    self.__poll_object.poll_unregister(self.fileno())
                    rep_struct.report_problem(NET_CONNECTION_REFUSED, "connection refused")
                elif errno == 107:
                    self.__poll_object.poll_unregister(self.fileno())
                    rep_struct.report_problem(NET_NOT_CONNECTED, "not connected")
            else:
                # timeout buffer
                self.check_for_timeout(time.time(), True)
                if self.__buffer:
                    self.__buffer.out_buffer_sent(diff_send)
            return 1000 * self.__timeout
        else:
            return 0

class udp_con_object(socket.socket):
    def __init__(self, udp_send_call, **args):
        self.__server = None
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_DGRAM)
        self.setblocking(0)
        self.__target_host, self.__target_port = (args["target_host"],
                                                  args["target_port"])
        self.__timeout = args.get("timeout", None)
        # default of bind_state is ok
        self.__bind_retries_sv, self.__bind_ok, self.__rebind_wait_time = (args.get("bind_retries", 5),
                                                                           True,
                                                                           args.get("rebind_wait_time", 5))
        self.__send_error_timeout = args.get("send_error_timeout", 100)
        self.__connect_state_call = args.get("connect_state_call", self._dummy_connect_state_call)
        self.__add_data = args.get("add_data", None)
        self.__udp_send_call = udp_send_call
        self.__buffer = None
        self.set_init_time()
    def get_add_data(self):
        return self.__add_data
    def get_target_host(self):
        return self.__target_host
    def get_target_port(self):
        return self.__target_port
    def _dummy_connect_state_call(self, **args):
        print args
    def get_server(self):
        return self.__server
    def register(self, server):
        self.__server = server
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        self.__server.register(self.fileno(), POLL_OUT)
        self._step = self._open
    def try_to_reopen(self, server):
        if not self.__server:
            # add to server if necessary
            server.add_object(self, True)
        self.set_init_time()
        self.__server.register(self.fileno(), POLL_OUT)
        self._step = self._open
    def unregister(self):
        self.__server.unregister(self.fileno())
        self.__server = None
        #print "Uds server clear"
    def delete(self):
        # to be called before del
        self.__connect_state_call = None
        self.__udp_send_call = None
        self.__target_name = None
        # remove self-reference
        self._step = None
        #print "-"*40
        #print "\n".join(["%-40s %-100s: %d" % (z, str(x), sys.getrefcount(x)) for x, z in [(getattr(self, y), y) for y in dir(self)]])
        #print "-"*40
    def __del__(self):
        if SHOW_DEL:
            print "*del uds_con_object"
        socket.socket.close(self)
    def check_for_timeout(self, act_time, set_activity=False):
        if not self.__bind_ok:
            diff_msec = self.__rebind_wait_time - abs(act_time - self.__bind_error)
            if diff_msec < 2:
                self.__server.register(self.fileno(), POLL_OUT)
            else:
                return 1000 * abs(diff_msec)
        else:
            idle_time = act_time - self.__last_activity
            if set_activity:
                self.__last_activity = act_time
            if idle_time >= self.__timeout:
                if self.__buffer:
                    self.__buffer.report_problem(NET_TIMEOUT, "timeout")
                return 0
            else:
                return min(1000 * (self.__timeout - idle_time), self.__send_error_timeout)
    def set_init_time(self):
        # initialisation time
        self.__init_time = time.time()
        self.__last_activity = self.__init_time
        self.__bind_retries = self.__bind_retries_sv
    def ready_to_send(self):
        # called from buffer
        self.__server.register(self.fileno(), POLL_OUT)
        self.__server.trigger()
    def send_done(self):
        # called from buffer
        self.__server.register(self.fileno(), POLL_IN)
    def close(self):
        # called from buffer
        if self.__server:
            self.__server.remove_object(self, True)
        self.unlink_buffer()
    def link_buffer(self, buff_obj):
        # called from server
        self.__buffer = buff_obj
        self.__buffer.link_socket(self)
    def unlink_buffer(self):
        # called from self (self.close())
        if self.__buffer:
            self.__buffer.unlink_socket()
            del self.__buffer
            self.__buffer = None
    def __call__(self, what):
        return self._step(what)
    def _open(self, dummy_arg):
        try:
            self.connect((self.__target_host, self.__target_port))
        except socket.error, val:
            self.__bind_ok = False
            self.__server.unregister(self.fileno())
            self.__bind_error = time.time()
            if self.__bind_retries:
                self.__connect_state_call(state="warn", log_level=logging_tools.LOG_LEVEL_WARN, host=self.__target_host, port=self.__target_port, type="udp", socket=self)
                self.__bind_retries -= 1
            else:
                self.__connect_state_call(state="error", log_level=logging_tools.LOG_LEVEL_ERROR, host=self.__target_host, port=self.__target_port, type="udp", socket=self)
                self.close()
            return 1000 * self.__rebind_wait_time
        else:
            self.__bind_ok = True
            self.__connect_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, host=self.__target_host, port=self.__target_port, type="udp", socket=self) 
            self._step = self._send
            new_buffer = self.__udp_send_call(self)
            self.link_buffer(new_buffer)
            new_buffer.setup_done()
            return None
    def _send(self, what):
        if self.check_for_timeout(time.time(), True):
            if self.__buffer:
                try:
                    diff_send = self.send(self.__buffer.get_out_buffer())
                except socket.error, val:
                    #print "*", val
                    try:
                        errno, what = val
                    except:
                        errno, what = (0, str(val))
                    if errno == 11:
                        self.__server.unregister(self.fileno())
                        return self.__send_error_timeout
                    elif errno == 111:
                        self.__server.unregister(self.fileno())
                        self.__buffer.report_problem(NET_CONNECTION_REFUSED, "connection_refused")
                    elif errno == 107:
                        self.__server.unregister(self.fileno())
                        self.__buffer.report_problem(NET_NOT_CONNECTED, "not_connected")
                else:
                    self.__buffer.out_buffer_sent(diff_send)
            return 1000 * self.__timeout
        else:
            return 0

class tcp_con_object(socket.socket):
    def __init__(self, tcp_send_call, **args):
        self.__server = None
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.setblocking(0)
        self.__target_name, self.__target_port = (args["target_host"], args["target_port"])
        self.__timeout = args.get("timeout", None)
        # default of bind_state is ok
        self.__bind_retries, self.__bind_ok, self.__rebind_wait_time = (args.get("bind_retries", 5),
                                                                        True,
                                                                        args.get("rebind_wait_time", 5))
        self.__add_data = args.get("add_data", None)
        self.__send_error_timeout = args.get("send_error_timeout", 100)
        self.__connect_state_call = args.get("connect_state_call", self._dummy_connect_state_call)
        self.__timeout_call = args.get("connect_timeout_call", self._dummy_connect_timeout_call)
        self.__tcp_send_call = tcp_send_call
        self.__buffer = None
        self.set_init_time()
        self.set_in_buffer_size()
        # init empty_read count
        self.__num_empty_reads = 0
    def get_add_data(self):
        return self.__add_data
    def get_target_host(self):
        return self.__target_name
    def get_target_port(self):
        return self.__target_port
    def _dummy_connect_state_call(self, **args):
        print args
    def _dummy_connect_timeout_call(self, sock):
        print "timeout"
    def delete(self):
        # to be called before del
        self.__connect_state_call = None
        self.__timeout_call = None
        self.__tcp_send_call = None
        # remove self-reference
        self._step = None
    def set_in_buffer_size(self, sz=4096):
        # maximum size of one read
        self.__ib_size = sz
    def register(self, server):#, act_poll_object):
        self.__server = server
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        self.__server.register(self.fileno(), POLL_OUT | POLL_IN)
        self._step = self._open
    def unregister(self):
        self.__server.unregister(self.fileno())
        self.server = None
        try:
            socket.socket.shutdown(2)
        except:
            pass
        socket.socket.close(self)
    def check_for_timeout(self, act_time, set_activity=False):
        if not self.__bind_ok:
            diff_msec = self.__rebind_wait_time - abs(act_time - self.__bind_error)
            if diff_msec < 2:
                self.__server.register(self.fileno(), POLL_OUT | POLL_IN)
            else:
                return 1000 * abs(diff_msec)
        else:
            idle_time = act_time - self.__last_activity
            if set_activity:
                self.__last_activity = act_time
            if idle_time >= self.__timeout:
                if self.__buffer:
                    self.__buffer.report_problem(NET_TIMEOUT, "timeout")
                else:
                    self.__timeout_call(self)
                return 0
            else:
                #self.__poll_object.register_handle(self.fileno(), POLL_IN | POLL_OUT)
                return min(1000 * (self.__timeout - idle_time), self.__send_error_timeout)
    def set_init_time(self):
        # initialisation time
        self.__init_time = time.time()
        self.__last_activity = self.__init_time
    def ready_to_send(self):
        # called from buffer
        self.__server.register(self.fileno(), POLL_OUT | POLL_IN)
        self.__server.trigger()
    def send_done(self):
        # called from buffer
        self.__server.register(self.fileno(), POLL_IN)
    def close(self):
        # called from buffer
        #print "close", self.fileno()
        self.__server.remove_object(self, True)
        self.unlink_buffer()
    def link_buffer(self, buff_obj):
        # called from server
        self.__buffer = buff_obj
        self.__buffer.link_socket(self)
    def unlink_buffer(self):
        # called from self (self.close())
        if self.__buffer:
            self.__buffer.unlink_socket()
            del self.__buffer
            self.__buffer = None
    def __call__(self, what):
        return self._step(what)
    def _open(self, dummy_arg):
        try:
            self.connect((self.__target_name, self.__target_port))
        except socket.error, val:
            try:
                errno, what = val
            except:
                errno, what = (0, str(val))
            if errno == 115:
                return None
            else:
                self.__bind_ok = False
                self.__server.unregister(self.fileno())
                self.__bind_error = time.time()
                if self.__bind_retries:
                    self.__connect_state_call(state="warn", log_level=logging_tools.LOG_LEVEL_WARN, host=self.__target_name, port=self.__target_port, type="tcp", socket=self)
                    self.__bind_retries -= 1
                else:
                    self.__connect_state_call(state="error", log_level=logging_tools.LOG_LEVEL_ERROR, host=self.__target_name, port=self.__target_port, type="tcp", socket=self)
                    self.close()
                return 1000 * self.__rebind_wait_time
        else:
            self.__bind_ok = True
            self.__connect_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, host=self.__target_name, port=self.__target_port, type="tcp", socket=self) 
            self._step = self._send
            new_buffer = self.__tcp_send_call(self)
            self.link_buffer(new_buffer)
            new_buffer.setup_done()
            return None
    def _send(self, p_type):
        if self.check_for_timeout(time.time(), True):
            if p_type & POLL_ERR:
                self.__buffer.report_problem(NET_POLL_ERROR, poll_flag_to_str(p_type))
            elif p_type & POLL_IN:
                try:
                    diff_read = self.recv(self.__ib_size)
                except socket.error, val:
                    try:
                        errno, what = val
                    except:
                        errno, what = (0, str(val))
                    if errno == 11:
                        self.__is_active = False
                else:
                    if diff_read:
                        self.__num_empty_reads = 0
                        self.__buffer.add_to_in_buffer(diff_read)
                    else:
                        self.__num_empty_reads += 1
                        if self.__num_empty_reads > 5 and self.__buffer:
                            self.__buffer.report_problem(NET_EMPTY_READ, "empty_read")
            elif p_type & POLL_OUT:
                if self.__buffer:
                    try:
                        diff_send = self.send(self.__buffer.get_out_buffer())
                    except socket.error, val:
                        try:
                            errno, what = val
                        except:
                            errno, what = (0, str(val))
                        if errno == 11:
                            self.__server.unregister(self.fileno())
                            return self.__send_error_timeout
                        elif errno == 111:
                            self.__server.unregister(self.fileno())
                            self.__buffer.report_problem(NET_CONNECTION_REFUSED, "connection_refused")
                        elif errno == 107:
                            self.__server.unregister(self.fileno())
                            self.__buffer.report_problem(NET_NOT_CONNECTED, "not_connected")
                    else:
                        if diff_send:
                            self.__buffer.out_buffer_sent(diff_send)
                        else:
                            self.__buffer.report_problem(NET_EMPTY_SEND, "empty_send")
            else:
                print "receive", p_type
            return 1000 * self.__timeout
        else:
            return 0
    
class com_socket(object):
    def __init__(self, sock, **args):
        #print "Init com_socket"
        self.__socket = sock
        self.__socket.setblocking(0)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__buffer = None
        self.__server, self.__log_buffer = (None, [])
        self.set_in_buffer_size(args.get("in_buffer_size", 4096))
        self.set_init_time()
        self.set_timeout(args.get("timeout", 5))
        # init empty_read count
        self.__num_empty_reads = 0
    def get_sock_name(self):
        return self.__socket.getsockname()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__server:
            if self.__log_buffer:
                for what, level in self.__log_buffer:
                    self.__server.log(what, level)
                self.__log_buffer = None
            self.__server.log(what, level)
        else:
            self.__log_buffer.append((what, level))
    def set_timeout(self, to=5):
        self.__timeout = to
    def set_in_buffer_size(self, sz=4096):
        # maximum size of one read
        self.__ib_size = sz
    def set_init_time(self):
        # initialisation time
        self.__init_time = time.time()
        self.__last_activity = self.__init_time
    def __del__(self):
        if SHOW_DEL:
            print "deleting com_socket"
    def link_buffer(self, buff_obj):
        # called from server
        self.__buffer = buff_obj
        self.__buffer.link_socket(self)
    def unlink_buffer(self):
        # called from self (self.close())
        if self.__buffer:
            self.__buffer.unlink_socket()
            del self.__buffer
    def fileno(self):
        return self.__socket.fileno()
    def register(self, server):
        # called from server
        self.__server = server
        self.__server.register(self.fileno(), POLL_IN)
    def unregister(self):
        # called from server (in self.close() remove_object call)
        self.__server.unregister(self.fileno())
        self.__server = None
        try:
            self.__socket.shutdown(2)
        except:
            pass
        self.__socket.close()
        self.__socket = None
    def ready_to_send(self):
        # called from buffer
        self.__server.register(self.fileno(), POLL_IN | POLL_OUT)
        self.__server.trigger()
    def send_done(self):
        # called from buffer
        self.__server.register(self.fileno(), POLL_IN)
        self.__server.trigger()
    def close(self):
        # called from buffer
        #print "close", self.fileno()
        self.__server.remove_object(self, True)
        self.unlink_buffer()
    def check_for_timeout(self, act_time, set_activity=False):
        # timeout handling: call check_for_timeout in every loop of the netserver (either
        # directly via a poll-interrupt or after the main loop to check)
        # returns 0 for timeout reached or time left in milliseconds
        idle_time = act_time - self.__last_activity
        #print "CFT", idle_time, self.__timeout
        if set_activity:
            self.__last_activity = act_time
        if idle_time >= self.__timeout:
            self.__buffer.report_problem(NET_TIMEOUT, "timeout")
            return 0
        else:
            return 1000 * (self.__timeout - idle_time)
    def __call__(self, p_type):
        # returns max time until next call or 0 (for timeout occured) or None (for infinite timeout)
        if self.check_for_timeout(time.time(), True):
            if p_type & POLL_IN:
                try:
                    diff_read = self.__socket.recv(self.__ib_size)
                except socket.error, val:
                    try:
                        errno, what = val
                    except:
                        errno, what = (0, str(val))
                    if errno == 11:
                        self.__is_active = False
                else:
                    if diff_read:
                        self.__num_empty_reads = 0
                        self.__buffer.add_to_in_buffer(diff_read)
                    else:
                        self.__num_empty_reads += 1
                        if self.__num_empty_reads > 5:
                            self.__buffer.report_problem(NET_EMPTY_READ, "empty_read")
            elif p_type & POLL_OUT:
                if self.__buffer:
                    try:
                        diff_send = self.__socket.send(self.__buffer.get_out_buffer())
                    except socket.error, val:
                        try:
                            errno, what = val
                        except:
                            errno, what = (0, str(val))
                    else:
                        self.__buffer.out_buffer_sent(diff_send)
            else:
                print "receive", p_type
            return 1000 * self.__timeout
        else:
            return 0
        
class tcp_bind(socket.socket):
    def __init__(self, new_buffer_object_call, **args):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.setblocking(0)
        # log_buffer if __net_server is not set
        self.__log_buffer = []
        # net_server
        self.__server = None
        self.__if_list = args.get("interface_list", [])
        self.__port = args["port"]
        # default of bind_state is ok
        self.__bind_retries, self.__bind_ok, self.__rebind_wait_time = (args.get("bind_retries", 5),
                                                                        True,
                                                                        args.get("rebind_wait_time", 5))
        # buffer object
        self.__new_buffer_object_call = new_buffer_object_call
        self.log("init %s" % (self.info_str()))
        self.__bind_state_call = args.get("bind_state_call", self._dummy_bind_state_call)
        self.__timeout = args.get("timeout", None)
        self.__in_buffer_size = args.get("in_buffer_size", 4096)
    def info_str(self):
        return "tcp_bind to port %d" % (self.__port)
    def __del__(self):
        if SHOW_DEL:
            print "*del tcp_bind %d" % (sys.getrefcount(self))
    def close(self):
        self.__server.remove_object(self)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__server:
            self.__log_buffer.append((what, level))
            for what, level in self.__log_buffer:
                self.__server.log(what, level)
            self.__log_buffer = []
        else:
            self.__log_buffer.append(("(delayed) %s" % (what), level))
    def register(self, server):#, act_poll_object):
        self.__server = server
        # overide if timeout was not set
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        #self.__poll_object = act_poll_object
        self._step = self._bind_port
        self.__server.register(self.fileno(), POLL_IN)
        self.log("registered %s" % (self.info_str()))
    def unregister(self):
        self.__server.unregister(self.fileno())
        self._step = None
    def _dummy_bind_state_call(self, **args):
        self.log("tcp_bind: state_call, %s: %s" % (logging_tools.get_plural("key", len(args.keys())),
                                                   ", ".join(["%s=%s" % (k, str(v)) for k, v in args.iteritems()])),
                 args.get("log_level", logging_tools.LOG_LEVEL_WARN))
    def _bind_port(self):
        try:
            self.bind((self.__if_list and self.__if_list[0] or "", self.__port))
        except socket.error, val:
            self.__bind_ok = False
            self.__server.unregister(self.fileno())
            self.__bind_error = time.time()
            if self.__bind_retries:
                self.__bind_state_call(state="warn", log_level=logging_tools.LOG_LEVEL_WARN, port=self.__port, type="tcp")
                self.__bind_retries -= 1
            else:
                self.__bind_state_call(state="error", log_level=logging_tools.LOG_LEVEL_ERROR,  port=self.__port, type="tcp")
                self.close()
            return 1000 * self.__rebind_wait_time
        else:
            self.__bind_ok = True
            self.__bind_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, port=self.__port, type="tcp") 
            try:
                self.listen(5)
            except socket.error, val:
                print "err", val
            else:
                self._step = self._accept
            return None
    def _accept(self):
        try:
            sock, source = self.accept()
        except socket.error, val:
            try:
                errno, what = val
            except:
                errno, what = (0, str(val))
            if errno == 11:
                print "err", what, errno
        else:
            sock = com_socket(sock, timeout=self.__timeout, in_buffer_size=self.__in_buffer_size)
            new_buffer = self.__new_buffer_object_call(sock, source)
            sock.link_buffer(new_buffer)
            self.__server.add_object(sock)
    def __call__(self, what):
        return self._step()
    def check_for_timeout(self, act_time):
        if not self.__bind_ok:
            diff_msec = self.__rebind_wait_time - abs(act_time - self.__bind_error)
            if diff_msec < 2:
                self.__server.register(self.fileno(), POLL_IN)
            else:
                return 1000 * abs(diff_msec)

class udp_bind(socket.socket):
    def __init__(self, udp_receive_call, **args):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_DGRAM)
        #self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.setblocking(0)
        # log_buffer if __net_server is not set
        self.__log_buffer = []
        # net_server
        self.__server = None
        self.__if_list = args.get("interface_list", [])
        self.__port = args["port"]
        # default of bind_state is ok
        self.__bind_retries, self.__bind_ok, self.__rebind_wait_time = (args.get("bind_retries", 5),
                                                                        True,
                                                                        args.get("rebind_wait_time", 5))
        # buffer object
        self.__udp_receive_call = udp_receive_call
        self.log("init %s" % (self.info_str()))
        self.__bind_state_call = args.get("bind_state_call", self._dummy_bind_state_call)
        self.__timeout = args.get("timeout", None)
    def info_str(self):
        return "udp_bind to port %d" % (self.__port)
    def __del__(self):
        if SHOW_DEL:
            print "*del udp_bind"
    def close(self):
        self.__server.remove_object(self)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__server:
            self.__log_buffer.append((what, level))
            for what, level in self.__log_buffer:
                self.__server.log(what, level)
            self.__log_buffer = []
        else:
            self.__log_buffer.append(("(delayed) %s" % (what), level))
    def register(self, server):#, act_poll_object):
        self.__server = server
        # overide if timeout was not set
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        #self.__poll_object = act_poll_object
        self._step = self._bind_port
        self.__server.register(self.fileno(), POLL_OUT)
        self.log("registered %s" % (self.info_str()))
    def unregister(self):
        self.__server.unregister(self.fileno())
        self._step = None
    def _dummy_bind_state_call(self, **args):
        self.log("tcp_bind: state_call, %s: %s" % (logging_tools.get_plural("key", len(args.keys())),
                                                   ", ".join(["%s=%s" % (k, str(v)) for k, v in args.iteritems()])),
                 args.get("log_level", logging_tools.LOG_LEVEL_WARN))
    def _bind_port(self):
        try:
            self.bind((self.__if_list and self.__if_list[0] or "", self.__port))
        except socket.error, val:
            self.__bind_ok = False
            self.__server.unregister(self.fileno())
            self.__bind_error = time.time()
            if self.__bind_retries:
                self.__bind_state_call(state="warn", log_level=logging_tools.LOG_LEVEL_WARN, port=self.__port, type="udp")
                self.__bind_retries -= 1
            else:
                self.__bind_state_call(state="error", log_level=logging_tools.LOG_LEVEL_ERROR,  port=self.__port, type="udp")
                self.close()
            return 1000 * self.__rebind_wait_time
        else:
            self.__server.register(self.fileno(), POLL_IN)
            self.__bind_ok = True
            self.__bind_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, port=self.__port, type="udp") 
            self._step = self._recvfrom
            return None
    def _recvfrom(self):
        try:
            d_read, frm = self.recvfrom(65535)
        except:
            self.log("error in self.recvfrom(): %s" % (get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.__udp_receive_call(d_read, frm)
    def __call__(self, what):
        return self._step()
    def check_for_timeout(self, act_time):
        if not self.__bind_ok:
            diff_msec = self.__rebind_wait_time - abs(act_time - self.__bind_error)
            if diff_msec < 2:
                self.__server.register(self.fileno(), POLL_OUT)
            else:
                return 1000 * abs(diff_msec)

class unix_domain_bind(socket.socket):
    def __init__(self, udomain_receive_call, **args):
        socket.socket.__init__(self, socket.AF_UNIX, socket.SOCK_DGRAM)
        #self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.setblocking(0)
        # log_buffer if __net_server is not set
        self.__log_buffer = []
        # net_server
        self.__server = None
        self.__socket, self.__mode = (args["socket"], args["mode"])
        # default of bind_state is ok
        self.__bind_retries, self.__bind_ok, self.__rebind_wait_time = (args.get("bind_retries", 5),
                                                                        True,
                                                                        args.get("rebind_wait_time", 5))
        # buffer object
        self.__unix_domain_receive_call = udomain_receive_call
        self.log("init %s" % (self.info_str()))
        self.__bind_state_call = args.get("bind_state_call", self._dummy_bind_state_call)
        self.__timeout = args.get("timeout", None)
    def info_str(self):
        return "unix_domain_bind to %s (mode %o)" % (self.__socket, self.__mode)
    def __del__(self):
        self.shutdown(2)
        if SHOW_DEL:
            print "*** del unix_domain_bind: %d" % (self.fileno())
        socket.socket.close(self)
        try:
            os.unlink(self.__socket)
        except:
            print "__del__ of unix_domain_bind: %s" % (get_except_info())
            pass
    def close(self):
        if self.__server:
            self.__server.remove_object(self)
        # clear references
        self.__unix_domain_receive_call = None
        self.__bind_state_call = None
        self._step = None
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__server:
            self.__log_buffer.append((what, level))
            for what, level in self.__log_buffer:
                self.__server.log(what, level)
            self.__log_buffer = []
        else:
            self.__log_buffer.append(("(delayed) %s" % (what), level))
    def register(self, server):#, act_poll_object):
        self.__server = server
        # overide if timeout was not set
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        #self.__poll_object = act_poll_object
        self._step = self._bind_port
        self.__server.register(self.fileno(), POLL_OUT)
        self.log("registered %s" % (self.info_str()))
    def unregister(self):
        self.__server.unregister(self.fileno())
        self._step = None
    def _dummy_bind_state_call(self, **args):
        self.log("tcp_bind: state_call, %s: %s" % (logging_tools.get_plural("key", len(args.keys())),
                                                   ", ".join(["%s=%s" % (k, str(v)) for k, v in args.iteritems()])),
                 args.get("log_level", logging_tools.LOG_LEVEL_WARN))
    def _bind_port(self):
        try:
            socket_name, socket_mode = (self.__socket, self.__mode)
            #print "_bind_port", socket_name, socket_mode
            try:
                os.unlink(socket_name)
            except:
                # FIXME
                pass
            self.bind(socket_name)
            os.chmod(socket_name, socket_mode)
        except socket.error, val:
            self.__bind_ok = False
            self.__server.unregister(self.fileno())
            self.__bind_error = time.time()
            if self.__bind_retries:
                self.__bind_state_call(state="warn", log_level=logging_tools.LOG_LEVEL_WARN, port=self.__socket, type="unix domain")
                self.__bind_retries -= 1
            else:
                self.__bind_state_call(state="error", log_level=logging_tools.LOG_LEVEL_ERROR,  port=self.__socket, type="unix domain")
                self.close()
            return 1000 * self.__rebind_wait_time
        else:
            self.__server.register(self.fileno(), POLL_IN)
            self.__bind_ok = True
            self.__bind_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, port=self.__socket, type="unix domain") 
            self._step = self._recvfrom
            return None
    def _recvfrom(self):
        try:
            d_read, frm = self.recvfrom(65535)
        except:
            print "UNIX DOMAIN ERROR: %s" % (get_except_info())
        else:
            self.__unix_domain_receive_call(d_read, frm)
    def __call__(self, what):
        return self._step()
    def check_for_timeout(self, act_time):
        if not self.__bind_ok:
            diff_msec = self.__rebind_wait_time - abs(act_time - self.__bind_error)
            if diff_msec < 2:
                self.__server.register(self.fileno(), POLL_OUT)
            else:
                return 1000 * abs(diff_msec)

class icmp_bind(socket.socket):
    def __init__(self, **args):
        self.__socket_ok = False
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        self.setblocking(0)
        self.__socket_ok = True
        # log_buffer if __net_server is not set
        self.__log_buffer = []
        # net_server
        self.__server = None
        ## poll object
        #self.__poll_object = None
        bind_state_call = args.get("bind_state_call", None)
        if bind_state_call:
            bind_state_call(state="ok", log_level=logging_tools.LOG_LEVEL_OK, type="icmp")
        self.log("init %s" % (self.info_str()))
        self.__icmp_id = os.getpid()
        # reentrant lock for double-locking
        self.__ic_lock = threading.RLock()
        self.__icmp_clients = {}
        self.__packets_to_send = 0
        self.__ic_id, self.__seq = (0, 0)
        self.__send_count, self.__recv_count = (0, 0)
        # timeout for loop
        self.__timeout = args.get("timeout", None)
        # sequence lookup
        self.__seq_lut = {}
        self.__sending, self.__receiving = (False, False)
        # exit when last icmp_clients is remove
        self.__exit_on_finish = args.get("exit_on_finish", False)
        self.__request_exit = False
    def add_icmp_client(self, ic):
        self.__ic_lock.acquire()
        self.__ic_id += 1
        self.__icmp_clients[self.__ic_id] = ic
        ic.link_socket(self, self.__ic_id)
        ic.setup_done()
        self.__ic_lock.release()
        if self.__server:
            self.__server.trigger()
    def remove_icmp_client(self, ic):
        # called from icmp_client
        self.__ic_lock.acquire()
        r_ic = ic.get_client_id()
        del self.__icmp_clients[r_ic]
        ic.remove_socket()
        d_ks = [key for key, value in self.__seq_lut.iteritems() if value == r_ic]
        for d_k in d_ks:
            del self.__seq_lut[d_k]
        if not self.__icmp_clients:
            if self.__server:
                self.__server.unregister(self.fileno())
            if self.__exit_on_finish:
                if self.__server:
                    self.__server.request_exit(True)
                else:
                    self.__request_exit = True
        self.__ic_lock.release()
    def register_packets_to_send(self, ic, num_p):
        #print "registering %d" % (num_p)
        self.__ic_lock.acquire()
        was_sending = self.__packets_to_send and True or False
        self.__packets_to_send += num_p
        if not was_sending and self.__server:
            self.__server.register(self.fileno(), POLL_OUT | POLL_IN)
        self.__ic_lock.release()
    def _get_next_packet(self):
        p_list = []
        self.__ic_lock.acquire()
        # further packets to send ?
        f_t_s = False
        # iterate over all ics and collect packets
        for ic in self.__icmp_clients.values():
            if ic.packets_to_send():
                p_list.extend(ic._get_packet())
                if ic.further_packets_to_send():
                    f_t_s = True
        self.__packets_to_send -= len(p_list)
        if not self.__packets_to_send or not f_t_s:
            self.__server.register(self.fileno(), POLL_IN)
        self.__ic_lock.release()
        return p_list
    def generate_icmp_packet(self, c_id, payload="net_tools ping"):
        s_pkt = icmp.Packet()
        self.__seq = (self.__seq % 32767) + 1
        self.__seq_lut[self.__seq] = c_id
        s_pkt.type, s_pkt.id, s_pkt.seq, s_pkt.data = (icmp.ICMP_ECHO,
                                                       self.__icmp_id,
                                                       self.__seq,
                                                       payload)
        return s_pkt.assemble()
    def info_str(self):
        return "icmp_bind"
    def __del__(self):
        if SHOW_DEL:
            print "*** del icmp_bind: %d" % (self.fileno())
        if self.__socket_ok:
            socket.socket.close(self)
    def close(self):
        if self.__server:
            self.__server.remove_object(self)
        # clear references
        self.__icmp_receive_call = None
        self.__bind_state_call = None
        self._step = None
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__server:
            self.__log_buffer.append((what, level))
            for what, level in self.__log_buffer:
                self.__server.log(what, level)
            self.__log_buffer = []
        else:
            self.__log_buffer.append(("(delayed) %s" % (what), level))
    def register(self, server):#, act_poll_object):
        self.__server = server
        #self.__poll_object = act_poll_object
        # overide if timeout was not set
        if self.__timeout is None:
            self.__timeout = self.__server.get_timeout()
        if self.__request_exit:
            self.__server.request_exit()
        else:
            self.ready_to_send()
            self._step = self._recvsend
            self.log("registered %s" % (self.info_str()))
    def ready_to_send(self):
        if self.__packets_to_send:
            self.__server.register(self.fileno(), POLL_OUT | POLL_IN)
    def unregister(self):
        self.__server.unregister(self.fileno())
        self._step = None
##     def ready_to_recv(self):
##         self.__recv_count += 1
##         if not self.__receiving:
##             if self.__sending:
##                 self.__poll_object.register_handle(self.fileno(), POLL_OUT)
##         self._change_poll()
##     def ready_to_send(self):
##         self.__send_count += 1
##         self._change_poll()
##     def _change_poll(self):
##         # called from buffer
##         self.__server.trigger()
    def _icmp_receive(self, d_read, frm):
        source_host, source_port = frm
        try:
            reply_p = icmp.Packet(ip.Packet(d_read).data)
        except:
            print "*** error _icmp_receive : %s" % (get_except_info())
        else:
            if reply_p.id == self.__icmp_id:
                #print source_host, len(d_read), reply_p.id, self.__icmp_id, reply_p.seq
                seq = reply_p.seq
                if seq in self.__seq_lut:
                    self.__icmp_clients[self.__seq_lut[seq]].reply_received(source_host)
                    # maybe seq was deleted by shutdown sequence of icmp_client
                    if seq in self.__seq_lut:
                        del self.__seq_lut[seq]
    def _recvsend(self, p_type):
        #print "+-" * 20
        if p_type & POLL_IN:
            try:
                d_read, frm = self.recvfrom(65535)
            except:
                print "ICMP ERROR: %s" % (get_except_info())
            else:
                self._icmp_receive(d_read, frm)
        elif p_type & POLL_OUT:
            for pack_dest, pack in self._get_next_packet():
                try:
                    self.sendto(pack, (pack_dest, 0))
                except:
                    pass
        else:
            print "p_type (icmp_recv_send):", p_type
        return self.check_for_timeout(time.time())
    def __call__(self, what):
        return self._step(what)
    def check_for_timeout(self, act_time):
        self.__ic_lock.acquire()
        if self.__icmp_clients:
            rv = min([1000. * self.__timeout] + [v.check_for_timeout(act_time) for v in self.__icmp_clients.values()])
        else:
            rv = 1000. * self.__timeout
        self.__ic_lock.release()
        return rv

class network_server(epoll_object):
    def __init__(self, **args):
        epoll_object.__init__(self,
                              verbose=args.get("poll_verbose", False),
                              log_handle=self.log)
        self.__objects = {}
        # init pipe-objects for adding objects
        self.__pipe_recv, self.__pipe_send = os.pipe()
        self.__pipe_buffer = ""
        # log hook
        self.__log_hook = args.get("log_hook", None)
        # polling object
        #self.__poll_object = poll_object(poll_verbose=args.get("poll_verbose", False),
        #                                 log_handle = self.log)
        # exit when no objects present ?
        self.__exit_when_empty = args.get("exit_when_empty", False)
        # register receiving pipe
        #self.__poll_object.poll_register(self.__pipe_recv, POLL_IN)
        self.register(self.__pipe_recv, POLL_IN)
        # add (requeue) lock
        self.__change_lock = threading.RLock()
        # add list, del_list
        self.__add_list, self.__del_list = ([], [])
        # clear local wait_times
        self.__local_wait_times = []
        self.set_timeout(args.get("timeout", 30))
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__log_hook:
            self.__log_hook(what, level)
        else:
            print "NServ (%d): %s" % (level, what)
    def set_timeout(self, to):
        if type(to) == type(0):
            self.log("setting timeout of network_server to %s" % (logging_tools.get_plural("second", to)))
        else:
            self.log("setting timeout of network_server to %.4f seconds" % (to))
        self.__timeout = to
        self.__local_wait_times.append(1000 * self.__timeout)
        #self._pipe_send("new_timeout")
    def get_timeout(self):
        return self.__timeout
    def close_objects(self):
        self.__change_lock.acquire()
        self.remove_object(self.__objects.values(), True)
        self.__change_lock.release()
    def add_object(self, obj_list, immediate=False):
        if type(obj_list) != type([]):
            obj_list = [obj_list]
        #self.__objects
        self.__change_lock.acquire()
        self.__add_list.extend([x for x in obj_list])
        self.__change_lock.release()
        self._pipe_send("new_object")
        return obj_list
    def get_num_objects(self):
        return len(self.__objects.keys())
    def remove_object(self, obj_list, immediate=False):
        if type(obj_list) != type([]):
            obj_list = [obj_list]
        if immediate:
            for del_obj in obj_list:
                act_fno = del_obj.fileno()
                del self.__objects[act_fno]
                del_obj.unregister()
                del_obj = None
        else:
            self.__change_lock.acquire()
            self.__del_list.extend([x for x in obj_list])
            self.__change_lock.release()
            self._pipe_send("del_object")
    def _add_object(self):
        self.__change_lock.acquire()
        for add_obj in self.__add_list:
            self.__objects[add_obj.fileno()] = add_obj
            add_obj.register(self)#, self.__poll_object)
        self.__add_list = []
        self.__change_lock.release()
    def _del_object(self):
        del_objs = []
        self.__change_lock.acquire()
        #self.log("list 0: %s" % (["%d" % (x.fileno()) for x in self.__del_list]))
        for del_obj in self.__del_list:
            act_fno = del_obj.fileno()
            #self.log("remove %d" % (act_fno))
            del_objs.append(act_fno)
            del self.__objects[act_fno]
            del_obj.unregister()
        self.__del_list = []
        #self.log("list 1: %s" % (["%d" % (x.fileno()) for x in self.__del_list]))
        self.__change_lock.release()
        return del_objs
    def _pipe_send(self, what):
        os.write(self.__pipe_send, "<%s>" % (what))
    def _pipe_read(self):
        self.__pipe_buffer += os.read(self.__pipe_recv, 32)
        # parse pipe_buffer
        results = []
        while True:
            if self.__pipe_buffer:
                if self.__pipe_buffer[0] != "<":
                    self.log("Error, __pipe_buffer starts with '%s' ('<' needed, buffer is '%s'), stripping" % (self.__pipe_buffer[0],
                                                                                                                self.__pipe_buffer),
                             logging_tools.LOG_LEVEL_CRITICAL)
                    while self.__pipe_buffer and self.__pipe_buffer[0] != "<":
                        self.__pipe_buffer = self.__pipe_buffer[1:]
                else:
                    try:
                        gt_idx = self.__pipe_buffer.index(">")
                    except ValueError:
                        break
                    else:
                        new_com = self.__pipe_buffer[1 : gt_idx]
                        if results and results[-1] == new_com:
                            #print " * _pipe_read * present", new_com
                            pass
                        else:
                            results.append(new_com)
                        self.__pipe_buffer = self.__pipe_buffer[gt_idx + 1 :]
            else:
                break
        return results
    def trigger(self):
        self._pipe_send("wakeup")
    def break_call(self):
        self._pipe_send("break")
    def step(self):
        # maximum run-time
        time_to_consume = 1000 * self.__timeout
        # local_wait_times for first iteration
        local_wait_times = self.__local_wait_times
        # run_flag
        run_flag = True
        # minimum time left is one millisecond (because poll_object.poll() sometimes returns sooner)
        while time_to_consume > 2 and run_flag:
            # start time of step
            start_time = time.time()
            # list of recently removed objects
            del_objs = []
            # timeout
            try:
                next_timeout = min([cur_time for cur_time in local_wait_times if cur_time])
            except ValueError:
                self.log("ValueError in next_timeout calc, %s, %s" % (str(local_wait_times),
                                                                      str(time_to_consume)),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise ValueError
            if next_timeout <= 0:
                self.log("next_timeout < 0 (%.4f), forcing break" % (next_timeout), logging_tools.LOG_LEVEL_ERROR)
                break
            # result of poll
            #poll_result = self.__poll_object.poll(next_timeout)
            poll_result = self.poll(next_timeout)
            # list of wait_times
            local_wait_times = []
            # keys present in poll_result
            polled_keys = [x for x, y in poll_result]
            for key, poll_type in poll_result:
                #self.log("polling %d %d" % (key, poll_type))
                if key == self.__pipe_recv:
                    for command in self._pipe_read():
                        if command == "new_object":
                            self._add_object()
                        elif command == "del_object":
                            del_objs.extend(self._del_object())
                        elif command == "wakeup":
                            pass
                        elif command == "break":
                            run_flag = False
                        elif command == "new_timeout":
                            print time_to_consume, self.__timeout * 1000
                        else:
                            print "Got unknown command '%s' via pipe, exiting ..."  % (command)
                            sys.exit(-1)
                elif key in del_objs:
                    print "do", key, poll_type
                else:
                    #print "key", key, poll_type
                    local_wait_times.append(self.__objects[key](poll_type))
            act_time = time.time()
            for key in [x for x in self.__objects.keys() if x not in polled_keys]:
                local_wait_times.append(self.__objects[key].check_for_timeout(act_time))
            # calculate time to consume
            time_to_consume -= abs(act_time - start_time) * 1000
            if time_to_consume > 0:
                local_wait_times.append(time_to_consume)
            if not self.__objects and self.__exit_when_empty:
                # no objects and exit_when_empty flag set ?
                run_flag = False
        local_wait_times.append(1000 * self.__timeout)
        self.__local_wait_times = local_wait_times
    def __repr__(self):
        return "network server with %s" % (logging_tools.get_plural("object",
                                                                    len(self.__objects.keys())))

class network_send(epoll_object):
    def __init__(self, **args):
        epoll_object.__init__(self,
                              verbose=args.get("poll_verbose", False),
                              log_handle=self.log)
        self.__objects = {}
        # init pipe-objects for adding objects
        self.__pipe_recv, self.__pipe_send = os.pipe()
        self.__pipe_buffer = ""
        # verbosity
        self.__verbose = args.get("verbose", False)
        # log hook
        self.__log_hook = args.get("log_hook", None)
        # polling object
        # register receiving pipe
        self.register(self.__pipe_recv, POLL_IN)
        # add (requeue) lock
        self.__change_lock = threading.RLock()
        # add list, del_list
        self.__add_list, self.__del_list = ([], [])
        # clear local wait_times
        self.__local_wait_times = []
        self.__timeout = None
        self.set_timeout(args.get("timeout", 30))
        self.__exit = False
    def close(self):
        if self.__pipe_recv:
            os.close(self.__pipe_recv)
            os.close(self.__pipe_send)
    def request_exit(self, er=True):
        self.__exit = er
    def exit_requested(self):
        return self.__exit
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__log_hook:
            self.__log_hook(what, level)
        else:
            print "NSend (%d): %s" % (level, what)
    def set_timeout(self, to):
##         if type(to) == type(0):
##             self.log("setting timeout to %s" % (logging_tools.get_plural("second", to)))
##         else:
##             self.log("setting timeout to %.4f seconds" % (to))
        self.__timeout = to
        self.__local_wait_times.append(1000 * self.__timeout)
    def get_timeout(self):
        return self.__timeout
    def close_objects(self):
        self.__change_lock.acquire()
        self.remove_object(self.__objects.values(), True)
        self.__change_lock.release()
    def add_object(self, obj_list, immediate=False):
        if type(obj_list) != type([]):
            obj_list = [obj_list]
        if immediate:
            for add_obj in obj_list:
                self.__objects[add_obj.fileno()] = add_obj
                add_obj.register(self)#, self.__poll_object)
        else:
            self.__change_lock.acquire()
            self.__add_list.extend(obj_list)
            self.__change_lock.release()
            self.trigger()
    def _add_object(self):
        if self.__add_list:
            self.__change_lock.acquire()
            while self.__add_list:
                add_obj = self.__add_list.pop(0)
                self.__objects[add_obj.fileno()] = add_obj
                add_obj.register(self)#, self.__poll_object)
            self.__change_lock.release()
    #def get_registered_handles(self):
    #    return [x for x in self.get_registered_handles() if x not in [self.__pipe_recv]]
    def get_num_objects(self):
        return len(self.__objects.keys())
    def remove_object(self, obj_list, immediate=False):
        if type(obj_list) != type([]):
            obj_list = [obj_list]
        self.__change_lock.acquire()
        self.__del_list.extend(obj_list)
        self.__change_lock.release()
        if immediate:
            self._remove_object()
        else:
            self.trigger()
    def _remove_object(self):
        if self.__del_list:
            self.__change_lock.acquire()
            while self.__del_list:
                del_obj = self.__del_list.pop(0)
                del self.__objects[del_obj.fileno()]
                del_obj.unregister()
            self.__change_lock.release()
    def trigger(self):
        os.write(self.__pipe_send, "*")
    def step(self):
        # maximum run-time
        time_to_consume = 1000 * self.__timeout
        # local_wait_times for first iteration
        local_wait_times = self.__local_wait_times
        # minimum time left is one millisecond (because poll_object.poll() sometimes returns sooner)
        while time_to_consume > 2:
            if self.__verbose:
                self.log("time_to_consume: %d" % (time_to_consume))
            # start time of step
            start_time = time.time()
            # list of recently removed objects
            # timeout
            try:
                next_timeout = min([x for x in local_wait_times if x])
            except ValueError:
                self.log("ValueError in next_timeout calc, %s, %s" % (str(local_wait_times),
                                                                      str(time_to_consume)),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise ValueError
            # result of poll
            poll_result = self.poll(next_timeout)
            # list of wait_times
            local_wait_times = []
            # keys present in poll_result
            polled_keys = set([fd for fd, fd_mask in poll_result])
            for key, poll_type in poll_result:
                if self.__verbose:
                    self.log("polling %d %d" % (key, poll_type))
                if key == self.__pipe_recv:
                    os.read(self.__pipe_recv, 32)
                    self._add_object()
                    self._remove_object()
                else:
                    local_wait_times.append(self.__objects[key](poll_type))
            act_time = time.time()
            for key in set(self.__objects.keys()) - polled_keys:
                local_wait_times.append(self.__objects[key].check_for_timeout(act_time))
            # calculate time to consume
            time_to_consume -= abs(act_time - start_time) * 1000
            if time_to_consume > 0:
                local_wait_times.append(time_to_consume)
            if not self.__objects or self.__exit:
                break
        local_wait_times.append(1000 * self.__timeout)
        self.__local_wait_times = local_wait_times
    def __repr__(self):
        return "network send with %s" % (logging_tools.get_plural("object",
                                                                  len(self.__objects.keys())))

class simple_con_obj(buffer_object):
    # connects to a foreign host-monitor
    def __init__(self, mother_obj, **args):
        # mother_object, has to support the functions set_result and set_error
        self.__mother_obj = mother_obj
        self.__mode = args.get("mode", "tcp")
        self.__send_str = args["command"]
        self.__protocoll = args.get("protocoll", 1)
        self.__idx = args.get("idx", None)
        buffer_object.__init__(self)
    def setup_done(self):
        if self.__protocoll:
            self.add_to_out_buffer(add_proto_1_header(self.__send_str, True))
            self.__send_len = len(self.__send_str) + 8
        else:
            self.add_to_out_buffer(self.__send_str)
            self.__send_len = len(self.__send_str)
    def out_buffer_sent(self, send_len):
        if send_len == self.__send_len:
            self.out_buffer = ""
            self.socket.send_done()
            if self.__mode == "udp":
                if self.__idx is not None:
                    self.__mother_obj.set_result(self.__idx, "ok send")
                else:
                    self.__mother_obj.set_result("ok send")
                self.delete()
        else:
            self.out_buffer = self.out_buffer[send_len:]
            self.__send_len -= send_len
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        if self.__protocoll:
            p1_ok, p1_data = check_for_proto_1_header(self.in_buffer)
        else:
            p1_ok, p1_data = (True, self.in_buffer)
        if p1_ok:
            if self.__idx is not None:
                self.__mother_obj.set_result(self.__idx, p1_data)
            else:
                self.__mother_obj.set_result(p1_data)
            self.delete()
    def report_problem(self, flag, what):
        if self.__idx is not None:
            self.__mother_obj.set_error(self.__idx, flag, what)
        else:
            self.__mother_obj.set_error(flag, what)
        self.delete()

class single_connection(network_send):
    def __init__(self, **args):
        network_send.__init__(self, verbose=args.get("verbose", False), log_hook=args.get("log_hook", None), timeout=args.get("timeout", 30))
        self.__mode = args.get("mode", "tcp")
        self.__host, self.__port = (args["host"],
                                    args["port"])
        if self.__mode == "tcp":
            self.add_object(tcp_con_object(self._new_tcp_con, connect_state_call=self._connect_state_call, connect_timeout_call=self._connect_timeout, target_host=self.__host, target_port=self.__port, bind_retries=args.get("bind_retries", 1), rebind_wait_time=args.get("rebind_wait_time", 2)))
        else:
            self.add_object(udp_con_object(self._new_tcp_con, connect_state_call=self._connect_state_call, connect_timeout_call=self._connect_timeout, target_host=self.__host, target_port=self.__port, bind_retries=args.get("bind_retries", 1), rebind_wait_time=args.get("rebind_wait_time", 2)))
        self.__protocoll = args.get("protocoll", 1)
        self.__command = args["command"]
        self.__errnum, self.__ret_str = (0, "not set")
    def iterate(self):
        self.step()
        while not self.exit_requested() and self.get_num_objects():
            self.step()
        return self.__errnum, self.__ret_str
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        print "what, level", what, level
    def _connect_timeout(self, sock):
        self.set_error(0, NET_TIMEOUT, "connect timeout")
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.set_error(0, NET_CONNECTION_REFUSED, "Error cannot connect")
    def _new_tcp_con(self, sock):
        return simple_con_obj(self, **{"idx"       : 0,
                                       "host"      : self.__host,
                                       "port"      : self.__port,
                                       "mode"      : self.__mode,
                                       "command"   : self.__command,
                                       "protocoll" : self.__protocoll})
    def set_result(self, idx, data):
        self.__ret_str = data
    def set_error(self, idx, errnum, data):
        self.__errnum, self.__ret_str = (errnum, data)

class multiple_connections(network_send):
    def __init__(self, **args):
        network_send.__init__(self, verbose=args.get("verbose", False), log_hook=args.get("log_hook", None), timeout=args.get("timeout", 30))
        self.__log_hook = args.get("log_hook", None)
        self.__save_logs = args.get("save_logs", False)
        args_keys = ["verbose", "log_hook", "timeout",
                     "target_dict", "bind_retries", "rebind_wait_time",
                     "protocoll", "save_logs", "target_list"]
        self.__log_storage = []
        act_args_keys = args.keys()
        unknown_args = [x for x in act_args_keys if x not in args_keys]
        if unknown_args:
            print "%s (%s) for net_tools.multiple_connection()" % (logging_tools.get_plural("unknown argument", len(unknown_args)),
                                                                   ", ".join(sorted(unknown_args)))
        # build target dict
        self.__target_dict = {}
        for idx, t_stuff in zip(range(len(args["target_list"])),
                                args["target_list"]):
            self.__target_dict[idx] = {"host"      : t_stuff["host"],
                                       "port"      : t_stuff["port"],
                                       "command"   : t_stuff["command"],
                                       "errnum"    : 0,
                                       "timeout"   : t_stuff.get("timeout", args.get("timeout", 30)),
                                       "protocoll" : t_stuff.get("protocoll", args.get("protocoll", 1)),
                                       "mode"      : t_stuff.get("mode", args.get("mode", "tcp")),
                                       "ret_str"   : "not set",
                                       "idx"       : idx}
        #pprint.pprint(self.__target_dict)
        for idx, t_stuff in self.__target_dict.iteritems():
            if t_stuff["mode"] == "tcp":
                self.add_object(tcp_con_object(self._new_tcp_con, connect_state_call=self._connect_state_call, connect_timeout_call=self._connect_timeout, target_host=t_stuff["host"], target_port=t_stuff["port"], bind_retries=args.get("bind_retries", 1), rebind_wait_time=args.get("rebind_wait_time", 2), timeout=t_stuff["timeout"], add_data=idx))
            else:
                self.add_object(udp_con_object(self._new_tcp_con, connect_state_call=self._connect_state_call, connect_timeout_call=self._connect_timeout, target_host=t_stuff["host"], target_port=t_stuff["port"], bind_retries=args.get("bind_retries", 1), rebind_wait_time=args.get("rebind_wait_time", 2), timeout=t_stuff["timeout"], add_data=idx))
    def iterate(self):
        if self.__target_dict:
            self.step()
            while not self.exit_requested() and self.get_num_objects():
                self.step()
        self.close()
        return self.__target_dict
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__log_hook:
            self.__log_hook.log(what, level)
        elif self.__save_logs:
            self.__log_storage.append((what, level))
        else:
            logging_tools.my_syslog("multiple_connection()[%d]: %s" % (level, what))
    def _connect_timeout(self, sock):
        self.set_error(sock.get_add_data(), NET_TIMEOUT, "connect timeout")
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.set_error(args["socket"].get_add_data(), NET_CONNECTION_REFUSED, "Error cannot connect")
    def _new_tcp_con(self, sock):
        return simple_con_obj(self, **self.__target_dict[sock.get_add_data()])#t_h, t_p, t_stuff["mode"], t_stuff["command"], t_stuff["protocoll"])
    def set_result(self, idx, data):
        self.__target_dict[idx]["ret_str"] = data
    def set_error(self, idx, errnum, data):
        self.__target_dict[idx]["errnum"] = errnum
        self.__target_dict[idx]["ret_str"] = data

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(-1)
