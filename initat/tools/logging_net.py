# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2015 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
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
""" logging tools, network related """

import inspect
import logging  # @UnusedImport
import logging.handlers
import pickle
import threading
import traceback

import zmq

from .logging_tools import *


def get_logger(name, destination, **kwargs):
    """ specify init_logger=True to prepend init.at to the logname """
    is_linux, cur_pid = (
        sys.platform in ["linux2", "linux3", "linux"],
        os.getpid()
    )
    if kwargs.get("init_logger", False) and is_linux:
        # force init.at logger
        if not name.startswith("init.at."):
            name = "init.at.{}".format(name)
    # get unique logger for 0MQ send
    act_logger = logging.getLogger("{}.{:d}".format(name, cur_pid))
    act_logger.name = name
    act_logger.propagate = 0
    if not hasattr(act_logger, "handler_strings"):
        # only initiate once
        act_logger.handler_strings = []
    act_logger.setLevel(kwargs.get("base_log_level", logging.DEBUG))
    if type(destination) != list:
        destination = [destination]
    # hack to make destination unique with respect to pid
    destination = [(cur_pid, cur_dest) for cur_dest in destination]
    for act_dest in destination:
        # print name, act_dest
        if (cur_pid, act_dest) not in act_logger.handler_strings:
            act_dest = act_dest[1]
            act_logger.handler_strings.append((cur_pid, act_dest))
            if "context" not in kwargs:
                cur_context = zmq.Context()
            else:
                cur_context = kwargs["context"]
            pub = cur_context.socket(zmq.PUSH)
            pub.setsockopt(zmq.IMMEDIATE, 1)
            pub.setsockopt(zmq.LINGER, 10)
            pub.connect(rewrite_log_destination(act_dest))
            act_logger.addHandler(zmq_handler(pub, act_logger))
    if log_adapter:
        # by using the log_adapter we also add thread-safety to the logger
        act_adapter = log_adapter(act_logger, {})
    else:
        act_adapter = act_logger
    return act_adapter


class log_adapter(logging.LoggerAdapter):
    """ small adapater which adds host information to logRecords """
    def __init__(self, logger, extra):
        self.__lock = threading.Lock()
        self.set_prefix()
        logging.LoggerAdapter.__init__(self, logger, extra)

    def process(self, msg, kwargs):
        # add hostname and parent process id (to handle multiprocessing logging)
        if sys.platform in ["linux2", "linux3", "linux"]:
            kwargs.setdefault("extra", {})
            kwargs["extra"].setdefault("host", os.uname()[1].split(".")[0])
            kwargs["extra"].setdefault("ppid", os.getppid())
        elif sys.platform in ["win32"]:
            kwargs.setdefault("extra", {})
            kwargs["extra"].setdefault("host", os.getenv("COMPUTERNAME").lower())
            kwargs["extra"].setdefault("ppid", os.getppid())
        return msg, kwargs

    def set_prefix(self, pfix=""):
        self.__prefix = pfix

    def log_command(self, what):
        self.log(LOG_LEVEL_OK, "<LCH>{}</LCH>".format(what))

    def log(self, level=LOG_LEVEL_OK, what=LOG_LEVEL_OK, *args, **kwargs):
        self.__lock.acquire()
        if isinstance(level, basestring):
            # exchange level and what
            _lev = what
            what = level
            level = _lev
        if self.__prefix:
            what = "{}{}".format(self.__prefix, what)
        try:
            logging.LoggerAdapter.log(self, level, what, *args, **kwargs)
        except:
            my_syslog(what)
            print(what, self)
            raise
        self.__lock.release()

    def close(self):
        self.log_command("close")
        for handle in self.logger.handlers:
            if hasattr(handle, "close"):
                handle.close()


class zmq_handler(logging.Handler):
    def __init__(self, t_sock, logger_struct, **kwargs):
        self.set_target(t_sock)
        self._open = True
        logging.Handler.__init__(self)
        self.__logger = logger_struct

    def set_target(self, t_sock):
        self.__target = t_sock

    def makePickle(self, record):
        """
        Pickles the record in binary format with a length prefix, and
        returns it ready for transmission across the socket.
        """
        ei = record.exc_info
        if ei:
            dummy = self.format(record)  # just to get traceback text into record.exc_text
            record.exc_info = None  # to avoid Unpickleable error
        _d = dict(record.__dict__)
        _d["msg"] = record.getMessage()
        _d["args"] = None
        p_str = pickle.dumps(_d, 1)
        if ei:
            record.exc_info = ei  # for next handler
        return p_str

    def emit(self, record):
        _retry_count = 0
        while True:
            try:
                self.__target.send(self.makePickle(record), zmq.DONTWAIT)
            except zmq.error.Again:
                _retry_count += 1
                if _retry_count > 10:
                    break
                else:
                    time.sleep(0.01)
            else:
                break

    def close(self):
        if self._open:
            self._open = False
            # set linger to zero to speed up close process
            self.__target.setsockopt(zmq.LINGER, 0)
            self.__target.close()
            del self.__target
            if self.__logger:
                # remove from handler
                self.__logger.removeHandler(self)


