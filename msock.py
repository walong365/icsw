#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

import sys
import os
import icmp
import ip
import socket
import select
import errno
import types
import syslog
import threading
import time
import operator
import logging_tools
#import leak

try:
    from M2Crypto import util, BIO, Err, m2, SSL
except:
    m2 = None
    # create SSL as instance of dummy_ssl in order to define SSL.SSLError
    class dummy_ssl:
        def __init__(self):
            self.SSLError = "None"
    SSL = dummy_ssl()

FailMark = -666
SO_OBJ_MAX_CALLS = 1000

class send_instance(object):
    # dummy, needs to be subclassed
    def __init__(self):
        pass
    def get_next_send_str(self):
        return None
    def get_continue_flag(self):
        return 0
    def put_result(self, what):
        print "***", what
    
# default message class
class message(object):
    def __init__(self, type="?", arg=()):
        self.type = type
        self.thread = threading.currentThread().getName()
        self.c_time = time.time()
        self.arg = arg
    def __repr__(self):
        return "Message type %s from thread %s, args: '%s'" % (self.type, self.thread, str(self.arg))

def long_err(errnum, errstr="<UNKNOWN>"):
    long_err_dict = { 0   : "OK",
                      -2  : "Name or service not known",
                      13  : "Permission denied",
                      61  : "no data (short read)",
                      75  : "value overflow",
                      98  : "Address already in use",
                      101 : "Net unreachable",
                      107 : "Not connected",
                      110 : "Timeout",
                      111 : "Connection refused",
                      113 : "No route to host"}
    if long_err_dict.has_key(errnum):
        return long_err_dict[errnum]
    elif errno.errorcode.has_key(errnum):
        return errno.errorcode[errnum]
    else:
        return errstr

# socket_object
# the socket_object provides the functions for the state-objects
# the return-format for the functions is a tuple with 2 values; the second value is returned to the calling instance
# the first value specifies the next state of the state-object or 0 if for the next step we have to wait
class sock_object(object):
    all_socks = {}
    def __init__(self, old_socket=None):
        sock_object.all_socks[id(self)] = 1
        if old_socket:
            self.socket = old_socket
            self.unblock()
        self.set_recv_size()
        self.set_send_size()
        self.set_protocoll()
        self.__blocking = None
    def set_protocoll(self, pc=0):
        self.protocoll = pc
    def get_protocoll(self):
        return self.protocoll
    def init_err(self):
        self.errnum, self.errstr = (0, "ok")
    def get_blocking_mode(self):
        return self.__blocking
    def unblock(self):
        self.__blocking = 0
        self.socket.setblocking(0)
    def block(self):
        self.__blocking = 1
        self.socket.setblocking(1)
    def set_recv_size(self, size=65535):
        self.recv_size = size
    def set_send_size(self, size=65535):
        self.send_size = size
    def fileno(self):
        return self.socket.fileno()
    def get_type_str(self):
        return "<unspecified>"
    def __del__(self):
        #print "delete sock_object"
        del sock_object.all_socks[id(self)]
        self.socket.close()
        del self.socket
    def shutdown(self, state_o, how=2):
        if hasattr(state_o, "ssl"):
            try:
                m2.ssl_set_shutdown(state_o.ssl, how)
            except:
                pass
            m2.ssl_shutdown(state_o.ssl)
        else:
            try:
                self.socket.shutdown(how)
            except:
                pass
    # helper functions
    def get_addr_string(self, (host, port)):
        if host:
            return "Host %s (port %d)" % (host, port)
        else:
            return "Host <INADDR_ANY> (port %d)" % (port)
    # socket functions
    def wait(self, state_o, state_p):
        # waits for the returning of a function-result
        act_time = time.time()
        elapsed_time = max(act_time - state_o.start_time, 0.)
        remain_time = min(state_o.timeout - elapsed_time, state_o.step_timeout)
        # changed 2005-06-17 09:25 : time.time() to act_time
        ret = (None, act_time + remain_time)
        #print "WAITING"
        if state_p.first_call:
            state_p.first_call = 0
            state_o.waiting = 1
            state_o.next_so_part = state_o.states[state_p.get_ok_state()]
            # send received message
            if state_p.get_log_flags("r"):
                state_o.send_recv_msg()
        else:
            if state_o.waiting:
                if remain_time < 0.:
                    state_o.set_error(110, "timed out in wait")
            else:
                ret = (state_p.get_ok_state(), 0.)
        return ret
    def open_connection(self, state_o, state_p):
        ret, init_ssl = ((None, 0), 0)
        if state_p.first_call:
            state_p.first_call = 0
            state_o.reset_timeout()
            try:
                # sometimes fails for UDS-sockets
                state_o.local_addr = self.socket.getsockname()
            except socket.error, val:
                try:
                    errnum, errstr = val
                except:
                    errnum, errstr = (FailMark, str(val))
                state_o.set_error(errnum, long_err(errnum))
            else:
                state_o.other_addr = state_p.get_args()
                try:
                    self.socket.connect(state_p.get_args())
                except socket.error, val:
                    act_time = time.time()
                    elapsed_time = max(act_time - state_o.start_time, 0.)
                    remain_time = min(state_o.timeout - elapsed_time, state_o.step_timeout)
                    try:
                        errnum, errstr = val
                    except:
                        errnum, errstr = (FailMark, str(val))
                    if errnum == 115:
                        #print "**",state_o.get_poll_object()
                        state_o.get_poll_object().register_handle(self.fileno(), POLL_OUT)
                        ret = (None, act_time + remain_time)
                    else:
                        state_o.set_error(errnum, long_err(errnum))
                except SSL.SSLError, what:
                    state_o.set_error(-2, str(what))
                else:
                    ret = (state_p.get_ok_state(), 0.)
                    init_ssl = hasattr(state_o, "ssl")
        else:
            elapsed_time = max(time.time() - state_o.start_time, 0.)
            if elapsed_time > state_o.timeout:
                state_o.set_error(110, "timed out in connect")
            else:
                errnum = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if errnum:
                    state_o.set_error(errnum, long_err(errnum))
                else:
                    ret = (state_p.get_ok_state(), 0.)
                    init_ssl = hasattr(state_o, "ssl")
        if init_ssl:
            state_o.sockbio = m2.bio_new_socket(state_o.state_machine.socket.fileno(), 0)
            # Link SSL struct with the BIO_socket.
            m2.ssl_set_bio(state_o.ssl, state_o.sockbio, state_o.sockbio)
            # Make a BIO_f_ssl.
            state_o.sslbio = m2.bio_new(m2.bio_f_ssl())
            # Link BIO_f_ssl with the SSL struct.
            m2.bio_set_ssl(state_o.sslbio, state_o.ssl, 1)
            m2.ssl_set_connect_state(state_o.ssl)
            try:
                m2.ssl_connect(state_o.ssl)
            except SSL.SSLError, what:
                state_o.set_error(-2, str(what))
                ret = (None, 0.)
            else:
                #print "XXXXXXX", m2.ssl_get_verify_result(state_o.ssl)
                pass
        return ret
    def bind_port(self, state_o, state_p):
        if state_p.first_call:
            state_p.first_call = 0
            state_o.local_addr, state_p.num_retries = state_p.get_args()
        ret = (None, 0.)
        try:
            if isinstance(self, unix_sock_object):
                sock_name, sock_mode = state_o.local_addr
                try:
                    os.unlink(sock_name)
                except:
                    pass
                self.socket.bind(sock_name)
                os.chmod(sock_name, int(sock_mode, 8))
            else:
                self.socket.bind(state_o.local_addr)
        except socket.error, val:
            try:
                errnum, errstr = val
            except:
                errnum, errstr = (FailMark, str(val))
            state_p.num_retries -= 1
            if errnum == 98 and state_p.num_retries > 0:
                ret = (None, time.time() + state_o.timeout)
                if state_p.get_log_flags("l"):
                    state_o.send_log_msg("Bind to %s %s (%d, %s), waiting for %.2f seconds" % (self.get_type_str(), self.get_addr_string(state_o.local_addr), errnum, long_err(errnum, errstr), state_o.timeout))
            else:
                if state_p.get_log_flags("l"):
                    state_o.send_log_msg("Bind to %s %s failed" % (self.get_type_str(), self.get_addr_string(state_o.local_addr)))
                state_o.set_error(errnum, errstr)
        else:
            if state_p.get_log_flags("l"):
                state_o.send_log_msg("Bind to %s %s ok" % (self.get_type_str(), self.get_addr_string(state_o.local_addr)))
            ret = (state_p.get_ok_state(), 0.)
        return ret
    def listen(self, state_o, state_p):
        ret = (None, 0.)
        try:
            self.socket.listen(state_p.get_args())
        except socket.error, val:
            try:
                errnum, errstr = val
            except:
                errnum, errstr = (-1, str(val))
            state_o.set_error(errnum, errstr)
        else:
            ret = (state_p.get_ok_state(), 0.)
        return ret
    def accept(self, state_o, state_p):
        ret = (None, 0.)
        try:
            sock, source = self.socket.accept()
        except socket.error, val:
            try:
                errnum, errstr = val
            except:
                errnum, errstr = (-1, val)
            if errnum == 11:
                # error EAGAIN -> please wait !
                state_o.get_poll_object().register_handle(self.fileno(), POLL_IN)
                ret = (None, time.time() + state_o.timeout)
            else:
                state_o.set_error(errnum, errstr)
        else:
            state_o.accept_hook(state_p.get_args(), sock, source, state_o, state_o.add_data)
            # got connection, try again
            ret = (state_o.act_state, 0.)
        return ret
    def send(self, state_o, state_p):
        return self.sendto(state_o, state_p, sendto=0)
    def sendto(self, state_o, state_p, sendto=1):
        if state_p.first_call:
            state_p.first_call = 0
            if sendto:
                state_o.other_addr, state_o.send_buffer = state_p.get_args()
            else:
                args = state_p.get_args()
                if isinstance(args, send_instance):
                    #print "+++++",args
                    state_o.send_buffer = args.get_next_send_str()
                    state_o.set_continue_flag(args.get_continue_flag())
                    state_o.set_wait_for_more_flag()
                    #print "++ sendto()", state_o.send_buffer, state_o.get_continue_flag()
                else:
                    state_o.send_buffer = args
            if self.protocoll:
                # special protocol: first digit is used as flag
                state_o.send_buffer = "%d%07d%s" % (state_o.get_continue_flag() and 1 or 0, len(state_o.send_buffer), state_o.send_buffer)
            else:
                state_o.send_buffer = "%s" % (state_o.send_buffer)
        ret = (state_p.get_error_state(), 0.)
        if state_o.get_elapsed_time() > state_o.timeout:
            state_o.set_error(110, "timed out in sendto (init)")
        else:
            try:
                if hasattr(state_o, "ssl"):
                    d_sent = m2.ssl_write_nbio(state_o.ssl, state_o.send_buffer[:2048])
                else:
                    if sendto:
                        d_sent = self.socket.sendto(state_o.send_buffer, state_o.other_addr)
                    else:
                        d_sent = self.socket.send(state_o.send_buffer)
            except socket.error, (errnum, errstr):
                remain_time = state_o.get_remain_time()
                if remain_time < 0.:
                    state_o.set_error(110, "timed out in sendto")
                else:
                    if errnum == 11:
                        state_o.get_poll_object().register_handle(self.fileno(), POLL_OUT)
                        ret = (None, time.time() + remain_time)
                    else:
                        state_o.set_error(errnum, errstr)
            except SSL.SSLError, what:
                state_o.set_error(-2, str(what))
            else:
                if d_sent < len(state_o.send_buffer):
                    if d_sent > 0:
                        state_o.send_buffer = state_o.send_buffer[d_sent:]
                    state_o.get_poll_object().register_handle(self.fileno(), POLL_OUT)
                    ret = (None, time.time() + state_o.step_timeout)
                else:
                    if state_o.get_continue_flag() and state_p.get_cont_state():
                        state_o.set_continue_flag(0)
                        state_o.set_wait_for_more_flag(1)
                        ret = (state_p.get_cont_state(), 0.)
                    else:
                        ret = (state_p.get_ok_state(), 0.)
        return ret
    def recv(self, state_o, state_p):
        return self.recvfrom(state_o, state_p, recvfrom = 0)
    def recvfrom(self, state_o, state_p, recvfrom=1):
        if state_p.first_call:
            state_p.first_call = 0
            state_o.init_iteration()
            state_o.reset_timeout()
            state_o.act_in_buffer = ""
            state_p.loc_counter, state_p.empty_counter = (0, 0)
        state_p.loc_counter += 1
        ret = (state_p.get_error_state(), 0.)
        if state_o.get_elapsed_time() > state_o.timeout:
            state_o.set_error(110, "timed out in recv (init)")
        else:
            try:
                # actual receive - size
                act_recv_size = self.recv_size
                if self.protocoll and len(state_o.act_in_buffer) > 7:
                    try:
                        act_recv_size = int(state_o.act_in_buffer[1:8]) + 8 - len(state_o.act_in_buffer)
                    except:
                        act_recv_size = self.recv_size
                if hasattr(state_o, "ssl"):
                    d_read = m2.ssl_read_nbio(state_o.ssl, act_recv_size)
                else:
                    if recvfrom:
                        d_read, frm = self.socket.recvfrom(act_recv_size)
                        state_o.other_addr = frm
                    else:
                        d_read = self.socket.recv(act_recv_size)
                # store in buffer
                if type(d_read) != type(None):
                    state_o.act_in_buffer += d_read
