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
""" classes for multiprocessing (using multiprocessing) """

import inspect
import io_stream_helper
import logging_tools
import multiprocessing
import os
import process_tools
import signal
import sys
import threading
import time
import traceback
import zmq
try:
    from threading_tools_ancient import thread_obj, thread_pool, twisted_main_thread # @UnusedImport
except:
    pass

# default stacksize
DEFAULT_STACK_SIZE = 2 * 1024 * 1024

# base class
class exception_handling_base(object):
    pass

# exception mixin
class operational_error_mixin(exception_handling_base):
    def __init__(self):
        self.register_exception("OperationalError", self._op_error)
    def _op_error(self, info):
        try:
            from django.db import connection
        except:
            pass
        else:
            self.log("operational error, closing db connection", logging_tools.LOG_LEVEL_ERROR)
            try:
                connection.close()
            except:
                pass

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

# debug objects for ZMQ debugging
class debug_zmq_sock(object):
    def __init__(self, zmq_sock):
        self._sock = zmq_sock
    def register(self, ctx):
        self.ctx = ctx
        ctx._sockets_open.add(self.fileno())
    def bind(self, name):
        self.ctx.log("bind %d to %s" % (self.fileno(), name))
        return self._sock.bind(name)
    def connect(self, name):
        self.ctx.log("connect %d to %s" % (self.fileno(), name))
        return self._sock.connect(name)
    def send(self, *args, **kwargs):
        return self._sock.send(*args, **kwargs)
    def send_pyobj(self, *args, **kwargs):
        return self._sock.send_pyobj(*args, **kwargs)
    def send_unicode(self, *args, **kwargs):
        return self._sock.send_unicode(*args, **kwargs)
    def recv(self, *args, **kwargs):
        return self._sock.recv(*args, **kwargs)
    def recv_pyobj(self, *args, **kwargs):
        return self._sock.recv_pyobj(*args, **kwargs)
    def recv_unicode(self, *args, **kwargs):
        return self._sock.recv_unicode(*args, **kwargs)
    def setsockopt(self, *args):
        return self._sock.setsockopt(*args)
    def getsockopt(self, *args):
        return self._sock.getsockopt(*args)
    def fileno(self):
        return self._sock.getsockopt(zmq.FD)
    def poll(self, **kwargs):
        return self._sock.poll(**kwargs)
    def close(self):
        self.ctx.log("close %d" % (self.fileno()))
        self.ctx._sockets_open.remove(self.fileno())
        if self.ctx._sockets_open:
            self.ctx.log("    still open: %s" % (", ".join(["%d" % (cur_fd) for cur_fd in self.ctx._sockets_open])))
        return self._sock.close()

class debug_zmq_ctx(zmq.Context):
    ctx_idx = 0
    def __init__(self, *args, **kwargs):
        self.zmq_idx = debug_zmq_ctx.ctx_idx
        debug_zmq_ctx.ctx_idx += 1
        zmq.Context.__init__(self, *args, **kwargs)
        self._sockets_open = set()
    def __setattr__(self, key, value):
        if key in ["zmq_idx", "_sockets_open"]:
            # not defined in zmq.Context
            self.__dict__[key] = value
        else:
            super(debug_zmq_ctx, self).__setattr__(key, value)
    def __delattr__(self, key):
        if key in ["zmq_idx", "_sockets_open"]:
            # not defined in zmq.Context
            if key in self.__dict__:
                del self.__dict__[key]
        else:
            super(debug_zmq_ctx, self).__delattr__(key)
    def log(self, out_str):
        t_name = threading.currentThread().name
        print("[[zmq_idx=%d, t_name=%-20s]] %s" % (self.zmq_idx, t_name, out_str))
    def _interpret_sock_type(self, s_type):
        l_type = ""
        for _s_type in ["XPUB", "XSUB", "REP", "REQ", "ROUTER", "SUB", "DEALER", "PULL", "PUB", "PUSH"]:
            if getattr(zmq, _s_type) == s_type:
                l_type = _s_type
        return "%d%s" % (s_type, "=%s" % (l_type) if l_type else "")
    def socket(self, sock_type, *args, **kwargs):
        ret_socket = super(debug_zmq_ctx, self).socket(sock_type, *args, **kwargs)
        self._sockets_open.add(ret_socket.fd)
        self.log("socket(%s) == %d, now open: %s" % (
            self._interpret_sock_type(sock_type),
            ret_socket.fd,
            ", ".join(["%d" % (cur_fd) for cur_fd in self._sockets_open])))
        ret_sock = debug_zmq_sock(ret_socket)
        ret_sock.register(self)
        return ret_sock
    def term(self):
        self.log("term, %s open" % (logging_tools.get_plural("socket", len(self._sockets_open))))
        del self._sockets_open
        super(debug_zmq_ctx, self).term()