class initat_formatter(object):
    # in fact a dummy formatter
    def format(self, record):
        record.message = record.getMessage()
        if getattr(record, "exc_info", None):
            tb_object = record.exc_info[2]
            frame_info = []
            for file_name, line_no, name, line in traceback.extract_tb(tb_object):
                frame_info.append("File '{}', line {:d}, in {}".format(file_name, line_no, name))
                if line:
                    frame_info.append(u" - {:d} : {}".format(line_no, line))
            frame_info.append(u"{} ({})".format(
                unicode(record.exc_info[0]),
                unicode(record.exc_info[1])))
            record.error_str = record.message + "\n" + "\n".join(frame_info)
            var_list, info_lines = ([], [])
            request = inspect.trace()[-1][0].f_locals.get("request", None)
            if request:
                info_lines.extend(
                    [
                        "",
                        "method is {}".format(request.method),
                        "",
                    ]
                )
                # print get / post variables
                v_dict = getattr(request, request.method, None)
                if v_dict:
                    var_list.extend(
                        [
                            "",
                            "{}:".format(get_plural("variable", len(v_dict))),
                            "",
                        ]
                    )
                    for s_num, s_key in enumerate(sorted(v_dict.keys())):
                        var_list.append(
                            "  {:3d} {}: {}".format(
                                s_num + 1,
                                s_key,
                                v_dict[s_key]
                            )
                        )
            # print frame_info, var_list
            record.exc_text = "\n".join(frame_info + var_list + info_lines)
        if hasattr(record, "request"):
            delattr(record, "request")


class init_handler(zmq_handler):
    zmq_context = None

    def __init__(self, filename=None):
        if not init_handler.zmq_context:
            self._init_zmq()
        pub = self._socket()
        zmq_handler.__init__(self, pub, None)

    def _init_zmq(self):
        init_handler.init_pid = os.getpid()
        init_handler.zmq_context = zmq.Context()

    def _socket(self):
        cur_context = init_handler.zmq_context
        pub = cur_context.socket(zmq.PUSH)
        # pub.setsockopt(zmq.IMMEDIATE, True)
        pub.connect(rewrite_log_destination("uds:/var/lib/logging-server/py_log_zmq"))
        return pub

    def emit(self, record):
        if not record.name.startswith("init.at."):
            record.name = "init.at.{}".format(record.name)
        self.format(record)
        zmq_handler.emit(self, record)


class init_email_handler(zmq_handler):
    zmq_context = None

    def __init__(self, filename=None, *args, **kwargs):
        if not init_handler.zmq_context:
            init_handler.zmq_context = zmq.Context()
        cur_context = init_handler.zmq_context
        pub = cur_context.socket(zmq.PUSH)
        pub.connect(rewrite_log_destination("uds:/var/lib/logging-server/py_err_zmq"))
        zmq_handler.__init__(self, pub, None)
        self.__lens = {
            "name": 1,
            "threadName": 1,
            "lineno": 1
        }

    def emit(self, record):
        record.IOS_type = "error"
        self.format(record)
        record.uid = os.getuid()
        record.gid = os.getgid()
        record.pid = os.getpid()
        record.ppid = os.getppid()
        zmq_handler.emit(self, record)


class init_handler_unified(zmq_handler):
    zmq_context = None

    def __init__(self, filename=None, *args, **kwargs):
        if not init_handler.zmq_context:
            self._init_zmq()
        pub = self._socket()
        zmq_handler.__init__(self, pub, None)

    def _init_zmq(self):
        init_handler.init_pid = os.getpid()
        init_handler.zmq_context = zmq.Context()

    def _socket(self):
        cur_context = init_handler.zmq_context
        pub = cur_context.socket(zmq.PUSH)
        pub.connect(rewrite_log_destination("uds:/var/lib/logging-server/py_log_zmq"))
        return pub

    def emit(self, record):
        if record.name.startswith("init.at."):
            record.name = record.name[8:]
        if os.getpid() != init_handler.init_pid:
            # dont share zmq-contexts between processes
            self._init_zmq()
            pub = self._socket()
            self.set_target(pub)
        self.format(record)
        form_str = "{:<s}/{}[{:d}]"
        record.threadName = form_str.format(record.name, record.threadName, record.lineno)
        record.name = "init.at.{}".format(UNIFIED_NAME)
        zmq_handler.emit(self, record)


class queue_handler(logging.Handler):
    """ sends log requests to other queues """
    def __init__(self, t_queue, **kwargs):
        self.__target_queue = t_queue
        self.__pre_tuple = kwargs.get("pre_tuple", "int_log")
        logging.Handler.__init__(self)

    def emit(self, record):
        try:
            self.__target_queue.put((self.__pre_tuple, record))
        except:
            self.handleError(record)
