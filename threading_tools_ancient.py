#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2014 Andreas Lang-Nevyjel
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
""" old classes for multiprocessing (using threading) """

import logging_tools
import os
try:
    import Queue
except:
    # python3
    import queue as Queue # @ImportRedefinition, @UnresolvedImport
import signal
import sys
import time
import threading
import traceback
try:
    import zmq
except ImportError:
    zmq = None
try:
    from twisted.internet import reactor # @UnresolvedImport
except ImportError:
    reactor = None

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
    return "%s (%s)" % (
        str(sys.exc_info()[0]),
        str(sys.exc_info()[1]))

def get_act_thread_name():
    return threading.currentThread().getName()

# threads communicate via messages
# message format is (com_str, rest) or com_str for simple commands

class min_thread_obj(threading.Thread):
    def __init__(self, name, **kwargs):
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
    def __init__(self, name, **kwargs):
        threading.Thread.__init__(self, name=name, target=self._code)
        self.name = name
        self.pid = os.getpid()
        self.__thread_pool = None
        self.__thread_queue = Queue.Queue(kwargs.get("queue_size", 100))
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
        self.__verbose = kwargs.get("verbose", False)
        # wait for more messages if one processed (for gathering of messages)
        self.__gather_timeout = kwargs.get("gather_timeout"   , 0.)
        self.__total_gather_wait = kwargs.get("total_gather_wait", 0.)
        # internal exit-function
        self.register_func("exit", self._exit_thread)
        # run flag
        self["run_flag"] = True
        # thread priority: when stopping threads start with the lowest priority and end with the highest
        self["priority"] = kwargs.get("priority", 0)
        # is a busy-loop thread ?
        self._busy_loop_function = kwargs.get("loop_function", None)
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
        print("thread %s %s: %s" % (self.getName(),
                                    logging_tools.get_log_level_str(log_level),
                                    what))
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
                mes, _in_stuff = mes
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
            # self.send_pool_message(["log_recv", "ok:::super"])
    def inner_loop(self, force_wait=False):
        # to be called from busy-loop threads like snmp trap sinks
        mes_list, mes, gather_messages, _gather_waited = ([], True, self.__gather_timeout > 0, 0.)
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
        self.add_queue(self.__my_queue_name, 128)
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
        self.__next_timeout = min([last_to for _cur_to, last_to, cb_func in self.__timer_list])
    def _handle_timer(self, cur_time):
        new_tl, t_funcs = ([], [])
        for cur_to, t_time, cb_func in self.__timer_list:
            if t_time <= cur_time:
                t_funcs.append(cb_func)
                new_tl.append((cur_to, t_time + cur_to, cb_func))
            else:
                new_tl.append((cur_to, t_time, cb_func))
        self.__timer_list = new_tl
        if self.__timer_list:
            self.__next_timeout = min([last_to for cur_to, last_to, cb_func in self.__timer_list])
        else:
            self.__next_timeout = None
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
        print("thread_pool %s %s: %s" % (self.get_name(),
                                         logging_tools.get_log_level_str(log_level),
                                         what))
    def add_ignore_func(self, f_str):
        if type(f_str) != type([]):
            f_str = [f_str]
        self.__ignore_funcs.extend(f_str)
    def set_stack_size(self, s_size):
        try:
            threading.stack_size(s_size)
        except:
            self.log("Error setting stack_size to %s: %s" % (logging_tools.get_size_str(s_size, long_format=True),
                                                             get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("setting stack_size to %s" % (logging_tools.get_size_str(s_size, long_format=True)))
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
        return dict([(q_n, (q_q.maxsize, q_q.qsize())) for q_n, q_q in self.__queues.items()])
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
    def _thread_exit(self, np_tuple):
        t_name, t_pid = np_tuple
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
            # err_h = io_stream_helper.io_stream("/var/lib/logging-server/py_err_zmq", zmq_context=self.zmq_context)
            # err_h.write("\n".join(out_lines))
            # err_h.close()
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
            raise term_error(sig_str)
        elif signum == signal.SIGINT:
            raise int_error(sig_str)
        elif signum == signal.SIGTSTP:
            raise stop_error(sig_str)
        elif signum == signal.SIGALRM:
            raise alarm_error(sig_str)
        elif signum == signal.SIGHUP:
            raise hup_error(sig_str)
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
            for sig_num, orig_h in self.__orig_sig_handlers.items():
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
                mes, _in_stuff = mes
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
                    for sock, c_type in socks.items():
                        if (sock, c_type) in self.poller_handler:
                            self.poller_handler[(sock, c_type)](sock)
                        else:
                            print("???")
                    cur_time = time.time()
                    if self.__next_timeout and cur_time > self.__next_timeout:
                        self._handle_timer(cur_time)
                    if self["exit_requested"] and not self.__sub_threads_running:
                        self.log("loop exit")
                        self["run_flag"] = False
                self.loop_end()
                excepted = False
            except:
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
        print("_dummy_loop_function(), sleeping for 10 seconds")
        time.sleep(10)
    def stop_running_threads(self):
        # int_queue = self.get_queue(self.__my_queue_name)
        pri_dict = {}
        for key, value in self.__threads.items():
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
                            self.log("Thread %s seems to be dead" % (t_name),
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

class twisted_main_thread(object):
    def __init__(self, name, **kwargs):
        self.name = name
        threading.currentThread().setName(self.name)
        self.__flags = {"run_flag"                  : True,
                        "signal_handlers_installed" : False,
                        "exit_requested"            : False}
        self.__exception_table = {}
        self.set_stack_size(kwargs.get("stack_size", DEFAULT_STACK_SIZE))
    def __getitem__(self, fn):
        return self.__flags[fn]
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print("thread_pool %s %s: %s" % (self.name,
                                         logging_tools.get_log_level_str(log_level),
                                         what))
    def set_stack_size(self, s_size):
        try:
            threading.stack_size(s_size)
        except:
            self.log("Error setting stack_size to %s: %s" % (logging_tools.get_size_str(s_size, long_format=True),
                                                             get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("setting stack_size to %s" % (logging_tools.get_size_str(s_size, long_format=True)))
    def _sig_handler(self, signum, frame):
        sig_str = "got signal %d" % (signum)
        self.log(sig_str)
        if signum == signal.SIGTERM:
            if hasattr(self, "_sigterm"):
                self._sigterm()
            else:
                raise term_error(sig_str)
        elif signum == signal.SIGINT:
            if hasattr(self, "_sigint"):
                self._sigint()
            else:
                raise int_error(sig_str)
        elif signum == signal.SIGTSTP:
            if hasattr(self, "_sigtstp"):
                self._sigtstp()
            else:
                raise stop_error(sig_str)
        elif signum == signal.SIGALRM:
            if hasattr(self, "_sigalrm"):
                self._sigalrm()
            else:
                raise alarm_error(sig_str)
        elif signum == signal.SIGHUP:
            if hasattr(self, "_sighup"):
                self._sighup()
            else:
                raise hup_error(sig_str)
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
            for sig_num, orig_h in self.__orig_sig_handlers.items():
                signal.signal(sig_num, orig_h)

if __name__ == "__main__":
    print("Loadable module, exiting...")
    sys.exit(-1)