##             except socket.error:
##                 print sys.exc_info()[0], str(sys.exc_info()[1])
            except socket.error, val:
                try:
                    errnum, errstr = val
                except:
                    errnum, errstr = (FailMark, "%s: %s" % (str(sys.exc_info()[0]),
                                                            str(sys.exc_info()[1])))
                remain_time = state_o.get_remain_time()
                if remain_time < 0.:
                    state_o.set_error(110, "timed out in recv")
                else:
                    if errnum == 11:
                        state_o.get_poll_object().register_handle(self.fileno(), POLL_IN)
                        ret = (None, time.time() + remain_time)
                    else:
                        state_o.set_error(errnum, errstr)
            except SSL.SSLError, what:
                state_o.set_error(-2, str(what))
            else:
                if d_read:
                    state_p.empty_counter = 0
                    #print "** got '%s', %d, %d, '%s'" % (d_read, len(d_read), self.protocoll, state_o.act_in_buffer)
                    # check if we are already done
                    rcv_done, wait_for_more = (0, 0)
                    if self.protocoll:
                        if len(state_o.act_in_buffer) > 7:
                            try:
                                wait_for_more, msg_len = (int(state_o.act_in_buffer[0]),
                                                          int(state_o.act_in_buffer[1:8]))
                            except ValueError:
                                state_o.set_error(75, "Value Overflow parsing %s" % (str(state_o.act_in_buffer[1:8])))
                            else:
                                if len(state_o.act_in_buffer) == 8 + msg_len:
                                    state_o.act_in_buffer = state_o.act_in_buffer[8:]
                                    rcv_done = 1
                    else:
                        rcv_done, wait_for_more = (1, 0)
                    if rcv_done:
                        if wait_for_more:
                            # sending side required more, so do we
                            state_o.set_continue_flag()
                        state_o.set_wait_for_more_flag(wait_for_more)
                        #print wait_for_more, state_o.get_continue_flag(), state_p.get_cont_state(), state_p.name
                        if state_o.get_continue_flag():
                            if state_p.get_cont_state():
                                state_o.set_continue_flag(0)
                                ret = (state_p.get_cont_state(), 0.)
                            else:
                                # save continue flag for next part with cont_state
                                #state_o.set_continue_flag(0)
                                #state_o.set_wait_for_more_flag(1)
                                ret = (state_p.get_ok_state(), 0.)
                        else:
                            ret = (state_p.get_ok_state(), 0.)
                        #print state_p.get_args(), state_p.get_log_flags("r")
                        # can be beautified
                        if state_p.get_args() and isinstance(state_p.get_args(), send_instance):
                            state_p.get_args().put_result(state_o.act_in_buffer)
                        #if isinstance(args, send_instance):
                        if not state_p.get_args() and state_p.get_log_flags("r"):
                            state_o.send_recv_msg()
                    else:
                        state_o.get_poll_object().register_handle(self.fileno(), POLL_IN)
                        ret = (None, time.time() + state_o.get_remain_time())
                else:
                    state_p.empty_counter += 1
                    if state_p.empty_counter == 10:
                        state_p.empty_counter = 0
                        ret = (None, time.time() + state_o.get_remain_time())
                    else:
                        state_o.get_poll_object().register_handle(self.fileno(), POLL_IN)
                        ret = (None, time.time() + state_o.get_remain_time())
                    # nothing read
        return ret
    def closesock(self, state_o, state_p):
        act_time = time.time()
        if state_p.first_call:
            state_p.first_call = 0
            state_o.close_time = act_time
            state_o.close_timeout = state_p.get_args()
            if state_o.close_timeout is None:
                state_o.close_timeout = state_o.step_timeout
            state_o.get_poll_object().register_handle(self.fileno(), POLL_ERR)
            ret = (None, act_time + state_o.close_timeout)
        else:
            elapsed_time = max(act_time - state_o.close_time, 0.)
            #print "*", elapsed_time, state_o.step_timeout
            if elapsed_time > state_o.close_timeout:
                if hasattr(state_o, "ssl"):
                    self.shutdown(state_o, SSL.SSL_SENT_SHUTDOWN|SSL.SSL_RECEIVED_SHUTDOWN)
                else:
                    self.shutdown(state_o)
                ret = (state_p.get_ok_state(), 0.)
            else:
                state_o.get_poll_object().register_handle(self.fileno(), POLL_ERR)
                ret = (None, act_time + state_o.close_timeout)
        return ret