class _timer_obj(object):
    def __init__(self, step, next_time, cb_func, **kwargs):
        # step value
        self.step = step
        # next wakeup time
        self.next_time = next_time
        # callback func
        self.cb_func = cb_func
        # onehost
        self.oneshot = kwargs.get("oneshot", False)
        # data
        self.data = kwargs.get("data", None)
    def __call__(self):
        self.next_time += self.step
        if self.data is None:
            self.cb_func()
        else:
            self.cb_func(self.data)

class timer_base(object):
    def __init__(self, **kwargs):
        # timer structure
        self.__timer_list, self.__next_timeout = ([], None)
        # loop timer
        self.__loop_timer = kwargs.get("loop_timer", 0)
    def register_timer(self, cb_func, timeout, **kwargs):
        s_time = time.time()
        if not kwargs.get("instant", False):
            s_time = s_time + timeout
        self.__timer_list.append(_timer_obj(timeout, s_time, cb_func, **kwargs))
        self.__next_timeout = min([cur_to.next_time for cur_to in self.__timer_list])
        if not self.__loop_timer:
            self.__loop_timer = 500
            self.log("set loop_timer to {:d} msecs".format(int(self.__loop_timer)))
    def unregister_timer(self, ut_cb_func):
        self.__timer_list = [cur_to for cur_to in self.__timer_list if cur_to.cb_func != ut_cb_func]
    def change_timer(self, ct_cb_func, timeout, **kwargs):
        instant = kwargs.get("instant", True)
        # timeout is here in milliseconds, just like the loop_timer
        for cur_to in self.__timer_list:
            if cur_to.cb_func == ct_cb_func:
                cur_to.step = timeout / 1000.
                self.set_loop_timer(min(self.__loop_timer, cur_to.step * 1000.))
                if instant:
                    cur_to.next_time = time.time()
                else:
                    cur_to.next_time = time.time() + cur_to.step
        self.__next_timeout = min([cur_to.next_time for cur_to in self.__timer_list])
    def _handle_timer(self, cur_time):
        new_tl = []
        # min_next = 1.0
        for cur_to in self.__timer_list:
            _diff = cur_to.next_time - cur_time
            if _diff <= 0:
                cur_to()
                # also remove if cur_to not in self.__timer_list (due to removal while processing cur_to() )
                if not cur_to.oneshot and cur_to in self.__timer_list:
                    new_tl.append(cur_to)
            else:
                # min_next = min(_diff, min_next)
                new_tl.append(cur_to)
        self.__timer_list = new_tl
        if self.__timer_list:
            self.__next_timeout = min([cur_to.next_time for cur_to in self.__timer_list])
        else:
            self.__next_timeout = None
    def set_loop_timer(self, lt):
        # loop timer in millisecons
        self.__loop_timer = lt
    @property
    def next_timeout(self):
        return self.__next_timeout
    @property
    def loop_timer(self):
        return self.__loop_timer

