#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006,2007,2009,2010,2011 Andreas Lang-Nevyjel
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
""" classes for multiprocessing (using threading or multiprocessing) """

import sys
import thread
import threading
import Queue
import logging_tools
import time
import os
import signal
import traceback
import io_stream_helper
import multiprocessing
import process_tools
import pprint
import pickle
try:
    import zmq
    from txZMQ import ZmqSubConnection, ZmqFactory, ZmqEndpoint, ZmqConnection
    from twisted.internet import reactor, defer
except ImportError:
    zmq = None
    
# default stacksize
DEFAULT_STACK_SIZE = 2 * 1024 * 1024

# Exceptions
class my_error(Exception):
    def __init__(self, args):
        self.value = args
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return "my_exception: %s" % (str(self.value))

class term_error(my_error):
    def __init__(self, args):
        my_error.__init__(self, args)
    
class alarm_error(my_error):
    def __init__(self, args):
        my_error.__init__(self, args)
    
class stop_error(my_error):
    def __init__(self, args):
        my_error.__init__(self, args)
    
class int_error(my_error):
    def __init__(self, args):
        my_error.__init__(self, args)

class hup_error(my_error):
    def __init__(self, args):
        my_error.__init__(self, args)

# to avoid import loops
def get_except_info():
    return "%s (%s)" % (str(sys.exc_info()[0]),
                        str(sys.exc_info()[1]))

def get_act_thread_name():
    return threading.currentThread().getName()

# threads communicate via messages
# message format is (com_str, rest) or com_str for simple commands

class min_thread_obj(threading.Thread):
    def __init__(self, name, **args):
        threading.Thread.__init__(self, name=name, target=self._code)
        self.__thread_queue = Queue.Queue(1)
    def _code(self):
        time.sleep(60)
    def set_thread_pool(self, tp):
        pass
    def get_thread_queue(self):
        return self.__thread_queue
    def __setitem__(self, key, value):
        pass
    def __getitem__(self, key):
        return None

class thread_obj(threading.Thread):
    def __init__(self, name, **args):
        threading.Thread.__init__(self, name=name, target=self._code)
        self.name = name
        self.pid = os.getpid()
        self.__thread_pool = None
        self.__thread_queue = Queue.Queue(args.get("queue_size", 100))
        # exit queue
        self.__exit_queue = None
        # spool for thread_pool_messages
        self.__thread_pool_messages = []
        # flags
        self.__flags = {}
        # function table
        self.__func_table = {}
        # ignore calls
        self.__ignore_funcs = []
        # verbose
        self.__verbose = args.get("verbose", False)
        # wait for more messages if one processed (for gathering of messages)
        self.__gather_timeout    = args.get("gather_timeout"   , 0.)
        self.__total_gather_wait = args.get("total_gather_wait", 0.)
        # internal exit-function
        self.register_func("exit", self._exit_thread)
        # run flag
        self["run_flag"] = True
        # thread priority: when stopping threads start with the lowest priority and end with the highest
        self["priority"] = args.get("priority", 0)
        # is a busy-loop thread ?
        self._busy_loop_function = args.get("loop_function", None)
        self.set_min_loop_time()
    def getName(self):
        return self.name
    def has_key(self, key):
        return key in self.__flags
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def __getitem__(self, fn):
        return self.__flags[fn]
    def send_pool_message(self, what=None):
        if self.__thread_pool:
            if what is not None:
                self.__thread_pool_messages.append(what)
            if self.__thread_pool_messages:
                for mesg in self.__thread_pool_messages:
                    self.__thread_pool.get_own_queue().put(mesg)
                self.__thread_pool_messages = []
            self.__thread_pool.get_own_queue().put(what)
            self.any_message_send()
        else:
            self.__thread_pool_messages.append(what)
    def set_min_loop_time(self, lt=0):
        self.__min_loop_time = lt
    def get_thread_queue(self):
        return self.__thread_queue
    def set_thread_pool(self, tp):
        self.__thread_pool = tp
        self.zmq_context = self.__thread_pool.zmq_context
        if self.zmq_context:
            # rewrite to zmq-style queueing
            del self.__thread_queue
            new_q = self.zmq_context.socket(zmq.PULL)
            new_q.bind("ipc://%s" % (self.name))
            self.__thread_queue = new_q
            tp_queue = self.zmq_context.socket(zmq.PUSH)
            tp_queue.connect("ipc://%s" % (self.__thread_pool.get_own_queue_name()))
            self.__tp_queue = tp_queue
        self.send_pool_message()
    def get_thread_pool(self):
        return self.__thread_pool
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "thread %s %s: %s" % (self.getName(),
                                    logging_tools.get_log_level_str(log_level),
                                    what)
    def register_func(self, f_str, f_call):
        self.__func_table[f_str] = f_call
    def add_ignore_func(self, f_str):
        if type(f_str) != type([]):
            f_str = [f_str]
        self.__ignore_funcs.extend(f_str)
    def _code(self):
        # call thread_init (set pid and stuff)
        self.thread_init()
        self.thread_running()
        self.loop_start()
        self.thread_loop()
        self.loop_end()
        self.thread_exit()
    def _exit_thread(self, ret_queue=None, **kwargs):
        # ret_queue is None for zmq-based threads
        self.__exit_queue = ret_queue
        self.log("exit_thread called for thread %s (pid=%d)" % (self.name, self.pid))
        self["run_flag"] = False
    def thread_exit(self):
        if self.__exit_queue:
            self.__exit_queue.put(("exiting", (self.getName(), self.pid)))
        elif self.zmq_context:
            self.send_pool_message(["exiting", "%d" % (self.pid)])
        else:
            self.log("no exit_queue defined, strange", logging_tools.LOG_LEVEL_WARN)
    def optimize_message_list(self, in_list):
        return in_list
    def thread_init(self):
        self.log("thread_init (%s, pid=%d)" % (self.name, self.pid))
    def thread_running(self):
        pass
    def loop_start(self):
        self.log("thread_loop_start (%s, pid=%d)" % (self.name, self.pid))
    def loop_end(self):
        self.log("thread_loop_end (%s, pid=%d)" % (self.name, self.pid))
    def any_message_received(self):
        pass
    def any_message_send(self):
        pass
    def _show_recv_messages(self, mes_list):
        for mes in mes_list:
            if type(mes) == type(()):
                mes, in_stuff = mes
                self.log("SRM: received message %s (with options)" % (mes))
            else:
                self.log("SRM: received message %s" % (mes))
    def _zmq_loop_function(self):
        cur_q = self.get_thread_queue()
        while self["run_flag"]:
            a = cur_q.recv_pyobj()
            src_thread = a.pop(0)
            mes_type = a.pop(0)
            self.__func_table[mes_type](*a, src_thread=src_thread)
            #self.send_pool_message(["log_recv", "ok:::super"])
    def inner_loop(self, force_wait=False):
        # to be called from busy-loop threads like snmp trap sinks
        mes_list, mes, gather_messages, gather_waited = ([], True, self.__gather_timeout > 0, 0.)
        total_gather_wait = self.__total_gather_wait or self.__gather_timeout * 5
        while mes:
            mes = None
            try:
                mes = self.__thread_queue.get_nowait()
            except Queue.Empty:
                if not mes_list and (not self._busy_loop_function or force_wait):
                    # nothing received so far, wait for message if no min_loop_time is set
                    if self.__min_loop_time:
                        try:
                            mes = self.__thread_queue.get(True, self.__min_loop_time)
                        except Queue.Empty:
                            mes = None
                    else:
                        mes = self.__thread_queue.get()
                else:
                    # something received so far
                    if gather_messages and total_gather_wait > 0:
                        time.sleep(self.__gather_timeout)
                        total_gather_wait -= self.__gather_timeout
                        try:
                            mes = self.__thread_queue.get_nowait()
                        except Queue.Empty:
                            mes = None
                        else:
                            pass
                    else:
                        # process received messages
                        mes = None
            if mes is not None:
                if type(mes) == type([]):
                    mes_list.extend(mes)
                else:
                    mes_list.append(mes)
        self.any_message_received()
        if mes_list and self.__verbose:
            self._show_recv_messages(mes_list)
        mes_list = self.optimize_message_list(mes_list)
        for mes in mes_list:
            if type(mes) == type(()):
                mes, in_stuff = mes
                if mes in self.__func_table:
                    self.__func_table[mes](in_stuff)
                else:
                    if mes not in self.__ignore_funcs:
                        try:
                            add_data_str = str(in_stuff)
                        except:
                            add_data_str = "<error generating add_data_str in threading_tools.py>"
                        self.log("Unknown function %s (add_data: %s)" % (str(mes), len(add_data_str) > 1024 and "(1024 bytes of %d): %s" % (len(add_data_str), add_data_str[:1024]) or add_data_str),
                                 logging_tools.LOG_LEVEL_ERROR)
                in_stuff = None
            else:
                if mes in self.__func_table:
                    self.__func_table[mes]()
                else:
                    if mes not in self.__ignore_funcs:
                        self.log("Unknown function %s" % (str(mes)),
                                 logging_tools.LOG_LEVEL_ERROR)
            mes = None
        return mes_list
    def thread_loop(self):
        if self.zmq_context:
            self._zmq_loop_function()
        else:
            while self["run_flag"]:
                mes_list = self.inner_loop()
                if self._busy_loop_function and not mes_list:
                    self._busy_loop_function()
                # clear message_list
                mes_list = []
                