class icmp_sock_object(sock_object):
    def __init__(self):
        sock_object.__init__(self)
        self.set_timeout_par()
        self.socket = icmp.PingSocket()
        self.__pid = os.getpid()
        self.__seq = 1
        self.__add_lock = threading.RLock()
        self.ret_dict = {}
        self.icmps, self.new_icmps, self.address_mapping, self.name_mapping = ({}, {}, {}, {})
        self.set_new_message_format()
    def set_new_message_format(self, nmf = 0):
        self.new_message_format = nmf
    def get_new_message_format(self):
        return self.new_message_format
    def get_type_str(self):
        return "<ICMP>"
    def set_timeout_par(self, tot=4.0, step=1.0):
        self.total_timeout = max(tot, 0.)
        self.step_timeout = min(step, self.total_timeout)
    def add_target_host(self, address, key, num = 3, timeout=5, q_dict = {}, add_data=None, flood=0):
        # key should be a unique key
        if type(address) == type(""):
            address = [address]
        self.__add_lock.acquire()
        for o_addr in address:
            try:
                fqname, aliases, ip_list = socket.gethostbyname_ex(o_addr)
            except socket.gaierror:
                # create temporary icmp_send_obj
                if o_addr not in self.new_icmps.keys():
                    addr = o_addr
                    new_so = icmp_send_obj(o_addr, addr, 0)
                    new_so.set_new_message_format(self.get_new_message_format())
                    new_so.set_error(FailMark, "Unable to resolve host '%s'" % (o_addr))
                    self.new_icmps[addr] = new_so
                else:
                    #print "*****", o_addr
                    new_so = None
            else:
                addr = ip_list[0]
                #self.address_mapping[addr] = (o_addr, fqname, aliases)
                #self.name_mapping[o_addr] = addr
                if addr not in self.new_icmps.keys():
                    new_so = icmp_send_obj(o_addr, addr, num)
                    new_so.set_new_message_format(self.get_new_message_format())
                    new_so.set_flood_flag(flood)
                    new_so.set_timeout(timeout)
                    self.new_icmps[addr] = new_so
                else:
                    new_so = self.new_icmps[addr]
            if new_so:
                new_so.add_key(key, q_dict, add_data)
        self.__add_lock.release()
    def icmp_step(self, state_o, state_p):
        # check for new icmp's
        self.__add_lock.acquire()
        for k1, v1 in self.new_icmps.iteritems():
            if self.icmps.has_key(k1):
                for k2, v2 in v1.key_dict.iteritems():
                    self.icmps[k1].key_dict[k2] = v2
            else:
                self.icmps[k1] = v1
        self.new_icmps = {}
        self.__add_lock.release()
        # time to wait
        ttw = 5000.
        can_send = True
        max_send = 50
        while can_send and max_send:
            max_send -= 1
            max_inner_send = 20
            # iterate as long as we can send an icmp packet and max_send is > 0
            for addr, icmp_s in self.icmps.iteritems():
                if icmp_s.to_send and icmp_s.ready_to_send:
                    self.__seq = operator.mod(self.__seq + 1, 20000)
                    #print "send to %s" % (addr)
                    icmp_s.send_packet(self.socket, self.step_timeout, self.__seq, self.__pid)
                    max_inner_send -= 1
                    if not max_inner_send:
                        break
                #icmp_s.show_status()
            while True:
                arrival = time.time()
                try:
                    r_pkt, who = self.socket.recvfrom(4096)
                except socket.error, (errnum, errstr):
                    break
                else:
                    source_host, source_port = who
                    rep_ip = ip.Packet(r_pkt)
                    try:
                        reply = icmp.Packet(rep_ip.data)
                    except ValueError:
                        print "ValueError"
                    else:
                        if reply.id == self.__pid:
                            # process reply-packet
                            #src = rep_ip.src
                            #print "got from %s (port %d), src=%s" % (source_host, source_port, src)
                            if self.icmps.has_key(source_host):
                                self.icmps[source_host].got_reply(reply, arrival)
            can_send = False
            for addr in self.icmps.keys():
                icmp_s = self.icmps[addr]
                ttw = min(ttw, icmp_s.check_timeout())
                if icmp_s.status:
                    icmp_s.send_reply(self)
                    del self.icmps[addr]
                else:
                    if icmp_s.to_send and icmp_s.ready_to_send:
                        can_send = True
        if self.icmps.keys():
            state_o.get_poll_object().register_handle(self.fileno(), POLL_IN)
            ret = (None, time.time() + ttw)
        else:
            # nothing to do for me, ignore incoming packets
            ret = (None, time.time() + ttw)
        return ret

class tcp_sock_object(sock_object):
    def __init__(self, old_socket = None):
        if old_socket:
            sock_object.__init__(self, old_socket)
        else:
            sock_object.__init__(self)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.socket.setsockopt(socket.SOCK_STREAM, socket.SO_KEEPALIVE, 1)
            except:
                pass
        self.unblock()
    def __del__(self):
        #print "delete tcp_sock_object"
        sock_object.__del__(self)
    def get_type_str(self):
        return "<TCP>"
    
class udp_sock_object(sock_object):
    def __init__(self, old_socket = None):
        if old_socket:
            sock_object.__init__(self, old_socket)
        else:
            sock_object.__init__(self)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.unblock()
    def get_addr_string(self, (host, port)):
        if host != "0.0.0.0":
            if host:
                return "Host %s (port %d)" % (host, port)
            else:
                return "Host <INADDR_ANY> (port %d)" % (port)
        else:
            return "Host <local UDP-SOCKET>"
    def get_type_str(self):
        return "<UDP>"
    def __del__(self):
        #print "delete udp_sock_object"
        pass
    
class unix_sock_object(sock_object):
    def __init__(self, old_socket = None):
        if old_socket:
            sock_object.__init__(self, old_socket)
        else:
            sock_object.__init__(self)
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.unblock()
    def __del__(self):
        #print "delete unix_sock_object"
        sock_object.__del__(self)
    def get_type_str(self):
        return "<UDS>"
    def get_addr_string(self, (socket, mode)):
        return "UDS %s (mode %s)" % (socket, mode)