class poller_obj(object):
    def __init__(self):
        # poller
        self.poller = zmq.Poller()
        self.poller_handler = {}
        # for ZMQ debug
        self.fd_lookup = {}
        self._socket_lut = {}
        self.__normal_sockets = False
    def register_poller(self, zmq_socket, sock_type, callback):
        if self.debug_zmq:
            self.fd_lookup[zmq_socket._sock] = zmq_socket
        self.poller_handler.setdefault(zmq_socket, {})[sock_type] = callback
        cur_mask = 0
        for mask in self.poller_handler[zmq_socket].keys():
            cur_mask |= mask
        if self.debug_zmq:
            self.poller.register(zmq_socket._sock, cur_mask)
        else:
            self.poller.register(zmq_socket, cur_mask)
    def unregister_poller(self, zmq_socket, sock_type, **kwargs):
        del self.poller_handler[zmq_socket][sock_type]
        if self.debug_zmq:
            self.poller.unregister(zmq_socket._sock)
        else:
            self.poller.unregister(zmq_socket)
        if not self.poller_handler[zmq_socket]:
            if self.debug_zmq:
                del self.fd_lookup[zmq_socket._sock]
            del self.poller_handler[zmq_socket]
            if kwargs.get("close_socket", False):
                zmq_socket.close()
        else:
            cur_mask = 0
            for mask in self.poller_handler[zmq_socket].keys():
                cur_mask |= mask
            self.poller.register(zmq_socket, cur_mask)
    def register_socket(self, n_socket, event_mask, callback):
        self._socket_lut[n_socket.fileno()] = n_socket
        _fn = n_socket.fileno()
        self.poller_handler.setdefault(n_socket, {})[event_mask] = callback
        cur_mask = 0
        for mask in self.poller_handler[n_socket].keys():
            cur_mask |= mask
        self.poller.register(n_socket, cur_mask)
        self.__normal_sockets = True
    def unregister_socket(self, n_socket):
        # del self._socket_lut[n_socket]
        # del self._socket_lut[n_socket.fileno()]
        self.poller.unregister(n_socket)
        if n_socket.fileno() in self._socket_lut:
            del self._socket_lut[n_socket.fileno()]
        del self.poller_handler[n_socket]
    def _do_select(self, timeout):
        _list = self.poller.poll(timeout)
        self._handle_select_list(_list)
    def _handle_select_list(self, in_list):
        # import select
        # print "**", in_list, zmq.POLLIN, zmq.POLLOUT, select.POLLIN, select.POLLOUT
        for sock, c_type in in_list:
            if self.debug_zmq and type(sock) not in [int, long]:
                sock = self.fd_lookup[sock]
            if sock in self._socket_lut:
                sock = self._socket_lut[sock]
            # print "..", sock, sock in self.poller_handler
            if sock in self.poller_handler:
                # print zmq.POLLIN, zmq.POLLOUT, zmq.POLLERR
                for r_type in set([zmq.POLLIN, zmq.POLLOUT, zmq.POLLERR]):
                    if c_type & r_type:
                        # the socket could vanish
                        if r_type in self.poller_handler.get(sock, []):
                            try:
                                self.poller_handler[sock][r_type](self._socket_lut.get(sock, sock))
                            except:
                                exc_info = process_tools.exception_info()
                                self.log(
                                    "error calling handler in poller_obj: {}".format(
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_CRITICAL
                                )
                                for line in exc_info.log_lines:
                                    self.log("    {}".format(line), logging_tools.LOG_LEVEL_ERROR)
                                # raise exception, important
                                raise
                        else:
                            self.log(
                                "r_type {:d} not found for socket '{}'".format(
                                    r_type,
                                    str(sock),
                                ),
                                logging_tools.LOG_LEVEL_CRITICAL
                            )
                            time.sleep(0.5)
            else:
                self.log("socket %s not found in handler_dict" % (str(sock)), logging_tools.LOG_LEVEL_CRITICAL)
                time.sleep(0.5)

class process_base(object):
    def set_stack_size(self, s_size):
        try:
            threading.stack_size(s_size)
        except:
            self.log("Error setting stack_size to %s: %s" % (logging_tools.get_size_str(s_size, long_version=True),
                                                             get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("setting stack_size to %s" % (logging_tools.get_size_str(s_size, long_version=True)))

class exception_handling_mixin(object):
    def __init__(self):
        self.__exception_table = {}
        for _cl in inspect.getmro(self.__class__):
            # handle if
            # ... is subclass of exception_handling_base
            # ... is not exception_handling_base
            # ... is no subclass of exception_handling_mixin
            if issubclass(_cl, exception_handling_base) and _cl != exception_handling_base and not issubclass(_cl, exception_handling_mixin):
                _cl.__init__(self)
                # print "*", _cl
    def register_exception(self, exc_type, call):
        self.__exception_table[exc_type] = call
        # self.log("registered exception handler for {}".format(exc_type))
    def show_exception_handlers(self):
        self.log(
            "{} defined: {}".format(
                logging_tools.get_plural("exception handler", len(self.__exception_table)),
                ", ".join(sorted(self.__exception_table.keys()))
            )
        )
    def handle_exception(self):
        _handled = False
        exc_info = sys.exc_info()
        # store info
        self._exc_info = exc_info
        # FIXME
        exc_type = str(exc_info[0]).split(".")[-1].split("'")[0]
        if exc_type in self.__exception_table:
            self.log("caught known exception {}".format(exc_type),
                     logging_tools.LOG_LEVEL_WARN)
            self.__exception_table[exc_type](exc_info[1])
            _handled = True
        else:
            except_info = get_except_info()
            self.log(
                "caught unknown exception {} ({}), traceback".format(
                    exc_type,
                    except_info),
                logging_tools.LOG_LEVEL_CRITICAL)
            tb = self._exc_info[2]
            out_lines = ["Exception in process '{}'".format(self.name)]
            for file_name, line_no, name, line in traceback.extract_tb(tb):
                self.log(
                    "File '{}', line {:d}, in {}".format(
                        file_name, line_no, name),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                out_lines.append("File '{}', line {:d} in {}".format(file_name, line_no, name))
                if line:
                    self.log(" - {:d} : {}".format(line_no, line),
                             logging_tools.LOG_LEVEL_CRITICAL)
                    out_lines.append(" - {:d} : {}".format(line_no, line))
            out_lines.append(except_info)
            # write to logging-server
            err_h = io_stream_helper.io_stream("/var/lib/logging-server/py_err_zmq", zmq_context=self.zmq_context)
            err_h.write("\n".join(out_lines))
            err_h.close()
            self.log(
                "waiting for 1 second",
                logging_tools.LOG_LEVEL_WARN)
            time.sleep(1)
        return _handled

class process_obj(multiprocessing.Process, timer_base, poller_obj, process_base, exception_handling_mixin):
    def __init__(self, name, **kwargs):
        multiprocessing.Process.__init__(self, target=self._code, name=name)
        timer_base.__init__(self, loop_timer=kwargs.get("loop_timer", 0))
        poller_obj.__init__(self)
        exception_handling_mixin.__init__(self)
        self.__stack_size = kwargs.get("stack_size", DEFAULT_STACK_SIZE)
        # flags
        self.__flags = {}
        # function table
        self.__func_table = {}
        # ignore calls
        self.__ignore_funcs = []
        # busy loop
        self.__busy_loop = kwargs.get("busy_loop", False)
        # verbose
        self.__verbose = kwargs.get("verbose", False)
        # internal exit-function
        self.register_func("exit", self._exit_process)
        # run flag
        # process priority: when stopping processes start with the lowest priority and end with the highest
        self["priority"] = kwargs.get("priority", 0)
        self.cb_func = kwargs.get("cb_func", None)
        # copy kwargs for reference
        self.start_kwargs = kwargs
        self.__exit_locked = False
    @property
    def global_config(self):
        return self.__global_config
    @global_config.setter
    def global_config(self, g_conf):
        self.__global_config = g_conf
    def lock_exit(self):
        self.__exit_locked = True
    def unlock_exit(self):
        self.__exit_locked = False
    @property
    def process_pool(self):
        return self.__process_pool
    @process_pool.setter
    def process_pool(self, p_pool):
        self.__process_pool = p_pool
    def getName(self):
        return self.name
    # def has_key(self, key):
    #    return key in self.__flags
    def __setitem__(self, fn, state):
        self.__flags[fn] = state
    def __getitem__(self, fn):
        return self.__flags[fn]
    def send_to_socket(self, t_socket, data, *args):
        if args:
            t_socket.send_pyobj(
                {
                    "name"   : self.name,
                    "pid"    : self.pid,
                    "type"   : data,
                    "args"   : args,
                }
            )
        else:
            t_socket.send_pyobj(
                {
                    "name"   : self.name,
                    "pid"    : self.pid,
                    "type"   : data[0],
                    "args"   : data[1:],
                }
            )
    def send_pool_message(self, *args):
        self.__pp_queue.send_pyobj({
            "name" : self.name,
            "pid"  : self.pid,
            "type" : list(args)[0],
            "args" : list(args)[1:]})
    def _init_sockets(self):
        if self.debug_zmq:
            self.zmq_context = debug_zmq_ctx()
        else:
            self.zmq_context = zmq.Context()
        new_q = self.zmq_context.socket(zmq.PULL)
        process_tools.bind_zmq_socket(new_q, process_tools.get_zmq_ipc_name(self.name))
        # new_q.setsockopt(zmq.SNDBUF, 65536)
        # new_q.setsockopt(zmq.RCVBUF, 65536)
        # new_q.setsockopt(zmq.HWM, 10)
        self.__process_queue = new_q
        pp_queue = self.zmq_context.socket(zmq.PUSH)
        pp_queue.connect(self.__process_pool.queue_name)
        self.register_poller(new_q, zmq.POLLIN, self._handle_message)
        self.__pp_queue = pp_queue
        # flush pool
        self.send_pool_message("process_start")
    def _close_sockets(self):
        # wait for the last commands to settle
        time.sleep(0.25)
        self.__process_queue.close()
        self.__pp_queue.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print("process %s (%d) %s: %s" % (self.name,
                                          self.pid,
                                          logging_tools.get_log_level_str(log_level),
                                          what))
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
        # now we should have a vaild log command
        self.set_stack_size(self.__stack_size)
        self.show_exception_handlers()
        self.process_running()
        self.loop_start()
        self.loop()
        self.loop_end()
        self.process_exit()
        self._close_sockets()
        self.loop_post()
        self.zmq_finish()
        return 0
    def loop_post(self):
        pass
    def zmq_finish(self):
        self.zmq_context.term()
    def connect_to_socket(self, name):
        cur_socket = self.zmq_context.socket(zmq.PUSH)
        cur_socket.connect(process_tools.get_zmq_ipc_name(name))
        return cur_socket
    def _exit_process(self, **kwargs):
        self.log("exit_process called for process %s (pid=%d)" % (self.name, self.pid))
        self["run_flag"] = False
    def process_exit(self):
        self.send_pool_message("process_exit")
    # def optimize_message_list(self, in_list):
    #    return in_list
    def process_init(self):
        self.log("process_init (%s, pid=%d)" % (self.name, self.pid))
    def process_running(self):
        pass
    def loop_start(self):
        self.log("process_loop_start (%s, pid=%d)" % (self.name, self.pid))
    def loop_end(self):
        self.log("process_loop_end (%s, pid=%d)" % (self.name, self.pid))
    def any_message_received(self):
        pass
    def _handle_message(self, zmq_socket):
        cur_mes = zmq_socket.recv_pyobj()
        src_process = cur_mes["name"]
        src_pid = cur_mes["pid"]
        mes_type = cur_mes["type"]
        if mes_type in self.__func_table:
            self.__func_table[mes_type](
                *cur_mes["args"],
                src_pid=src_pid,
                src_process=src_process,
                func_name=mes_type,
                **cur_mes.get("kwargs", {}))
            self.any_message_received()
        else:
            self.log("unknown message type '%s' from %s (%d)" % (
                mes_type,
                src_process,
                src_pid),
                     logging_tools.LOG_LEVEL_ERROR)
    def step(self, blocking=False, timeout=0):
        # unify with loop from process_pool ? FIXME, TODO
        # process all pending messages
        if self.next_timeout:
            diff_time = self.next_timeout - time.time()
            # important to avoid negative timeouts
            timeout = max(min(diff_time * 1000, timeout), 0)
            if not timeout:
                blocking = False
        if blocking:
            timeout = None
        # no loop to reduce latency for ICMP ping
        self._do_select(timeout)
    def loop(self):
        while self["run_flag"] or self.__exit_locked:
            try:
                if self.loop_timer:
                    cur_time = time.time()
                    if self.next_timeout and cur_time > self.next_timeout:
                        self._handle_timer(cur_time)
                    self.step(blocking=False, timeout=self.loop_timer)
                else:
                    # print "bl", self.name
                    if self.__busy_loop:
                        self.step()
                    else:
                        self.step(blocking=True)
            except:
                handled = self.handle_exception()
                if not handled:
                    print(
                        "process_obj.loop() {}: {}".format(
                            self.name,
                            process_tools.get_except_info()
                        )
                    )
                    raise
            if self.cb_func:
                self.cb_func()

class process_pool(timer_base, poller_obj, process_base, exception_handling_mixin):
    def __init__(self, name, **kwargs):
        self.debug_zmq = kwargs.get("zmq_debug", False)
        timer_base.__init__(self)
        poller_obj.__init__(self)
        exception_handling_mixin.__init__(self)
        self.name = name
        self.pid = os.getpid()
        self.__sockets = {}
        self.__socket_buffer = {}
        self.__processes = {}
        if self.debug_zmq:
            self.zmq_context = debug_zmq_ctx(kwargs.pop("zmq_contexts", 1))
        else:
            self.zmq_context = zmq.Context(kwargs.pop("zmq_contexts", 1))
        self.loop_granularity = kwargs.get("loop_granularity", 1000)
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
        self.register_func("process_exception", self._process_exception)
        # flags for exiting / loop-control
        self.__flags = {"run_flag"                  : True,
                        "signal_handlers_installed" : False,
                        "exit_requested"            : False,
                        "return_value"              : 0}
        self.process_init()
        self.set_stack_size(kwargs.get("stack_size", DEFAULT_STACK_SIZE))
        self.__processes_stopped = set()
        # clock ticks per second
        self.__sc_clk_tck = float(os.sysconf(os.sysconf_names["SC_CLK_TCK"]))
        self.__cpu_usage = []
    def check_cpu_usage(self):
        _excess = False
        _pids = [self.pid] + [value.pid for value in self.processes.itervalues()]
        try:
            usage = [sum([int(_val) for _val in file("/proc/%d/stat" % (_pid), "r").read().split()[13:15]], 0) for _pid in _pids]
        except:
            # some problems, ignore
            pass
        else:
            cur_time = time.time()
            self.__cpu_usage = self.__cpu_usage[-4:] + [(cur_time, usage)]
            try:
                if len(self.__cpu_usage) > 2:
                    pid_count = len(self.__cpu_usage[0][1])
                    _usage = [0] * pid_count
                    _prev_time = None
                    _p = None
                    # max. number of usage
                    _uf = []
                    for _cur_time, _t in self.__cpu_usage:
                        if _prev_time:
                            _uf.append(max([max(_a, _b) for _a, _b in zip(_usage, [(_v0 - _v1) / (_cur_time - _prev_time) / self.__sc_clk_tck for _v0, _v1 in zip(_t, _p)])]))
                            # print _usage
                        _prev_time = _cur_time
                        _p = _t
                    if len(_uf) > 3 and min(_uf) > 0.95:
                        self.log("exczess values: %s" % (str(_uf)))
                        _excess = True
            except:
                pass
        return _excess
    @property
    def processes(self):
        return self.__processes
    @property
    def loop_granularity(self):
        return self.__loop_granularity
    @loop_granularity.setter
    def loop_granularity(self, val):
        self.__loop_granularity = val
    def renice(self, nice_level=16):
        try:
            os.nice(nice_level)
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
    def add_zmq_socket(self, q_name):
        if q_name in self.__sockets:
            zmq_socket = self.__sockets[q_name]
        else:
            zmq_socket = self.zmq_context.socket(zmq.PULL)
            process_tools.bind_zmq_socket(zmq_socket, q_name)
            # zmq_socket.setsockopt(zmq.SNDBUF, 65536)
            # zmq_socket.setsockopt(zmq.RCVBUF, 65536)
            # zmq_socket.setsockopt(zmq.HWM, 10)
            self.register_poller(zmq_socket, zmq.POLLIN, self._tp_message_received)
            self.__sockets[q_name] = zmq_socket
        return zmq_socket
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print("process_pool %s (%d) %s: %s" % (self.get_name(),
                                               os.getpid(),
                                               logging_tools.get_log_level_str(log_level),
                                               what))
    def add_ignore_func(self, f_str):
        if type(f_str) != type([]):
            f_str = [f_str]
        self.__ignore_funcs.extend(f_str)
    def _close_pp_sockets(self):
        for _sock_name, zmq_sock in self.__sockets.items():
            zmq_sock.close()
        self.zmq_context.term()
    def add_process(self, t_obj, **kwargs):
        # add a process_object to the process_pool
        if t_obj.getName() in self.__processes:
            self.log("process named '%s' already present" % (t_obj.getName()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            return None
        else:
            t_obj.process_pool = self
            self.__processes[t_obj.getName()] = t_obj
            # process_queue.setsockopt(zmq.SNDBUF, 65536)
            # process_queue.setsockopt(zmq.RCVBUF, 65536)
            # process_queue.setsockopt(zmq.HWM, 10)
            process_queue = self.zmq_context.socket(zmq.PUSH)
            process_queue.connect(process_tools.get_zmq_ipc_name(t_obj.getName()))
            self.__sockets[t_obj.getName()] = process_queue
            # set additional attributes
            for key in [sub_key for sub_key in sorted(kwargs.keys()) if sub_key not in ["start"]]:
                self.log("setting attribute '%s' for %s" % (key, t_obj.getName()))
                setattr(t_obj, key, kwargs[key])
            # copy debug_zmq flag to child process
            t_obj.debug_zmq = self.debug_zmq
            if kwargs.get("start", False):
                self.start_process(t_obj.getName())
            self._flush_process_buffers(t_obj.getName())
            return self.__sockets[t_obj.getName()]
    def send_to_process(self, t_process, m_type, *args, **kwargs):
        """ send message to target_process, type is m_type """
        if t_process not in self.__sockets:
            self.__socket_buffer.setdefault(t_process, []).append((m_type, list(args), dict(kwargs)))
        else:
            if t_process in self.__socket_buffer:
                self._flush_process_buffers(t_process)
            self.__sockets[t_process].send_pyobj({
                "name"   : self.name,
                "pid"    : self.pid,
                "type"   : m_type,
                "args"   : list(args),
                "kwargs" : dict(kwargs)})
    def _flush_process_buffers(self, t_process):
        if t_process in self.__socket_buffer:
            for b_m_type, b_args, b_kwargs in self.__socket_buffer[t_process]:
                self.__sockets[t_process].send_pyobj({
                "name"   : self.name,
                "pid"    : self.pid,
                "type"   : b_m_type,
                "args"   : list(b_args),
                "kwargs" : dict(b_kwargs)})
            del self.__socket_buffer[t_process]
    def get_process_names(self):
        return self.__processes.keys() + [self.get_name()]
    def get_process(self, p_name):
        if p_name == self.get_name():
            return self
        else:
            return self.__processes[p_name]
    def get_info_dict(self):
        p_dict = dict([(key, {"alive" : self.get_process(key).is_alive()}) for key in self.get_process_names()])
        return p_dict
    def is_alive(self):
        # dummy function
        return True
    def start_process(self, p_name):
        if not self.__processes[p_name].is_alive():
            self.log("starting process %s" % (p_name))
            self.__processes[p_name].start()
            self.__processes_running += 1
    def stop_process(self, p_name):
        if self.__processes[p_name].is_alive():
            self.log("sending exit to process %s" % (p_name))
            self.send_to_process(p_name, "exit")
    def _process_exit_zmq(self, t_name, t_pid, *args):
        self._process_exit(t_name, t_pid)
    def _process_start_zmq(self, t_name, t_pid, *args):
        self.log("process %s (%d) started" % (t_name, t_pid))
        self.process_start(t_name, t_pid)
    def _process_exception(self, t_name, t_pid, *args):
        self.log("process %s (pid %d) exception: %s" % (t_name, t_pid, unicode(args[0])),
                 logging_tools.LOG_LEVEL_CRITICAL)
        self["exit_requested"] = True
    def _process_exit(self, t_name, t_pid):
        self.__processes_running -= 1
        if t_pid:
            self.log("process %s (%d) exited" % (t_name, t_pid))
            # remove process from structures
            self.__processes[t_name].join()
        else:
            self.log("process %s forced exit" % (t_name))
        del self.__processes[t_name]
        self.__sockets[t_name].close()
        del self.__sockets[t_name]
        # for subclassing
        self.process_exit(t_name, t_pid)
    def process_exit(self, p_name, p_pid):
        # dummy function, called when a process exits
        pass
    def process_start(self, p_name, p_pid):
        # dummy function, called when a process starts
        pass
    def register_func(self, f_str, f_call):
        self.__func_table[f_str] = f_call
    def optimize_message_list(self, in_list):
        return in_list
    def _sig_handler(self, signum, frame):
        sig_str = "got signal %d" % (signum)
        self.log(sig_str)
        # return self._handle_exception()
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
            for sig_num in [
                signal.SIGTERM,
                signal.SIGINT,
                signal.SIGTSTP,
                signal.SIGALRM,
                signal.SIGHUP
                ]:
                self.__orig_sig_handlers[sig_num] = signal.signal(sig_num, self._sig_handler)
    def uninstall_signal_handlers(self):
        if self["signal_handlers_installed"]:
            self["signal_handlers_installed"] = False
            self.log("uninstalling signal handlers")
            for sig_num, orig_h in self.__orig_sig_handlers.items():
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
                mes, _in_stuff = mes
                self.log("SRM: received message %s (with options)" % (mes))
            else:
                self.log("SRM: received message %s" % (mes))
    def _tp_message_received(self, zmq_socket):
        mes_parts = zmq_socket.recv_pyobj()
        src_process = mes_parts["name"]
        src_pid = mes_parts["pid"]
        msg_type = mes_parts["type"]
        if msg_type in self.__func_table:
            self.__func_table[msg_type](src_process, src_pid, *mes_parts["args"], **mes_parts.get("kwargs", {}))
        else:
            self.log("unknown msg_type '%s' from src_process %s (%d)" % (msg_type, src_process, src_pid),
                     logging_tools.LOG_LEVEL_ERROR)
    def loop(self):
        self["loop_start_called"] = False
        self.install_signal_handlers()
        self.show_exception_handlers()
        excepted = True
        while excepted:
            try:
                # call loop_start for first iteration
                if not self["loop_start_called"]:
                    self["loop_start_called"] = True
                    self.loop_start()
                if self.__blocking_loop:
                    while self["run_flag"]:
                        if self["exit_requested"]:
                            self.stop_running_processes()
                        cur_time = time.time()
                        if self.next_timeout and cur_time > self.next_timeout:
                            self._handle_timer(cur_time)
                        if not self["exit_requested"] or self.__processes_running:
                            self._poll()
                        if self["exit_requested"] and not self.__processes_running:
                            self.log("loop exit")
                            self["run_flag"] = False
                else:
                    while self["run_flag"]:
                        for do_loop in self.loop_function():
                            if not do_loop:
                                self["exit_requested"] = True
                            if self["exit_requested"]:
                                self.stop_running_processes()
                            cur_time = time.time()
                            if self.next_timeout and cur_time > self.next_timeout:
                                self._handle_timer(cur_time)
                            if not self["exit_requested"] or self.__processes_running:
                                self._poll()
                            if self["exit_requested"] and not self.__processes_running:
                                self.log("loop exit")
                                self["run_flag"] = False
                                break
                self.loop_end()
                excepted = False
            except:
                self.handle_exception()
        self.uninstall_signal_handlers()
        self.loop_post()
        self._close_pp_sockets()
        return self["return_value"]
    def _poll(self):
        # only check sockets if no exit was requested by one of the timer funcs above
        # otherwise we have to wait for loop_granularity milliseconds
        try:
            _socks = self.poller.poll(timeout=self.__loop_granularity)
        except:
            raise
        self._handle_select_list(_socks)
    def loop_function(self):
        # generator
        print("_dummy_loop_function(), sleeping for 10 seconds")
        time.sleep(10)
        yield None
    def stop_running_processes(self):
        pri_dict = {}
        for key, value in self.__processes.items():
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
        return "process_pool %s, %s, %s" % (
            self.name,
            logging_tools.get_plural("process", len(self.__processes.keys())),
            logging_tools.get_plural("0MQ socket", len(self.__sockets.keys())))

if __name__ == "__main__":
    print("Loadable module, exiting...")
    sys.exit(-1)
