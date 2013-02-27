#!/usr/bin/python-init -Otu

import sys
import logging_tools
import zmq
import process_tools

def open_socket(zmq_context):
    send_sock = zmq_context.socket(zmq.DEALER)
    send_sock.setsockopt(zmq.IDENTITY, "%s:syslog_scan" % (process_tools.get_machine_name()))
    send_sock.setsockopt(zmq.LINGER, 0)
    send_sock.connect("tcp://localhost:8000")
    return send_sock

def main():
    zmq_context = zmq.Context()
    log_template = logging_tools.get_logger(
        "syslog_scan",
        "uds:/var/lib/logging-server/py_log_zmq",
        zmq=True,
        context=zmq_context)
    send_sock = None
    log_template.log(logging_tools.LOG_LEVEL_OK, "starting")
    while True:
        line = sys.stdin.readline().strip()
        if not line:
            break
        try:
            timestamp, host, msg = line.split(None, 2)
        except:
            log_template.log(logging_tools.LOG_LEVEL_ERROR,
                             "error parsing line %s: %s" % (line, process_tools.get_except_info()))
        else:
            log_template.log("got line from %s: %s" % (host, msg))
            if not send_sock:
                send_sock = open_socket(zmq_context)
            send_sock.send_unicode(msg)
    if send_sock:
        send_sock.close()
    log_template.log(logging_tools.LOG_LEVEL_OK, "received empty line, exiting")
    log_template.close()
    zmq_context.term()

if __name__ == "__main__":
    main()