class so_part(object):
    def __init__(self, name, func_name, valid_next, args = None, oe_dict={}, log_flags="erl"):
        self.__name = name
        self.__func_name = func_name
        self.valid_next = valid_next
        self.args = args
        self.oe_dict = oe_dict
        # first call in actual loop
        self.first_call = 1
        # the log flag 'e' (for error messages) is in fact never checked, the flag 'r' very seldom
        self.set_log_flags(log_flags)
    def get_name(self):
        return self.__name
    def get_func_name(self):
        return self.__func_name
    def set_log_flags(self, lf):
        self.log_flags = lf
    def get_log_flags(self, what=None):
        if what:
            return what in self.log_flags
        else:
            return self.log_flags
    def __call__(self, s_obj):
        return self.r_func(s_obj, self)
    def set_args(self, args):
        self.args = args
    def get_args(self):
        return self.args
    def set_func_addr(self, s_mach):
        self.r_func = getattr(s_mach, self.__func_name)
    def get_next_list(self):
        return self.valid_next
    def set_oe_dict(self, last_error_state):
        self.error_state   = self.oe_dict.get("e", last_error_state)
        self.ok_state      = self.oe_dict.get("o", self.valid_next[0])
        self.cont_state    = self.oe_dict.get("c", None)
        self.timeout_state = self.oe_dict.get("t", None)
    def get_ok_state(self):
        return self.ok_state
    def get_cont_state(self):
        return self.cont_state
    def get_error_state(self):
        return self.error_state
    def get_timeout_state(self):
        return self.timeout_state
    def __repr__(self):
        return "so_part, name %s, valid_next %s, arg %s" % (self.__name, self.valid_next, self.args and "%d bytes" % (len(self.args)) or "empty")
    def __del__(self):
        self.r_func = None
        #print "delete so_part %s" % (self.name)
        pass
        
def single_icmp_ping(target, num, timeout, flood):
    sd = [so_part("l", "icmp_step", ["l"], None)]
    so = state_object("l", sd, icmp_sock_object())
    try:
        so.fileno()
    except:
        errnum, r_dict = (13, {})
    else:
        my_po = poll_object()
        so.set_poll_object(my_po)
        if type(target) == type(""):
            target = [target]
        so.state_machine.add_target_host(target, 0,num, timeout, {}, None, flood)
        so.single_step()
        while not so.errnum and so.new_state != "ok" and so.state_machine.icmps:
            what, act_to = so.act_reply
            act_to -= time.time()
            if not what and act_to > 0:
                try:
                    my_po.poll(act_to * 1000)
                except socket.error, (errnum, errstr):
                    print "Socket error (%d, %s)" % (errnum, errstr)
            so.step()
        errnum, r_dict = (0, so.state_machine.ret_dict)
        del my_po
    return errnum, r_dict
    
def get_tcp_object((dest_host, dest_port, command), add_data=None, timeout=5, protocoll=1, ssl_context=None):
    if ssl_context and not m2:
        return None
    if type(command) == type(()) and len(command) == 2:
        s_command, r_command = command
    else:
        s_command, r_command = (command, None)
    # initiates a new connection
    sd = [so_part("b", "open_connection", ["s"]          , (dest_host, dest_port), {"e" : "c"} ),
          so_part("s", "send"           , ["r", "s"]     , s_command                           ),
          so_part("r", "recv"           , ["c", "r", "s"], r_command             , {"c" : "s"} ),
          so_part("c", "closesock"      , ["c"]          , 0.0001                , {"o" : "ok"})]
    so = state_object("b", sd, tcp_sock_object(), {}, add_data)
    if ssl_context:
        so.ssl_context = ssl_context
        so.ssl = m2.ssl_new(so.ssl_context.ctx)
    so.set_timeout(timeout)
    so.set_protocoll(protocoll)
    return so

def multiple_tcp_connections(so_list):
    # build so_dict
    so_dict, res_dict = (dict([(x.fileno(), x) for x in so_list]),
                         {})
    my_po = poll_object()
    for f_no, s_o in so_dict.iteritems():
        s_o.set_poll_object(my_po)
        s_o.single_step()
    while so_dict:#[1 for x in so_list if (not x.errnum and x.new_state != "ok")]:
        # check for finished instances
        done_list = []
        for k, v in so_dict.iteritems():
            if v.errnum or v.new_state == "ok":
                done_list.append(k)
                if v.errnum:
                    res_dict[v.fileno()] = (v.errnum, v.errstr)
                else:
                    res_dict[v.fileno()] = (0, v.act_in_buffer)
        for k in done_list:
            del so_dict[k]
        if not so_dict:
            break
        # iterate so_dict and build g_list
        global_poll, act_to = (1, 100)
        act_time = time.time()
        for k, v in so_dict.iteritems():
            local_step, remain_time = v.act_reply
            remain_time -= act_time
            if local_step or remain_time <= 0:
                global_poll = 0
                v.step()
            elif global_poll:
                act_to = min(act_to, remain_time)
        if global_poll:
            for key, key_type in my_po.poll(act_to * 1000):
                if so_dict.has_key(key):
                    so_dict[key].step()
##         print "***"
##         break
    del my_po
    return res_dict
    
def single_tcp_connection((dest_host, dest_port, command), add_data=None, timeout=5, protocoll=1, ssl_context=None):
    if ssl_context and not m2:
        return 111, "no m2-module found"
    so = get_tcp_object((dest_host, dest_port, command), add_data, timeout, protocoll, ssl_context)
    #so.set_verbose(1)
    my_po = poll_object()
    so.set_poll_object(my_po)
    so.single_step()
    while not so.errnum and so.new_state != "ok":
        local_step, remain_time = so.act_reply
        remain_time -= time.time()
        if not local_step and remain_time > 0:
            try:
                my_po.poll(remain_time * 1000)
            except socket.error, (errnum, errstr):
                print "Socket error (%d, %s)" % (errnum, errstr)
            #else:
            #    print so.new_state, so.act_state, g_list
        so.step()
    del my_po
    if so.errnum:
        return so.errnum, so.errstr
    else:
        #if not isinstance(command, send_instance):
        #    so.in_buffer = so.in_buffer[0]
        return 0, so.act_in_buffer

def get_udp_object((dest_host, dest_port, command), add_data=None, timeout=5, protocoll=1):
    # initiates a new connection
    sd = [so_part("b", "bind_port", ["s"]     , (("0.0.0.0", 0), 1),  {"e" : "c"} ),
          so_part("s", "sendto"   , ["c", "s"], ((dest_host, dest_port), command)),
          so_part("c", "closesock", ["c"]     , 0.0001             ,  {"o" : "ok"})]
    so = state_object("b", sd, udp_sock_object(), {}, add_data)
    so.set_timeout(timeout)
    so.set_protocoll(protocoll)
    return so

def single_udp_connection_op(so):
    # initiates a new connection
    so.step()
    #so.set_verbose(1)
    while not so.errnum and so.new_state != "ok":
        local_step, remain_time = so.act_reply
        remain_time -= time.time()
        if not local_step and remain_time > 0:
            try:
                so.get_poll_object().poll(remain_time * 1000)
            except socket.error, (errnum, errstr):
                print "Socket error (%d, %s)" % (errnum, errstr)
        so.step()
    if so.errnum:
        return so.errnum, so.errstr
    else:
        return 0, "ok sent"

def single_udp_connection((dest_host, dest_port, command), add_data=None, timeout=5, protocoll=1):
    # initiates a new connection
    so = get_udp_object((dest_host, dest_port, command), add_data, timeout, protocoll)
    my_po = poll_object()
    so.set_poll_object(my_po)
    so.step()
    #so.set_verbose(1)
    while not so.errnum and so.new_state != "ok":
        local_step, remain_time = so.act_reply
        remain_time -= time.time()
        if not local_step and remain_time > 0:
            try:
                my_po.poll(remain_time * 1000)
            except socket.error, (errnum, errstr):
                print "Socket error (%d, %s)" % (errnum, errstr)
        so.step()
    del my_po
    if so.errnum:
        return so.errnum, so.errstr
    else:
        return 0, "ok sent"

def single_unix_domain_connection_op(so):
    so.step()
    if not so.state_machine.get_blocking_mode():
        while not so.errnum and so.new_state != "ok":
            local_step, remain_time = so.act_reply
            remain_time -= time.time()
            if not local_step and remain_time > 0:
                try:
                    my_po.poll(remain_time * 1000)
                except socket.error, (errnum, errstr):
                    print "Socket error (%d, %s)" % (errnum, errstr)
            so.step()
    if so.errnum:
        return so.errnum, so.errstr
    else:
        return 0, "ok"
    
def get_uds_object(sock_name, command, timeout=5, protocoll=0, blocking=1):
    sd = [so_part("b", "open_connection", ["s"], sock_name, {"e" : "c"} ),
          so_part("s", "send"           , ["c"], command                ),
          so_part("c", "closesock"      , ["c"], 0.0      , {"o" : "ok"})]
    so = state_object("b", sd, unix_sock_object())
    so.set_protocoll(protocoll)
    so.set_timeout(timeout)
    # use blocking communication for uds connections
    if blocking:
        so.state_machine.block()
    else:
        so.state_machine.unblock()
    return so
    