class thread_pool(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.pid = os.getpid()
        self.__thread = threading.currentThread()
        self.__thread.setName(name)
        self.__queues = {}
        self.__queue_buffer = {}
        self.__threads = {}
        if zmq and kwargs.get("zmq", False):
            self.zmq_context = zmq.Context()
            self.poller = zmq.Poller()
            self.thread_loop = self.zmq_thread_loop
            self.__loop_granularity = kwargs.get("loop_granularity", 1000)
            self.__timer_list, self.__next_timeout = ([], None)
        else:
            self.zmq_context = None
            self.poller = None
            self.thread_loop = self.queue_thread_loop
        self.__my_queue_name = kwargs.get("internal_queue_name", "internal")
        self.add_queue(self.__my_queue_name, 20)
        self.__sub_threads_running = 0
        # blocking main-loop
        self.__blocking_loop = kwargs.get("blocking_loop", True)
        # wait timeout
        self.__queue_get_timeout = kwargs.get("queue_get_timeout", None)
        # verbose
        self.__verbose = kwargs.get("verbose", False)
        # ignore calls
        self.__ignore_funcs = []
        # function table
        self.__func_table = {}
        # internal exit-function for terminating sub-threads
        if self.zmq_context:
            self.register_func("exiting", self._thread_exit_zmq)
        else:
            self.register_func("exiting", self._thread_exit)
        # flags for exiting / loop-control
        self.__flags = {"run_flag"                  : True,
                        "signal_handlers_installed" : False,
                        "exit_requested"            : False}
        self.__exception_table = {}
        self.thread_init()
        self.set_stack_size(kwargs.get("stack_size", DEFAULT_STACK_SIZE))
    def get_name(self):
        return self.name
    def __getitem__(self, fn):
        return self.__flags[fn]
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def register_timer(self, cb_func, timeout, **kwargs):
        s_time = time.time()
        if not kwargs.get("instant", False):
            s_time = s_time + timeout
        self.__timer_list.append((timeout, s_time, cb_func))
        self.__next_timeout = min([last_to for cur_to, last_to, cb_func in self.__timer_list])
    def _handle_timer(self, cur_time):
        new_tl, t_funcs = ([], [])
        for cur_to, t_time, cb_func in self.__timer_list:
            if t_time <= cur_time:
                t_funcs.append(cb_func)
                new_tl.append((cur_to, t_time + cur_to, cb_func))
            else:
                new_tl.append((cur_to, t_time, cb_func))
        self.__timer_list = new_tl
        self.__next_timeout = min([last_to for cur_to, last_to, cb_func in self.__timer_list])
        for t_func in t_funcs:
            t_func()
    def add_queue(self, q_name, q_len):
        if q_name in self.__queues:
            new_queue = self.__queues[q_name]
        else:
            if self.zmq_context:
                new_queue = self.zmq_context.socket(zmq.PULL)
                new_queue.bind("inproc://%s" % (q_name))
                self.poller_handler = {}
                time.sleep(0.1)
                self.register_poller(new_queue, zmq.POLLIN, self._tp_message_received)
            else:
                new_queue = Queue.Queue(q_len)
            self.__queues[q_name] = new_queue
        return new_queue
    def register_poller(self, zmq_socket, sock_type, callback):
        self.poller_handler[(zmq_socket, sock_type)] = callback
        self.poller.register(zmq_socket, sock_type)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "thread_pool %s %s: %s" % (self.get_name(),
                                         logging_tools.get_log_level_str(log_level),
                                         what)
    def add_ignore_func(self, f_str):
        if type(f_str) != type([]):
            f_str = [f_str]
        self.__ignore_funcs.extend(f_str)
    def set_stack_size(self, s_size):
        try:
            thread.stack_size(s_size)
        except:
            self.log("Error setting stack_size to %s: %s" % (logging_tools.get_size_str(s_size, long_version=True),
                                                             get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("setting stack_size to %s" % (logging_tools.get_size_str(s_size, long_version=True)))
    def get_own_queue(self):
        return self.__queues[self.__my_queue_name]
    def get_own_queue_name(self):
        return self.__my_queue_name
    def get_queue(self, q_name):
        return self.__queues[q_name]
    def add_thread(self, t_obj, **kwargs):
        # add a thread_object to the thread_pool
        if t_obj.getName() in self.__threads:
            self.log("thread named '%s' already present" % (t_obj.getName()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            return None
        else:
            self.__threads[t_obj.getName()] = t_obj
            t_obj.set_thread_pool(self)
            if self.zmq_context:
                thread_queue = self.zmq_context.socket(zmq.PUSH)
                thread_queue.connect("inproc://%s" % (t_obj.getName()))
                self.__queues[t_obj.getName()] = thread_queue
            else:
                self.__queues[t_obj.getName()] = t_obj.get_thread_queue()
            t_obj["started"] = False
            t_obj["stopped"] = False
            if kwargs.get("start_thread", False):
                self.start_thread(t_obj.getName())
            if self.zmq_context:
                self._flush_thread_buffers(t_obj.getName())
                return self.__queues[t_obj.getName()]
            else:
                return t_obj
    def send_to_thread(self, t_thread, m_type, *args, **kwargs):
        if t_thread not in self.__queues:
            self.__queue_buffer.setdefault(t_thread, []).append((m_type, args))
        else:
            if t_thread in self.__queue_buffer:
                self._flush_thread_buffers(t_thread)
            self.__queues[t_thread].send_pyobj([self.name, m_type] + list(args))
    def _flush_thread_buffers(self, t_thread):
        if t_thread in self.__queue_buffer:
            for b_m_type, b_args in self.__queue_buffer[t_thread]:
                self.__queues[t_thread].send_pyobj([self.name, b_m_type] + list(b_args))
            del self.__queue_buffer[t_thread]
    def get_thread_names(self):
        return self.__threads.keys()
    def get_thread(self, t_name):
        return self.__threads[t_name]
    def start_thread(self, t_name):
        if not self.__threads[t_name]["started"]:
            self.log("starting thread %s" % (t_name))
            self.__threads[t_name]["started"] = True
            self.__threads[t_name].start()
            self.__sub_threads_running += 1
    def get_thread_queue_info(self):
        return dict([(q_n, (q_q.maxsize, q_q.qsize())) for q_n, q_q in self.__queues.iteritems()])
    def stop_thread(self, t_name):
        if not self.__threads[t_name]["stopped"]:
            self.log("sending exit to thread %s" % (t_name))
            self.__threads[t_name]["stopped"] = True
            if self.zmq_context:
                self.send_to_thread(t_name, "exit")
            else:
                self.__queues[t_name].put(("exit", self.get_queue(self.__my_queue_name)))
    def num_threads_running(self, only_sub_threads=True):
        if only_sub_threads:
            return len([True for t in self.__threads.values() if t.isAlive()])
        else:
            return len([True for t in self.__threads.values() + [self.__thread] if t.isAlive()])
    def num_threads(self, only_sub_threads=True):
        if only_sub_threads:
            return len(self.__threads.keys())
        else:
            return len(self.__threads.keys()) + 1
    def _thread_exit_zmq(self, t_name, t_pid):
        t_pid = int(t_pid[0])
        self._thread_exit((t_name, t_pid))
    def _thread_exit(self, (t_name, t_pid)):
        self.__threads[t_name]["started"] = False
        self.__threads[t_name]["stopped"] = False
        self.__sub_threads_running -= 1
        self.log("thread %s exited" % (t_name))
        # remove thread from structures
        del self.__threads[t_name]
        del self.__queues[t_name]
        # for subclassing
        self.thread_exited(t_name, t_pid)
    def thread_exited(self, t_name, t_pid):
        # dummy function, called when a thread exits
        pass
    def _handle_exception(self):
        exc_info = sys.exc_info()
        self._exc_info = exc_info
        # FIXME
        exc_type = str(exc_info[0]).split(".")[-1].split("'")[0]
        if exc_type in self.__exception_table:
            self.log("caught known exception %s" % (exc_type),
                     logging_tools.LOG_LEVEL_WARN)
            self.__exception_table[exc_type](exc_info[1])
        else:
            except_info = get_except_info()
            self.log("caught unknown exception %s (%s), traceback" % (exc_type, except_info),
                     logging_tools.LOG_LEVEL_CRITICAL)
            tb = self._exc_info[2]
            out_lines = ["Exception in thread '%s'" % (self.name)]
            for file_name, line_no, name, line in traceback.extract_tb(tb):
                self.log("File '%s', line %d, in %s" % (file_name, line_no, name),
                         logging_tools.LOG_LEVEL_CRITICAL)
                out_lines.append("File '%s', line %d, in %s" % (file_name, line_no, name))
                if line:
                    self.log(" - %d : %s" % (line_no, line),
                             logging_tools.LOG_LEVEL_CRITICAL)
                    out_lines.append(" - %d : %s" % (line_no, line))
            out_lines.append(except_info)
            # write to logging-server
            #err_h = io_stream_helper.io_stream("/var/lib/logging-server/py_err")
            #err_h.write("\n".join(out_lines))
            #err_h.close()
            self.log("waiting for 1 second",
                     logging_tools.LOG_LEVEL_WARN)
            time.sleep(1)
    def register_func(self, f_str, f_call):
        self.__func_table[f_str] = f_call
    def register_exception(self, exc_type, call):
        self.__exception_table[exc_type] = call
    def optimize_message_list(self, in_list):
        return in_list
    def _sig_handler(self, signum, frame):
        sig_str = "got signal %d" % (signum)
        self.log(sig_str)
        if signum == signal.SIGTERM:
            raise term_error, sig_str
        elif signum == signal.SIGINT:
            raise int_error, sig_str
        elif signum == signal.SIGTSTP:
            raise stop_error, sig_str
        elif signum == signal.SIGALRM:
            raise alarm_error, sig_str
        elif signum == signal.SIGHUP:
            raise hup_error, sig_str
        else:
            raise
    def install_signal_handlers(self):
        if not self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = True
            self.log("installing signal handlers")
            self.__orig_sig_handlers = {}
            for sig_num in [signal.SIGTERM,
                            signal.SIGINT,
                            signal.SIGTSTP,
                            signal.SIGALRM,
                            signal.SIGHUP]:
                self.__orig_sig_handlers[sig_num] = signal.signal(sig_num, self._sig_handler)
    def uninstall_signal_handlers(self):
        if self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = False
            self.log("uninstalling signal handlers")
            for sig_num, orig_h in self.__orig_sig_handlers.iteritems():
                signal.signal(sig_num, orig_h)
    def thread_init(self):
        self.log("thread_init %d" % (os.getpid()))
    def loop_start(self):
        self.log("thread_loop_start %d" % (os.getpid()))
    def loop_end(self):
        self.log("thread_loop_end %d" % (os.getpid()))
    def thread_loop_post(self):
        pass
    def _show_recv_messages(self, mes_list):
        for mes in mes_list:
            if type(mes) == type(()):
                mes, in_stuff = mes
                self.log("SRM: received message %s (with options)" % (mes))
            else:
                self.log("SRM: received message %s" % (mes))
    def _tp_message_received(self, zmq_socket):
        mes_parts = zmq_socket.recv_pyobj() 
        src_thread = mes_parts.pop(0)
        msg_type = mes_parts.pop(0)
        if msg_type in self.__func_table:
            self.__func_table[msg_type](src_thread, mes_parts)
        else:
            self.log("unknown msg_type '%s' from src_thread %s" % (msg_type, src_thread),
                     logging_tools.LOG_LEVEL_ERROR)
    def zmq_thread_loop(self):
        self["loop_start_called"] = False
        self.install_signal_handlers()
        excepted = True
        while excepted:
            try:
                # call loop_start for first iteration
                if not self["loop_start_called"]:
                    self["loop_start_called"] = True
                    self.loop_start()
                while self["run_flag"]:
                    if self["exit_requested"]:
                        self.stop_running_threads()
                    try:
                        socks = dict(self.poller.poll(timeout=self.__loop_granularity))
                    except:
                        raise
                    for sock, c_type in socks.iteritems():
                        if (sock, c_type) in self.poller_handler:
                            self.poller_handler[(sock, c_type)](sock)
                        else:
                            print "???"
                    cur_time = time.time()
                    if self.__next_timeout and cur_time > self.__next_timeout:
                        self._handle_timer(cur_time)
                    if self["exit_requested"] and not self.__sub_threads_running:
                        self.log("loop exit")
                        self["run_flag"] = False
                self.loop_end()
                excepted = False
            except:
                print "he"
                self._handle_exception()
        self.uninstall_signal_handlers()
        self.thread_loop_post()
    def queue_thread_loop(self):
        self["loop_start_called"] = False
        self.install_signal_handlers()
        excepted = True
        while excepted:
            try:
                # call loop_start for first iteration
                if not self["loop_start_called"]:
                    self["loop_start_called"] = True
                    self.loop_start()
                my_queue = self.get_queue(self.__my_queue_name)
                while self["run_flag"]:
                    if self["exit_requested"]:
                        self.stop_running_threads()
                    mes_list, mes = ([], True)
                    while mes:
                        mes = None
                        try:
                            mes = my_queue.get_nowait()
                        except Queue.Empty:
                            if not mes_list:
                                if self.__blocking_loop:
                                    if self.__queue_get_timeout:
                                        try:
                                            mes = my_queue.get(True, self.__queue_get_timeout)
                                        except Queue.Empty:
                                            mes = None
                                    else:
                                        mes = my_queue.get()
                                else:
                                    mes = None
                            else:
                                mes = None
                        if mes is not None:
                            if type(mes) == type([]):
                                mes_list.extend(mes)
                            else:
                                mes_list.append(mes)
                    if mes_list:
                        if self.__verbose:
                            self._show_recv_messages(mes_list)
                        for mes in mes_list:
                            if type(mes) == type(()):
                                mes, in_stuff = mes
                                if mes in self.__func_table:
                                    self.__func_table[mes](in_stuff)
                                else:
                                    if mes not in self.__ignore_funcs:
                                        try:
                                            add_data_str = str(in_stuff)
                                        except:
                                            add_data_str = "<error generating add_data_str in threading_tools.py>"
                                        self.log("Unknown function %s (add_data: %s)" % (str(mes), len(add_data_str) > 1024 and "(1024 bytes of %d): %s" % (len(add_data_str), add_data_str[:1024]) or add_data_str),
                                                 logging_tools.LOG_LEVEL_ERROR)
                                in_stuff = None
                            else:
                                if mes in self.__func_table:
                                    self.__func_table[mes]()
                                else:
                                    if mes not in self.__ignore_funcs:
                                        self.log("Unknown function %s" % (str(mes)),
                                                 logging_tools.LOG_LEVEL_ERROR)
                            mes = None
                    elif not self.__blocking_loop:
                        self.loop_function()
                    # check for loop-end
                    if self["exit_requested"] and not self.__sub_threads_running:
                        self.log("loop exit")
                        self["run_flag"] = False
                # call loop_end
                self.loop_end()
                excepted = False
            except:
                self._handle_exception()
        self.uninstall_signal_handlers()
        self.thread_loop_post()
    def loop_function(self):
        print "_dummy_loop_function(), sleeping for 10 seconds"
        time.sleep(10)
    def stop_running_threads(self):
        int_queue = self.get_queue(self.__my_queue_name)
        pri_dict = {}
        for key, value in self.__threads.iteritems():
            pri_dict.setdefault(value["priority"], []).append(key)
        # flag: any threads stopped in previous priorities, all threads deads in previous priorities
        act_threads_stopped, prev_threads_dead = (False, True)
        # iterate over priorities
        for pri in sorted(pri_dict.keys()):
            # only loop if all threads in lower priority groups are dead and no signals were sent to lower pri groups
            if prev_threads_dead and not act_threads_stopped:
                thread_list = pri_dict[pri]
                for t_name in thread_list:
                    t_stuff = self.__threads[t_name]
                    if t_stuff["started"] and not t_stuff["stopped"]:
                        act_threads_stopped = True
                        # check if thread is alive
                        if t_stuff.isAlive():
                            self.stop_thread(t_name)
                            prev_threads_dead = False
                        else:
                            self.log("Thread %s seams to be dead" % (t_name),
                                     logging_tools.LOG_LEVEL_ERROR)
                            self._thread_exit((t_name, 0))
                    elif t_stuff.isAlive():
                        # thread still running
                        prev_threads_dead = False
    def wait_for_all_threads_to_finish(self, timeout=1.0):
        while len(threading.enumerate()) > 1:
            time.sleep(timeout)
    def __repr__(self):
        return "thread_pool %s, %s, %s" % (self.name,
                                           logging_tools.get_plural("thread", len(self.__threads.keys())),
                                           logging_tools.get_plural("queue", len(self.__queues.keys())))

class tz_pull_connection(ZmqConnection):
    socketType = zmq.core.constants.PULL
    def messageReceived(self, message):
        """
        Called on incoming message from ZeroMQ.

        @param message: message data
        """
        if len(message) == 2:
            # compatibility receiving of tag as first part
            # of multi-part message
            self.gotMessage(message[1], message[0])
        else:
            self.gotMessage(*reversed(message[0].split('\0', 1)))
    def connectionLost(self, reason):
        # catch connection lost
        pass
    
class tz_factory(object):
    reactor = reactor
    ioThreads = 1
    lingerPeriod = 1
    def __init__(self, context):
        self.connections = set()
        self.context = context
    def __repr__(self):
        return "ZmqFactory()"
    def shutdown(self):
        """
        Shutdown factory.

        This is shutting down all created connections
        and terminating ZeroMQ context.
        """
        for connection in self.connections.copy():
            connection.shutdown()
        self.connections = None
        self.context.term()
        self.context = None
    def registerForShutdown(self):
        """
        Register factory to be automatically shut down
        on reactor shutdown.
        """
        reactor.addSystemEventTrigger('during', 'shutdown', self.shutdown)
        
class process_obj(multiprocessing.Process):
    def __init__(self, name, **kwargs):
        multiprocessing.Process.__init__(self, target=self._code, name=name)
        # flags
        self.__flags = {}
        # function table
        self.__func_table = {}
        # ignore calls
        self.__ignore_funcs = []
        # verbose
        self.__verbose = kwargs.get("verbose", False)
        # internal exit-function
        self.register_func("exit", self._exit_process)
        # run flag
        # process priority: when stopping processes start with the lowest priority and end with the highest
        self["priority"] = kwargs.get("priority", 0)
    @property
    def twisted(self):
        return self.__twisted
    @twisted.setter
    def twisted(self, flag):
        # flag if runs a twisted reactor
        self.__twisted = flag
    @property
    def global_config(self):
        return self.__global_config
    @global_config.setter
    def global_config(self, g_conf):
        self.__global_config = g_conf
    def set_process_pool(self, p_pool):
        self.__process_pool = p_pool
    def getName(self):
        return self.name
    #def has_key(self, key):
    #    return key in self.__flags
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def __getitem__(self, fn):
        return self.__flags[fn]
    def send_to_socket(self, t_socket, data):
        t_socket.send_pyobj([self.name, self.pid] + data)
    def send_pool_message(self, *args):
        self.__pp_queue.send_pyobj([self.name, self.pid] + list(args))
    def _init_sockets(self):
        self.zmq_context = zmq.Context()
        if self.__twisted:
            my_factory = tz_factory(self.zmq_context)
            new_q = tz_pull_connection(my_factory, ZmqEndpoint("bind", process_tools.get_zmq_ipc_name(self.name)))
            new_q.gotMessage = self._recv_message
        else:
            new_q = self.zmq_context.socket(zmq.PULL)
            process_tools.bind_zmq_socket(new_q, process_tools.get_zmq_ipc_name(self.name))
            #new_q.setsockopt(zmq.SNDBUF, 65536)
            #new_q.setsockopt(zmq.RCVBUF, 65536)
            #new_q.setsockopt(zmq.HWM, 10)
        self.__process_queue = new_q
        pp_queue = self.zmq_context.socket(zmq.PUSH)
        pp_queue.connect(self.__process_pool.queue_name)
        self.__pp_queue = pp_queue
        # flush pool
        self.send_pool_message("process_start")
    def _close_sockets(self):
        # wait for the last commands to settle
        time.sleep(0.5)
        if not self.__twisted:
            self.__process_queue.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "process %s (%d) %s: %s" % (self.name,
                                          self.pid,
                                          logging_tools.get_log_level_str(log_level),
                                          what)
    def register_func(self, f_str, f_call):
        self.__func_table[f_str] = f_call
    def add_ignore_func(self, f_str):
        if type(f_str) != type([]):
            f_str = [f_str]
        self.__ignore_funcs.extend(f_str)
    def _install_signal_handlers(self):
        # ignore all signals
        for sig_num in [signal.SIGTERM,
                        signal.SIGINT,
                        signal.SIGTSTP,
                        signal.SIGALRM,
                        signal.SIGHUP]:
            signal.signal(sig_num, signal.SIG_IGN)
    def _code(self):
        self["run_flag"] = True
        threading.currentThread().setName(self.name)
        self._install_signal_handlers()
        self._init_sockets()
        # call process_init (set pid and stuff)
        self.process_init()
        self.process_running()
        self.loop_start()
        self.loop()
        self.loop_end()
        self.process_exit()
        self._close_sockets()
    def connect_to_socket(self, name):
        cur_socket = self.zmq_context.socket(zmq.PUSH)
        cur_socket.connect(process_tools.get_zmq_ipc_name(name))
        return cur_socket
    def _exit_process(self, **kwargs):
        self.log("exit_process called for process %s (pid=%d)" % (self.name, self.pid))
        self["run_flag"] = False
        if self.__twisted:
            reactor.stop()
    def process_exit(self):
        self.send_pool_message("process_exit")
    #def optimize_message_list(self, in_list):
    #    return in_list
    def process_init(self):
        self.log("process_init (%s, pid=%d)" % (self.name, self.pid))
    def process_running(self):
        pass
    def loop_start(self):
        self.log("process_loop_start (%s, pid=%d)" % (self.name, self.pid))
    def loop_end(self):
        self.log("process_loop_end (%s, pid=%d)" % (self.name, self.pid))
    def _recv_message(self, *args):
        """ receive message from self.__process_queue in twisted mode """
        mes_parts = pickle.loads("\000".join(reversed(args)))
        self._handle_message(mes_parts)
    def any_message_received(self):
        pass
    def _handle_message(self, cur_mes):
        src_process = cur_mes.pop(0)
        src_pid = cur_mes.pop(0)
        mes_type = cur_mes.pop(0)
        if mes_type in self.__func_table:
            self.__func_table[mes_type](*cur_mes, src_pid=src_pid, src_process=src_process)
            self.any_message_received()
        else:
            self.log("unknown message type '%s' from %s (%d)" % (
                mes_type,
                src_process,
                src_pid),
                     logging_tools.LOG_LEVEL_ERROR)
    def loop(self):
        if self.__twisted:
            reactor.run(installSignalHandlers=False)
        else:
            cur_q = self.__process_queue
            while self["run_flag"]:
                try:
                    cur_mes = cur_q.recv_pyobj()
                    self._handle_message(cur_mes)
                except:
                    print "process_obj.loop() %s: %s" % (self.name,
                                                         process_tools.get_except_info())
                    raise

class process_pool(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.pid = os.getpid()
        self.__sockets = {}
        self.__socket_buffer = {}
        self.__processes = {}
        self.zmq_context = zmq.Context()
        self.poller = zmq.Poller()
        self.__loop_granularity = kwargs.get("loop_granularity", 1000)
        self.__timer_list, self.__next_timeout = ([], None)
        self.queue_name = process_tools.get_zmq_ipc_name("internal")
        self.add_zmq_socket(self.queue_name)
        self.__processes_running = 0
        # blocking main-loop
        self.__blocking_loop = kwargs.get("blocking_loop", True)
        # wait timeout
        self.__queue_get_timeout = kwargs.get("queue_get_timeout", None)
        # verbose
        self.__verbose = kwargs.get("verbose", False)
        # ignore calls
        self.__ignore_funcs = []
        # function table
        self.__func_table = {}
        # internal exit-function for terminating processes
        self.register_func("process_exit", self._process_exit_zmq)
        self.register_func("process_start", self._process_start_zmq)
        # flags for exiting / loop-control
        self.__flags = {"run_flag"                  : True,
                        "signal_handlers_installed" : False,
                        "exit_requested"            : False}
        self.__exception_table = {}
        self.process_init()
        self.set_stack_size(kwargs.get("stack_size", DEFAULT_STACK_SIZE))
        self.__processes_stopped = set()
    def renice(self, nice_level=16):
        try:
            os.nice(self.pid)
        except:
            self.log("cannot renice pid %d to %d: %s" % (self.pid,
                                                         nice_level,
                                                         process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("reniced pid %d to %d" % (self.pid, nice_level))
    def get_name(self):
        return self.name
    def __getitem__(self, fn):
        return self.__flags[fn]
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def register_timer(self, cb_func, timeout, **kwargs):
        s_time = time.time()
        if not kwargs.get("instant", False):
            s_time = s_time + timeout
        self.__timer_list.append((timeout, s_time, cb_func))
        self.__next_timeout = min([last_to for cur_to, last_to, cb_func in self.__timer_list])
    def _handle_timer(self, cur_time):
        new_tl, t_funcs = ([], [])
        for cur_to, t_time, cb_func in self.__timer_list:
            if t_time <= cur_time:
                t_funcs.append(cb_func)
                new_tl.append((cur_to, t_time + cur_to, cb_func))
            else:
                new_tl.append((cur_to, t_time, cb_func))
        self.__timer_list = new_tl
        self.__next_timeout = min([last_to for cur_to, last_to, cb_func in self.__timer_list])
        for t_func in t_funcs:
            t_func()
    def add_zmq_socket(self, q_name):
        if q_name in self.__sockets:
            zmq_socket = self.__sockets[q_name]
        else:
            zmq_socket = self.zmq_context.socket(zmq.PULL)
            process_tools.bind_zmq_socket(zmq_socket, q_name)
            #zmq_socket.setsockopt(zmq.SNDBUF, 65536)
            #zmq_socket.setsockopt(zmq.RCVBUF, 65536)
            #zmq_socket.setsockopt(zmq.HWM, 10)
            self.poller_handler = {}
            self.register_poller(zmq_socket, zmq.POLLIN, self._tp_message_received)
            self.__sockets[q_name] = zmq_socket
        return zmq_socket
    def register_poller(self, zmq_socket, sock_type, callback):
        self.poller_handler[(zmq_socket, sock_type)] = callback
        self.poller.register(zmq_socket, sock_type)
    def unregister_poller(self, zmq_socket, sock_type):
        self.poller.unregister(zmq_socket)
        del self.poller_handler[(zmq_socket, sock_type)]
        zmq_socket.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "process_pool %s (%d) %s: %s" % (self.get_name(),
                                               os.getpid(),
                                               logging_tools.get_log_level_str(log_level),
                                               what)
    def add_ignore_func(self, f_str):
        if type(f_str) != type([]):
            f_str = [f_str]
        self.__ignore_funcs.extend(f_str)
    def set_stack_size(self, s_size):
        try:
            thread.stack_size(s_size)
        except:
            self.log("Error setting stack_size to %s: %s" % (logging_tools.get_size_str(s_size, long_version=True),
                                                             get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("setting stack_size to %s" % (logging_tools.get_size_str(s_size, long_version=True)))
    def add_process(self, t_obj, **kwargs):
        # add a process_object to the process_pool
        if t_obj.getName() in self.__processes:
            self.log("process named '%s' already present" % (t_obj.getName()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            return None
        else:
            t_obj.set_process_pool(self)
            self.__processes[t_obj.getName()] = t_obj
            process_queue = self.zmq_context.socket(zmq.PUSH)
            process_queue.connect(process_tools.get_zmq_ipc_name(t_obj.getName()))
            #process_queue.setsockopt(zmq.SNDBUF, 65536)
            #process_queue.setsockopt(zmq.RCVBUF, 65536)
            #process_queue.setsockopt(zmq.HWM, 10)
            self.__sockets[t_obj.getName()] = process_queue
            t_obj.twisted = kwargs.get("twisted", False)
            # set additional attributes
            for key in [sub_key for sub_key in sorted(kwargs.keys()) if sub_key not in ["twisted", "start"]]:
                self.log("setting attribute '%s' for %s" % (key, t_obj.getName()))
                setattr(t_obj, key, kwargs[key])
            if kwargs.get("start", False):
                self.start_process(t_obj.getName())
            self._flush_process_buffers(t_obj.getName())
            return self.__sockets[t_obj.getName()]
    def send_to_process(self, t_process, m_type, *args, **kwargs):
        """ send message to target_process, type is m_type """
        if t_process not in self.__sockets:
            self.__socket_buffer.setdefault(t_process, []).append((m_type, list(args)))
        else:
            if t_process in self.__socket_buffer:
                self._flush_process_buffers(t_process)
            self.__sockets[t_process].send_pyobj([self.name, self.pid, m_type] + list(args))
    def _flush_process_buffers(self, t_process):
        if t_process in self.__socket_buffer:
            for b_m_type, b_args in self.__socket_buffer[t_process]:
                self.__sockets[t_process].send_pyobj([self.name, self.pid, b_m_type] + list(b_args))
            del self.__socket_buffer[t_process]
    #def get_thread_names(self):
    #    return self.__processes.keys()
    def get_process(self, p_name):
        return self.__processes[p_name]
    def start_process(self, p_name):
        if not self.__processes[p_name].is_alive():
            self.log("starting process %s" % (p_name))
            self.__processes[p_name].start()
            self.__processes_running += 1
    #def get_thread_queue_info(self):
    #    return dict([(q_n, (q_q.maxsize, q_q.qsize())) for q_n, q_q in self.__queues.iteritems()])
    def stop_process(self, p_name):
        if self.__processes[p_name].is_alive():
            self.log("sending exit to process %s" % (p_name))
            self.send_to_process(p_name, "exit")
    #def num_threads_running(self, only_sub_threads=True):
    #    if only_sub_threads:
    #        return len([True for t in self.__processes.values() if t.isAlive()])
    #    else:
    #        return len([True for t in self.__processes.values() + [self.__thread] if t.isAlive()])
    #def num_threads(self, only_sub_threads=True):
    #    if only_sub_threads:
    #        return len(self.__processes.keys())
    #    else:
    #        return len(self.__processes.keys()) + 1
    def _process_exit_zmq(self, t_name, t_pid, *args):
        self._process_exit(t_name, t_pid)
    def _process_start_zmq(self, t_name, t_pid, *args):
        self.log("process %s (%d) started" % (t_name, t_pid))
        self.process_start(t_name, t_pid)
    def _process_exit(self, t_name, t_pid):
        self.__processes_running -= 1
        if t_pid:
            self.log("process %s (%d) exited" % (t_name, t_pid))
            # remove process from structures
            self.__processes[t_name].join()
        else:
            self.log("process %s forced exit" % (t_name))
        del self.__processes[t_name]
        del self.__sockets[t_name]
        # for subclassing
        self.process_exit(t_name, t_pid)
    def process_exit(self, p_name, p_pid):
        # dummy function, called when a process exits
        pass
    def process_start(self, p_name, p_pid):
        # dummy function, called when a process starts
        pass
    def _handle_exception(self):
        exc_info = sys.exc_info()
        self._exc_info = exc_info
        # FIXME
        exc_type = str(exc_info[0]).split(".")[-1].split("'")[0]
        if exc_type in self.__exception_table:
            self.log("caught known exception %s" % (exc_type),
                     logging_tools.LOG_LEVEL_WARN)
            self.__exception_table[exc_type](exc_info[1])
        else:
            except_info = get_except_info()
            self.log("caught unknown exception %s (%s), traceback" % (exc_type, except_info),
                     logging_tools.LOG_LEVEL_CRITICAL)
            tb = self._exc_info[2]
            out_lines = ["Exception in process '%s'" % (self.name)]
            for file_name, line_no, name, line in traceback.extract_tb(tb):
                self.log("File '%s', line %d, in %s" % (file_name, line_no, name),
                         logging_tools.LOG_LEVEL_CRITICAL)
                out_lines.append("File '%s', line %d, in %s" % (file_name, line_no, name))
                if line:
                    self.log(" - %d : %s" % (line_no, line),
                             logging_tools.LOG_LEVEL_CRITICAL)
                    out_lines.append(" - %d : %s" % (line_no, line))
            out_lines.append(except_info)
            # write to logging-server
            #err_h = io_stream_helper.io_stream("/var/lib/logging-server/py_err")
            #err_h.write("\n".join(out_lines))
            #err_h.close()
            self.log("waiting for 1 second",
                     logging_tools.LOG_LEVEL_WARN)
            time.sleep(1)
    def register_func(self, f_str, f_call):
        self.__func_table[f_str] = f_call
    def register_exception(self, exc_type, call):
        self.__exception_table[exc_type] = call
    def optimize_message_list(self, in_list):
        return in_list
    def _sig_handler(self, signum, frame):
        sig_str = "got signal %d" % (signum)
        self.log(sig_str)
        #return self._handle_exception()
        if signum == signal.SIGTERM:
            raise term_error, sig_str
        elif signum == signal.SIGINT:
            raise int_error, sig_str
        elif signum == signal.SIGTSTP:
            raise stop_error, sig_str
        elif signum == signal.SIGALRM:
            raise alarm_error, sig_str
        elif signum == signal.SIGHUP:
            raise hup_error, sig_str
        else:
            raise
    def install_signal_handlers(self):
        if not self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = True
            self.log("installing signal handlers")
            self.__orig_sig_handlers = {}
            for sig_num in [signal.SIGTERM,
                            signal.SIGINT,
                            signal.SIGTSTP,
                            signal.SIGALRM,
                            signal.SIGHUP]:
                self.__orig_sig_handlers[sig_num] = signal.signal(sig_num, self._sig_handler)
    def uninstall_signal_handlers(self):
        if self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = False
            self.log("uninstalling signal handlers")
            for sig_num, orig_h in self.__orig_sig_handlers.iteritems():
                signal.signal(sig_num, orig_h)
    def process_init(self):
        self.log("process_init %d" % (os.getpid()))
    def loop_start(self):
        self.log("loop_start %d" % (os.getpid()))
    def loop_end(self):
        self.log("loop_end %d" % (os.getpid()))
    def loop_post(self):
        pass
    def _show_recv_messages(self, mes_list):
        for mes in mes_list:
            if type(mes) == type(()):
                mes, in_stuff = mes
                self.log("SRM: received message %s (with options)" % (mes))
            else:
                self.log("SRM: received message %s" % (mes))
    def _tp_message_received(self, zmq_socket):
        mes_parts = zmq_socket.recv_pyobj() 
        src_process = mes_parts.pop(0)
        src_pid = mes_parts.pop(0)
        msg_type = mes_parts.pop(0)
        if msg_type in self.__func_table:
            self.__func_table[msg_type](src_process, src_pid, *mes_parts)
        else:
            self.log("unknown msg_type '%s' from src_process %s (%d)" % (msg_type, src_process, src_pid),
                     logging_tools.LOG_LEVEL_ERROR)
    def loop(self):
        self["loop_start_called"] = False
        self.install_signal_handlers()
        excepted = True
        while excepted:
            try:
                # call loop_start for first iteration
                if not self["loop_start_called"]:
                    self["loop_start_called"] = True
                    self.loop_start()
                while self["run_flag"]:
                    if self["exit_requested"]:
                        self.stop_running_processes()
                    try:
                        socks = dict(self.poller.poll(timeout=self.__loop_granularity))
                    except:
                        raise
                    #print socks
                    for sock, c_type in socks.iteritems():
                        if (sock, c_type) in self.poller_handler:
                            self.poller_handler[(sock, c_type)](sock)
                        else:
                            print "???", sock, c_type
                    cur_time = time.time()
                    if self.__next_timeout and cur_time > self.__next_timeout:
                        self._handle_timer(cur_time)
                    if self["exit_requested"] and not self.__processes_running:
                        self.log("loop exit")
                        self["run_flag"] = False
                self.loop_end()
                excepted = False
            except:
                self._handle_exception()
        self.uninstall_signal_handlers()
        self.loop_post()
    def loop_function(self):
        print "_dummy_loop_function(), sleeping for 10 seconds"
        time.sleep(10)
    def stop_running_processes(self):
        pri_dict = {}
        for key, value in self.__processes.iteritems():
            if key not in self.__processes_stopped:
                pri_dict.setdefault(value["priority"], []).append(key)
        # flag: any processes stopped in previous priorities, all processes deads in previous priorities
        act_processes_stopped, prev_processes_dead = (False, True)
        # iterate over priorities
        for pri in sorted(pri_dict.keys()):
            # only loop if all processes in lower priority groups are dead and no signals were sent to lower pri groups
            if prev_processes_dead and not act_processes_stopped:
                proc_list = pri_dict[pri]
                for p_name in proc_list:
                    if p_name not in self.__processes_stopped:
                        p_stuff = self.__processes[p_name]
                        # check if process is alive
                        if p_stuff.is_alive():
                            act_processes_stopped = True
                            self.stop_process(p_name)
                            prev_processes_dead = False
                            self.__processes_stopped.add(p_name)
                        else:
                            self.log("process %s seams to be dead" % (p_name),
                                     logging_tools.LOG_LEVEL_ERROR)
                            self._process_exit(p_name, 0)
                    else:
                        self.log("process '%s' already got exit message" % (p_name), logging_tools.LOG_LEVEL_WARN)
    def __repr__(self):
        return "process_pool %s, %s, %s" % (self.name,
                                            logging_tools.get_plural("process", len(self.__processes.keys())),
                                            logging_tools.get_plural("0MQ socket", len(self.__sockets.keys())))

class twisted_main_thread(object):
    def __init__(self, name, **args):
        self.name = name
        threading.currentThread().setName(self.name)
        self.__flags = {"run_flag"                  : True,
                        "signal_handlers_installed" : False,
                        "exit_requested"            : False}
        self.__exception_table = {}
        self.set_stack_size(args.get("stack_size", DEFAULT_STACK_SIZE))
    def __getitem__(self, fn):
        return self.__flags[fn]
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "thread_pool %s %s: %s" % (self.name,
                                         logging_tools.get_log_level_str(log_level),
                                         what)
    def set_stack_size(self, s_size):
        try:
            thread.stack_size(s_size)
        except:
            self.log("Error setting stack_size to %s: %s" % (logging_tools.get_size_str(s_size, long_version=True),
                                                             get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("setting stack_size to %s" % (logging_tools.get_size_str(s_size, long_version=True)))
    def _sig_handler(self, signum, frame):
        sig_str = "got signal %d" % (signum)
        self.log(sig_str)
        if signum == signal.SIGTERM:
            if hasattr(self, "_sigterm"):
                self._sigterm()
            else:
                raise term_error, sig_str
        elif signum == signal.SIGINT:
            if hasattr(self, "_sigint"):
                self._sigint()
            else:
                raise int_error, sig_str
        elif signum == signal.SIGTSTP:
            if hasattr(self, "_sigtstp"):
                self._sigtstp()
            else:
                raise stop_error, sig_str
        elif signum == signal.SIGALRM:
            if hasattr(self, "_sigalrm"):
                self._sigalrm()
            else:
                raise alarm_error, sig_str
        elif signum == signal.SIGHUP:
            if hasattr(self, "_sighup"):
                self._sighup()
            else:
                raise hup_error, sig_str
        else:
            raise
    def install_signal_handlers(self):
        if not self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = True
            
            self.log("installing signal handlers")
            self.__orig_sig_handlers = {}
            for sig_num in [signal.SIGTERM,
                            signal.SIGINT,
                            signal.SIGTSTP,
                            signal.SIGALRM,
                            signal.SIGHUP]:
                self.__orig_sig_handlers[sig_num] = signal.signal(sig_num, self._sig_handler)
    def uninstall_signal_handlers(self):
        if self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = False
            self.log("uninstalling signal handlers")
            for sig_num, orig_h in self.__orig_sig_handlers.iteritems():
                signal.signal(sig_num, orig_h)
    

class tp_test(thread_pool):
    def __init__(self):
        thread_pool.__init__(self, "test", blocking_loop=False)
        self.register_exception("int_error", self._int_error)
        self.__iter = 0
    def _int_error(self, bla):
        self["exit_requested"] = True
    def loop_end(self):
        for tn in self.get_thread_names():
            print self.get_thread(tn)["run_flag"]
    def loop_function(self):
        #print self.get_own_queue().qsize()
        if self["exit_requested"]:
            time.sleep(1)
        else:
            time.sleep(2)
        self.__iter += 1
        if self.__iter > 20:
            self["exit_requested"] = True
        print self.get_own_queue().qsize()
    
def test_it():
    mtp = tp_test()#hread_pool("test", blocking_loop=False)
    mtp.add_queue("log", 200)
    t_t = mtp.add_thread(thread_obj("sub", queue_size=200), start_thread=True)
    t_t2 = mtp.add_thread(thread_obj("sub2", queue_size=200), start_thread=True)
    mtp.get_queue("sub").put([("a", 4), ("b", 5)])
    mtp.get_queue("sub2").put([("a", 4), ("b", 5)])
    mtp.thread_loop()
    print mtp
    #os.kill(os.getpid(), 9)
    
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_it()
    print "Loadable module, exiting..."
    sys.exit(-1)