def single_unix_domain_connection(sock_name, command, timeout=5, protocoll=0, blocking=1):
    # initiates a new connection
    so = get_uds_object(sock_name, command, timeout, protocoll, blocking)
    my_po = poll_object()
    so.set_poll_object(my_po)
    so.step()
    if not so.state_machine.get_blocking_mode():
        while not so.errnum and so.new_state != "ok":
            local_step, remain_time = so.act_reply
            remain_time -= time.time()
            if not local_step and remain_time > 0:
                try:
                    my_po.poll(remain_time * 1000)
                except socket.error, (errnum, errstr):
                    print "Socket error (%d, %s)" % (errnum, errstr)
            so.step()
    del my_po
    if so.errnum:
        return so.errnum, so.errstr
    else:
        return 0, "ok"

class simple_state_object(object):
    def __init__(self, first_state, state_list, state_machine, queue_dict={}, add_data = None):
        pass
    
# state object (runs through state-machine)
class state_object(object):
    def __init__(self, first_state, state_list, state_machine, queue_dict={}, add_data = None):
        self.init_err()
        # init verbose-flag
        self.set_verbose(0)
        # save additional data
        self.set_add_data(add_data)
        # save state_machine
        self.state_machine = state_machine
        # actual state and next state
        self.__first_state = first_state
        # actual reply
        self.act_reply = None
        # polling object
        self.set_poll_object()
        # init state dictionary
        self.states = {}
        self.init_iteration()
        # queue dictionary
        self.set_queue_dict(queue_dict)
        # address of foreing host
        self.other_addr = None
        # clear continue flag by default
        self.set_continue_flag(0)
        # clear wait_for_more flag by default
        self.set_wait_for_more_flag()
        # rewrite references
        # if no error-exit-state is given, the last one will be used
        # if no ok-exit-state is given, the first of the valid_next list will be used
        act_error_state = None
        for so_p in state_list:
            self.states[so_p.get_name()] = so_p
            if so_p.oe_dict.has_key("o"):
                act_error_state = so_p.oe_dict["o"]
            so_p.set_func_addr(state_machine)
            so_p.set_oe_dict(act_error_state)
        self.init_states()
        #print "State dict:", self.states
        self.set_timeout()
        self.set_new_message_format()
    def set_external_key(self, ek):
        self.ext_key = ek
    def get_external_key(self):
        return self.ext_key
    def init_states(self):
        self.act_state, self.new_state = (self.__first_state, None)
        if self.act_state:
            if not self.states.has_key(self.act_state):
                self.set_error(FailMark, "Actual state %s not found in state_object keylist '%s'" % (str(self.act_state), ", ".join(self.states.keys())))
            else:
                self.act_so_part = self.states[self.act_state]
                self.act_so_part.first_call = 1
    def set_state_command(self, sn, com):
        self.states[sn].set_args(com)
    def set_poll_object(self, po=None):
        self.__poll_obj = po
    def get_poll_object(self):
        return self.__poll_obj
    def init_iteration(self):
        # number of function-calls
        self.calls = 0
    def set_wait_for_more_flag(self, wfm=0):
        #print "******", wfm
        self.__wait_for_more = wfm
    def wait_for_more(self):
        return self.__wait_for_more
    def set_continue_flag(self, cf=1):
        self.__continue = cf
    def get_continue_flag(self):
        return self.__continue
    def set_new_message_format(self, nmf = 0, with_sm=0):
        self.new_message_format = nmf
        if with_sm:
            self.state_machine.set_new_message_format(nmf)
    def set_queue_dict(self, q_dict):
        self.queue_dict = q_dict
    def set_add_data(self, a_data):
        self.add_data = a_data
    def get_elapsed_time(self):
        if self.timeout:
            elapsed_time = max(time.time() - self.start_time, 0.)
        else:
            elapsed_time = -1
        return elapsed_time
    def get_remain_time(self):
        if self.timeout:
            elapsed_time = max(time.time() - self.start_time, 0.)
            remain_time = min(self.timeout - elapsed_time, self.step_timeout)
        else:
            remain_time = 30.
        return remain_time
    def set_protocoll(self, pc):
        self.state_machine.set_protocoll(pc)
    def get_protocoll(self):
        return self.state_machine.get_protocoll()
    def fileno(self):
        return self.state_machine.fileno()
    def __del__(self):
        #print "delete state_objectx"
        #print self.calls
        pass
    def set_timeout(self, tot=5.0, step=None):
        # sets max. lifetime in seconds for this state_object
        # a timeout of 0 indicates no timeout at all
        self.timeout = max(tot, 0.)
        if not step:
            step = self.timeout / 5.
        self.step_timeout = min(step, self.timeout)
        # init start-time
        self.reset_timeout()
    def get_timeout(self):
        return self.timeout, self.step_timeout
    def reset_timeout(self):
        self.start_time = time.time()
    def set_verbose(self, verbose=0):
        self.verbose = verbose
    def single_step(self, new_state=None):
        return self.step(new_state, 1)
    def send_error_msg(self):
        err_queue = self.queue_dict.get("e", None)
        if err_queue:
            if self.new_message_format:
                err_queue.put(("mserr", (self.ext_key, (self.local_addr, self.other_addr, (self.errnum, self.errstr)), self.add_data)))
            else:
                err_queue.put(message("mserr", (self.ext_key, (self.local_addr, self.other_addr, (self.errnum, self.errstr)), self.add_data)))
    def send_recv_msg(self, del_in_buffer=1):
        recv_q = self.queue_dict.get("r", None)
        if recv_q:
            #print"*******", self.add_data
            if self.new_message_format:
                recv_q.put(("msrcv", (self.ext_key, (self.local_addr, self.other_addr, self.act_in_buffer), self.add_data)))
            else:
                recv_q.put(message("msrcv", (self.ext_key, (self.local_addr, self.other_addr, self.act_in_buffer), self.add_data)))
            if del_in_buffer:
                self.act_in_buffer = []
    def send_log_msg(self, log_str):
        log_q = self.queue_dict.get("l", None)
        if log_q:
            if self.new_message_format:
                log_q.put(("mslog", (self.ext_key, (self.local_addr, self.other_addr, log_str), self.add_data)))
            else:
                log_q.put(message("mslog", (self.ext_key, (self.local_addr, self.other_addr, log_str), self.add_data)))
    def step(self, new_state=None, num_steps=0):
        ret_val = None
        while 1:
            if self.new_state and not new_state:
                new_state = self.new_state
            if new_state:
                if self.states.has_key(new_state):
                    if new_state in self.act_so_part.get_next_list():
                        if self.verbose:
                            print "(%d/%d) %s Advancing from %s (%s) to %s" % (self.fileno(),
                                                                               self.ext_key,
                                                                               time.ctime(),
                                                                               self.act_so_part.get_func_name(),
                                                                               self.act_state,
                                                                               new_state)
                        self.act_state = new_state
                        self.act_so_part = self.states[self.act_state]
                        # experimental to enable continue-mode
                        self.act_so_part.first_call = 1
                    else:
                        self.set_error(FailMark, "New state %s not allowed in state_object keylist '%s' of act_state %s" % (str(new_state), ", ".join(self.act_so_part.get_next_list()), str(self.act_state)))
                else:
                    self.set_error(FailMark, "New state %s not found in state_object keylist '%s'" % (str(new_state), ", ".join(self.states.keys())))
            if not self.errnum:
                self.calls += 1
                # call only if no error has accured up to now
                self.new_state = None
                if self.verbose:
                    print "(%d/%d) Calling state %s (%s)" % (self.fileno(),
                                                             self.ext_key,
                                                             self.act_so_part.get_func_name(),
                                                             self.act_state)
                new_state, ret_val = self.act_so_part(self)
                if self.verbose:
                    if new_state == self.act_state:
                        print "  (%d/%d) Returned from call %s (%s) (no state_change), continue_flag is %s" % (self.fileno(),
                                                                                                               self.ext_key,
                                                                                                               self.act_so_part.get_func_name(),
                                                                                                               self.act_state,
                                                                                                               self.get_continue_flag() and "enabled" or "disabled")
                    else:
                        print "  (%d/%d) Returned from call %s (%s) (new_state: %s), continue_flag is %s" % (self.fileno(),
                                                                                                             self.ext_key,
                                                                                                             self.act_so_part.get_func_name(),
                                                                                                             self.act_state,
                                                                                                             new_state,
                                                                                                             self.get_continue_flag() and "enabled" or "disabled")
                    print "  (%d/%d) time left: %.2f seconds" % (self.fileno(),
                                                                 self.ext_key,
                                                                 self.timeout - self.get_elapsed_time())
                if new_state:
                    self.new_state = new_state
                # check for special timeout-hook
                if self.errnum == 110 and self.act_so_part.get_timeout_state():
                    self.init_err()
                    self.reset_timeout()
                    new_state = self.act_so_part.get_timeout_state()
                self.act_reply = (new_state, ret_val)
            #print " + ", new_state, ret_val
            num_steps -= 1
            if not new_state or self.errnum or num_steps == 0 or new_state == "ok":
                break
        if self.errnum:
            self.send_error_msg()
        return self.act_reply
    def set_error(self, errnum, errstr):
        self.errnum, self.errstr = (errnum, errstr)
    def init_err(self):
        self.errnum, self.errstr = (0, "ok")
    def show_error(self):
        if self.errnum == FailMark:
            return "Error %d (%s)" % (self.errnum, self.errstr)
        else:
            return "Error %d (%s)" % (self.errnum, long_err(self.errnum, self.errstr))
    
class icmp_send_obj(state_object):
    def __init__(self, other_addr=None, t_addr=None, num=0):
        state_object.__init__(self, None, {}, None)
        self.addr, self.other_addr = (t_addr, other_addr)
        self.num, self.to_send, self.received = (num, num, 0)
        self.deltas, self.wait_for = ({}, {})
        self.ready_to_send = (self.num > 0)
        self.__last_send = 0
        self.status = 0
        self.key_dict = {}
        self.set_flood_flag()
        self.set_timeout()
        #print "New icmp_send to ", t_addr, self.start_time
        self.local_addr = ("raw ping socket", 0)
        self.set_fileno(FailMark)
        self.set_new_message_format()
    def set_new_message_format(self, nmf=0):
        self.new_message_format = nmf
    def set_flood_flag(self, flood = 0):
        self.flood = flood
    def set_fileno(self, fn):
        self.act_fileno = fn
        self.set_external_key(fn)
    def fileno(self):
        return self.act_fileno
    def add_key(self, key, r_queue, add_data):
        #print "kd:", key_dict
        self.key_dict[key] = (r_queue, add_data)
        self.set_queue_dict(r_queue)
        self.set_add_data(add_data)
    def send_packet(self, socket, step_timeout, seq, id):
        act_time = time.time()
        if self.to_send:
            if self.ready_to_send or act_time - self.__last_send > step_timeout:
                self.ready_to_send = self.flood
                self.to_send -= 1
                s_pkt = icmp.Packet()
                #print "Send to %s (seq=%d)" % (self.addr, seq)
                s_pkt.type, s_pkt.id, s_pkt.seq, s_pkt.data = (icmp.ICMP_ECHO, id, seq, "init.at sock_pingtest")
                socket.sendto(self.addr, s_pkt.assemble())
                self.wait_for[seq] = act_time
                self.__last_send = act_time
                self.deltas[seq] = FailMark
    def got_reply(self, reply, arrival):
        if self.wait_for.has_key(reply.seq) and self.deltas.has_key(reply.seq):
            self.deltas[reply.seq] = arrival - self.wait_for[reply.seq]
            self.received += 1
            del self.wait_for[reply.seq]
            if self.to_send:
                self.ready_to_send = True
            elif self.received == self.num:
                self.generate_summary()
                self.status = 1
    def check_timeout(self):
        act_time = time.time()
        if not self.status and act_time >= self.start_time + self.timeout or not self.num:
            self.generate_summary()
            self.status = -1
            wait_time = 5000.
        else:
            wait_time = self.start_time + self.timeout - act_time
        return wait_time
    def show_status(self):
        print "address: %s" % (str(self.addr))
        print "to_send %d, total %d" % (self.to_send, self.num)
    def generate_summary(self):
        if self.num:
            dltas = self.deltas.values()
            miss = dltas.count(FailMark)
            sent = len(dltas)
            recv = sent - miss
            davg, dmin, dmax, loss = (0, 0, 0, 0)
            if sent:
                if miss != sent:
                    dmin = min([x for x in dltas if x != FailMark])
                    davg = (reduce(lambda x, y : x + y, dltas) - miss * FailMark) / (sent - miss)
                    dmax = max([x for x in dltas if x != FailMark])
                loss = 100 * int(float(sent - recv) / float(sent))
            self.act_in_buffer = (self.num, sent, recv, loss, dmin, davg, dmax, time.time() - self.start_time)
        else:
            self.act_in_buffer = (self.num, 0, 0, 0, 0, 0, 0, 0)
    def send_reply(self, icmp_sock):
        for key, (r_queue, add_data) in self.key_dict.iteritems():
            if r_queue:
                # queue(s) defined: send
                self.set_external_key(key)
                self.set_queue_dict(r_queue)
                self.set_add_data(add_data)
                if self.num:
                    self.send_recv_msg(0)
                else:
                    self.send_error_msg()
            else:
                icmp_sock.ret_dict[self.other_addr] = self.act_in_buffer
                icmp_sock.ret_dict[self.addr] = self.act_in_buffer

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
        self.log("registering fd %d to type %d" % (fd, pt))
    def poll_check_registered(self, fd):
        return self.__poll_inv_type_dict.get(fd, 0)
    def poll_unregister(self, fd):
        if self.__poll_inv_type_dict.has_key(fd):
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
    def register_handle(self, h, ht):
        if h:
            if h in self.__poll_inv_type_dict.keys():
                if self.__poll_inv_type_dict[h] != ht:
                    self.poll_unregister(h)
                    self.poll_register(h, ht)
            else:
                self.poll_register(h, ht)
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
        
def tcp_accept_hook(net_server, sock, (src_host, src_port), other_so, add_data):
    sd = [so_part("r" , "recv"     , ["w"]           , 1                       , {"e" : "c"} ),
          so_part("w" , "wait"     , ["s", "w", "ew"], None                    , {"t" : "ew"}),
          so_part("ew", "send"     , ["c"]           , "error internal timeout"              ),
          so_part("s" , "send"     , ["c", "r"]      , None                    , {"c" : "r"} ),
          so_part("c" , "closesock", ["c"]           , 0.1                     , {"o" : "ok"})]
    so = state_object("r", sd, tcp_sock_object(sock), other_so.queue_dict, other_so.add_data)
    so.set_new_message_format(net_server.get_new_message_format())
    if hasattr(so.state_machine.socket, "getsockname"):
        so.local_addr = so.state_machine.socket.getsockname()
    else:
        so.local_addr = ("not set", 0)
    so.other_addr = (src_host, src_port)
    so.set_protocoll(other_so.get_protocoll())
    so.set_timeout(*other_so.get_timeout())
    so.set_verbose(net_server.get_verbose())
    if hasattr(other_so, "ssl"):
        so.ssl_context = other_so.ssl_context
        so.ssl = m2.ssl_new(so.ssl_context.ctx)
        so.sockbio = m2.bio_new_socket(so.state_machine.socket.fileno(), 0)
        # Link SSL struct with the BIO_socket.
        m2.ssl_set_bio(so.ssl, so.sockbio, so.sockbio)
        # Make a BIO_f_ssl.
        so.sslbio = m2.bio_new(m2.bio_f_ssl())
        # Link BIO_f_ssl with the SSL struct.
        m2.bio_set_ssl(so.sslbio, so.ssl, 1)
        m2.ssl_set_accept_state(so.ssl)
        m2.ssl_accept(so.ssl)
    net_server.add_object(so)

class is_net_server(object):
    def __init__(self, name = None, log_hook=None, new_pid_hook=None, **ndict):
        self.__log_hook, self.new_pid_hook = (log_hook, new_pid_hook)
        self.__err_log_hook = ndict.get("err_log_hook", log_hook)
        self.set_timeout()
        self.exit_rt_flag = None
        if name:
            self.__name = name
        else:
            self.__name = threading.currentThread().getName()
        # state-object dictionary
        self.__so_dict = {}
        # ext_key dict
        self.__ext_key_dict = {}
        # poll_object
        self.__poll_obj = poll_object(log_handle=self.log)
        # ping state-object
        self.__ping_object = None
        # add (requeue) list
        self.__add_list = []
        # remove list
        self.__del_list = []
        # skip a few filedescriptors
        d1, d2 = os.pipe()
        d3, d4 = os.pipe()
        self.__delete_hooks = {}
        # pipe-object for normal sockets
        self.__pipe_rt_read, self.__pipe_rt_write = os.pipe()
        self.__poll_obj.poll_register(self.__pipe_rt_read, POLL_IN)
        # pipe-object for ping stuff
        self.__pipe_ping_read, self.__pipe_ping_write = os.pipe()
        self.__poll_obj.poll_register(self.__pipe_ping_read, POLL_IN)
        # add (requeue) lock
        self.__add_lock = threading.RLock()
        # remove (delete) lock
        self.__del_lock = threading.RLock()
        self.__exit_st_flag, self.last_breakout_time = (None, None)
        self.set_new_message_format()
        self.set_verbose()
        self.set_max_calls(SO_OBJ_MAX_CALLS)
        self.__ext_keys_counter = 30000
    def set_max_calls(self, nc):
        self.__max_calls = nc
    def install_delete_hook(self, key, func):
        self.__delete_hooks[key] = func
    def set_verbose(self, vl=0):
        self.__verbosity = vl
    def get_verbose(self):
        return self.__verbosity
    def set_new_message_format(self, nmf=0):
        self.new_message_format = nmf
    def get_new_message_format(self):
        return self.new_message_format
    def start_thread(self):
        self.__exit_st_flag = threading.Semaphore()
        self.__exit_st_flag.acquire()
        self.stopped_st_flag = threading.Semaphore()
        self.stopped_st_flag.acquire()
        self.thread_object = threading.Thread(name = "%s_ns_step" % (self.__name), target=self.thread_code)
        self.thread_object.start()
        return self.thread_object
    def stop_thread(self):
        if self.__exit_st_flag:
            # wake-up signal
            self.log("pid %d: stopping socketserver-subthread named %s" % (os.getpid(), "%s_pst" % (self.__name)))
            self.__exit_st_flag.release()
            os.write(self.__pipe_rt_write, "1")
            self.stopped_st_flag.acquire()
            self.__exit_st_flag, self.stopped_st_flag = (None, None)
            os.close(self.__pipe_rt_read)
            os.close(self.__pipe_rt_write)
    def __del__(self):
        self.close()
    def close(self):
        self.stop_thread()
    def add_icmp_socket(self):
        sd = [so_part("l", "icmp_step", ["l"], None)]
        so = state_object("l", sd, icmp_sock_object())
        so.set_new_message_format(self.get_new_message_format(), 1)
        try:
            so.fileno()
        except:
            self.log_err("Cannot create raw-socket (not root?)")
        else:
            so.set_poll_object(self.__poll_obj)
            self.__ping_object = so
            self.add_object(so)
    def new_ping(self, target, key, num, timeout, req_queue, add_data=None, flood=0):
        if not self.__ping_object:
            self.add_icmp_socket()
        if self.__ping_object:
            self.__ping_object.state_machine.add_target_host(target, key, num, timeout, req_queue, add_data, flood)
            os.write(self.__pipe_ping_write, ".")
    def new_tcp_bind(self, queue_dict, (port, if_list, num_retries, listen_queue), add_data = None, timeout=None, ssl_context=None, protocoll=1, accept_hook=None):
        if ssl_context and not m2:
            return []
        if type(if_list) == type(""):
            if_list = [if_list]
        fn_list = []
        for bind_if in if_list:
            sd = [so_part("b", "bind_port", ["l", "b"], ((bind_if, port), num_retries), {"e" : "c"} ),
                  so_part("l", "listen"   , ["a"]     , listen_queue                                ),
                  so_part("a", "accept"   , ["a", "c"], self,                                       ),
                  so_part("c", "closesock", ["c"]     , 0.1                           , {"o" : "ok"})]
            so = state_object("b", sd, tcp_sock_object(), queue_dict, add_data)
            so.set_new_message_format(self.get_new_message_format())
            so.set_protocoll(protocoll)
            so.set_verbose(self.get_verbose())
            #so.set_verbose(1)
            if timeout:
                so.set_timeout(timeout)
            else:
                so.set_timeout(self.get_timeout())
            #so.set_verbose(1)
            if accept_hook == None:
                so.accept_hook = tcp_accept_hook
            else:
                so.accept_hook = accept_hook
            if ssl_context:
                so.ssl_context = ssl_context
                so.ssl = m2.ssl_new(so.ssl_context.ctx)
            self.add_object(so)
            fn_list.append(so.get_external_key())
        if len(fn_list) > 1:
            return fn_list
        else:
            return fn_list[0]
    def new_udp_bind(self, queue_dict, (port, if_list, num_retries, listen_queue), add_data=None, timeout=None, protocoll=0):
        if type(if_list) == type(""):
            if_list = [if_list]
        fn_list = []
        for bind_if in if_list:
            sd = [so_part("b", "bind_port", ["r"], ((bind_if, port), num_retries), {"e" : "ci"}),
                  so_part("r", "recvfrom" , ["r"], None                          , {"e" : "r"} ),
                  so_part("c", "closesock", ["c"], 0.1                           , {"o" : "ok"})]
            so = state_object("b", sd, udp_sock_object(), queue_dict, add_data)
            so.set_new_message_format(self.get_new_message_format())
            so.set_protocoll(protocoll)
            # timeout is always zero ?
            so.set_timeout(0)
            so.set_verbose(self.get_verbose())
            #so.set_verbose(1)
            self.add_object(so)
            fn_list.append(so.get_external_key())
        if len(fn_list) > 1:
            return fn_list
        else:
            return fn_list[0]
    def new_udp_send(self, queue_dict, (dest_host, dest_port, command), add_data=None, timeout=None, addit=1):
        # initiates a new connection
        sd = [so_part("b", "bind_port", ["s"]     , (("0.0.0.0", 0), 1), {"e" : "c"} , "er"),
              so_part("s", "sendto"   , ["c", "s"], ((dest_host, dest_port), command)      ),
              so_part("c", "closesock", ["c"]     , 0.1                , {"o" : "ok"}      )]
        so = state_object("b", sd, udp_sock_object(), queue_dict, add_data)
        so.set_new_message_format(self.get_new_message_format())
        so.set_verbose(self.get_verbose())
        #new_sock.set_verbose(1)
        if timeout:
            so.set_timeout(timeout)
        else:
            so.set_timeout(self.get_timeout())
        if addit:
            self.add_object(so)
        else:
            return so
    def new_udp_socket(self, queue_dict, add_data=None, timeout=None):
        # initiates a new connection
        sd = [so_part("b", "bind_port", ["r"], (("0.0.0.0", 0), 1), {"e" : "c"} ),
              so_part("r", "recvfrom" , ["r"], None                             ),
              so_part("c", "closesock", ["c"], 0.1                , {"o" : "ok"})]
        so = state_object("b", sd, udp_sock_object(), queue_dict, add_data)
        so.set_new_message_format(self.get_new_message_format())
        so.set_verbose(self.get_verbose())
        #new_sock.set_verbose(1)
        if timeout:
            so.set_timeout(timeout)
        else:
            so.set_timeout(0)
        self.add_object(so)
        return so.state_machine.socket
    def new_tcp_connection(self, queue_dict, (dest_host, dest_port, command), add_data=None, timeout=0, protocoll=1, ssl_context=None, bidirectional=0):
        if ssl_context and not m2:
            return
        # initiates a new connection
        sd = [so_part("b", "open_connection", ["s"]          , (dest_host, dest_port), {"e" : "c"} ),
              so_part("s", "send"           , ["r", "s"]     , command                             ),
              so_part("r", "recv"           , ["c", "r", "s"], None                  , {"c" : "s"} ),
              so_part("c", "closesock"      , ["c"]          , 0.1                   , {"o" : "ok"})]
        so = state_object("b", sd, tcp_sock_object(), queue_dict, add_data)
        so.set_new_message_format(self.get_new_message_format())
        so.set_protocoll(protocoll)
        if ssl_context:
            so.ssl_context = ssl_context
            so.ssl = m2.ssl_new(so.ssl_context.ctx)
        #print dest_host, dest_port
        so.set_verbose(self.get_verbose())
        if timeout is not None:
            so.set_timeout(timeout)
        else:
            so.set_timeout(self.get_timeout())
        #print len(self.__so_dict)
        self.add_object(so)
        return so
    def new_unix_domain_bind(self, queue_dict, (sock_name, sock_mode, num_retries, listen_queue), add_data=None, timeout=0, protocoll=1):
        sd = [so_part("b", "bind_port", ["r"]     , ((sock_name, sock_mode), num_retries), {"e" : "c"} ),
              so_part("r", "recv"     , ["r", "c"], None                                               ),
              so_part("c", "closesock", ["c"]     , None                                 , {"o" : "ok"})]
        so = state_object("b", sd, unix_sock_object(), queue_dict, add_data)
        so.set_new_message_format(self.get_new_message_format())
        so.set_protocoll(protocoll)
        so.set_timeout(timeout)
        so.set_verbose(self.get_verbose())
        self.add_object(so)
        return so
    def get_file_no(self, ext_key):
        return self.__ext_key_dict[ext_key]
    def wait_for_more(self, ext_key):
        return self.__so_dict[self.__ext_key_dict[ext_key]].wait_for_more()
    def set_result(self, ext_key, what):
        try:
            key = self.__ext_key_dict[ext_key]
        except KeyError:
            self.log_err("external key %d invalid" % (ext_key))
        else:
            so_obj = self.__so_dict.get(key, None)
            if so_obj:
                if hasattr(so_obj, "next_so_part"):
                    so_obj.next_so_part.set_args(what)
                    so_obj.waiting = 0
                    os.write(self.__pipe_rt_write, "%d " % (key))
                else:
                    self.log_err("no waiting_part for key %d (ext_key %d)" % (key,
                                                                              ext_key))
            else:
                self.log_err("key %d (from ext_key %d) has no associated so_obj" % (key,
                                                                                    ext_key))
    def delete_stream(self, ext_key):
        #print "*******",key, self.__so_dict[key].wait_for_more()
        try:
            key = self.__ext_key_dict[ext_key]
        except KeyError:
            self.log_err("external key %d invalid" % (ext_key))
        else:
            self.__del_lock.acquire()
            self.__del_list.append(key)
            self.__del_lock.release()
            os.write(self.__pipe_rt_write, "* ")
    def add_object(self, obj):
        if type(obj) != type([]):
            obj = [obj]
        # protect setting of ext_key_counter and adding with self.__add_lock
        self.__add_lock.acquire()
        for x in obj:
            x.set_external_key(self.__ext_keys_counter)
            self.__ext_keys_counter += 1
        self.__add_list.extend(obj)
        self.__add_lock.release()
        os.write(self.__pipe_rt_write, "- ")
        # cap ext_keys_counter
        self.__ext_keys_counter = self.__ext_keys_counter % 1000000
    def log(self, in_str, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_hook:
            self.__log_hook(in_str)
        else:
            syslog.syslog(syslog.LOG_INFO | syslog.LOG_USER, in_str)
    def log_err(self, in_str):
        if self.__err_log_hook:
            self.__err_log_hook(in_str)
        else:
            syslog.syslog(syslog.LOG_ERR | syslog.LOG_USER, in_str)
    def set_timeout(self, timeout=5):
        self.timeout = timeout
    def get_timeout(self):
        return self.timeout
    def thread_code(self):
        my_pid = os.getpid()
        if self.new_pid_hook:
            self.new_pid_hook(my_pid)
        my_name = threading.currentThread().getName()
        self.log("pid %d: step-subthread named %s is now awake" % (my_pid, my_name))
        self.step()
        self.stopped_st_flag.release()
        self.log("pid %d: step-subthread named %s exiting" % (my_pid, my_name))
    def step(self, breakout=0):
        while 1:
            # delete finished state_machines
            for key in [x for x, y in self.__so_dict.iteritems() if y.errnum or y.new_state == "ok"]:
                #print "del", key
                ext_key = self.__so_dict[key].get_external_key()
                if self.__so_dict[key].calls > self.__max_calls:
                    self.log_err("so_object with key %d (ext %d) had too many calls: %d > %d" % (key,
                                                                                                 ext_key,
                                                                                                 self.__so_dict[key].calls,
                                                                                                 self.__max_calls))
                    #print key, self.__so_dict[key].errnum, self.__so_dict[key].new_state, self.__so_dict[key].calls
                if self.__delete_hooks.has_key(ext_key):
                    self.__delete_hooks[ext_key](ext_key)
                    del self.__delete_hooks[ext_key]
                self.__poll_obj.poll_unregister(self.__so_dict[key].fileno())
                del self.__so_dict[key]
                try:
                    del self.__ext_key_dict[ext_key]
                except KeyError:
                    self.log_err("KeyError triggered while trying to remove key %s from ext_key_dict" % (str(ext_key)))
            act_time = time.time()
            #print self.__so_dict.keys(), act_time
            #print "*** LOOP "*10, act_time
            if breakout: 
                if not self.last_breakout_time or act_time >= self.get_timeout() + self.last_breakout_time or act_time < self.last_breakout_time:
                    self.last_breakout_time = act_time
                    break
                act_self_to = max(0., min(self.get_timeout(), (self.get_timeout() - (act_time - self.last_breakout_time))))
            else:
                act_self_to = self.get_timeout()
            do_select = True
            for key, act_so in self.__so_dict.iteritems():
                #print "**", key, act_so.act_reply
                select_local, remain_time = act_so.act_reply
                remain_time -= act_time
                if select_local or remain_time <= 0:
                    do_select = False
                    act_so.step()
                elif do_select:
                    act_self_to = min(act_self_to, remain_time)
            #print "do_select: %d" % (do_select)
            if do_select:
                # advance all in receive_list
                for key, poll_type in self.__poll_obj.poll(act_self_to * 1000):
                    if key == self.__pipe_rt_read:
                        ret = os.read(self.__pipe_rt_read, 6)
                        for rs in ret.split():
                            if rs == "-":
                                # check for new state-objects
                                self.__add_lock.acquire()
                                while self.__add_list:
                                    new_s_o = self.__add_list.pop(0)
                                    # add to dict
                                    self.__so_dict[new_s_o.fileno()] = new_s_o
                                    # add ext_key_lut
                                    self.__ext_key_dict[new_s_o.get_external_key()] = new_s_o.fileno()
                                    new_s_o.set_poll_object(self.__poll_obj)
                                    new_s_o.single_step()
                                self.__add_lock.release()
                            elif rs == "*":
                                self.__del_lock.acquire()
                                for d_key in self.__del_list:
                                    if self.__so_dict.has_key(d_key):
                                        ext_key = self.__so_dict[d_key].get_external_key()
                                        if self.__delete_hooks.has_key(ext_key):
                                            self.__delete_hooks[ext_key](ext_key)
                                            del self.__delete_hooks[ext_key]
                                        self.__poll_obj.poll_unregister(self.__so_dict[d_key].fileno())
                                        del self.__ext_key_dict[ext_key]
                                        del self.__so_dict[d_key]
                                self.__del_list = []
                                self.__del_lock.release()
                            else:
                                try:
                                    ret_i = int(rs)
                                except:
                                    pass
                                else:
                                    if self.__so_dict.has_key(ret_i):
                                        self.__so_dict[ret_i].step()
                    elif key == self.__pipe_ping_read:
                        ret = os.read(self.__pipe_ping_read, 5)
                        self.__ping_object.step()
                    else:
                        if poll_type & select.POLLERR:
                            self.log_err("key %d: poll_type is %s, setting error (actual state: %s)" % (self.__so_dict[key].get_external_key(),
                                                                                                        poll_flag_to_str(poll_type),
                                                                                                        self.__so_dict[key].act_so_part.get_func_name()))
                            self.__so_dict[key].set_error(FailMark, "error for %s in poll()" % (self.__so_dict[key].act_so_part.get_func_name()))
                            self.__so_dict[key].send_error_msg()
                        else:
                            if self.__so_dict.has_key(key):
                                self.__so_dict[key].step()
                            else:
                                self.log("Cannot step key %d (not in __so_dict)" % (key))
            if self.__exit_st_flag and self.__exit_st_flag.acquire(0):
                break
        
if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(-1)
