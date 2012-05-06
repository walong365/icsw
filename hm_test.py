#!/usr/bin/python-init -Otu

import server_command
import zmq
import os
import time

def main():
    ctx = zmq.Context()
    slave = ctx.socket(zmq.ROUTER)
    id_str = "test_%d" % (os.getpid())
    slave.setsockopt(zmq.IDENTITY, id_str)
    slave.setsockopt(zmq.LINGER, 0)
    slave.setsockopt(zmq.HWM, 1)
    slave.setsockopt(zmq.BACKLOG, 1)
    slave.connect("tcp://localhost:2001")
    slave.connect("tcp://192.168.44.25:2001")
    to_send = [
        "urn:uuid:49481fb4-4ca7-11e1-85fb-001f161a5a03",
        "urn:uuid:2f9f5348-8348-11e1-b4f3-00216a4d8630"
    ]
    to_receive = 0
    time.sleep(0.1)
    while to_send:
        print "send"
        to_receive += 1
        dst_id = to_send.pop(0)
        slave.send_unicode(dst_id, zmq.SNDMORE)
        slave.send_unicode(unicode(server_command.srv_command(command="load")))
    while to_receive:
        print "recv"
        data = []
        while True:
            data.append(slave.recv())
            if not slave.getsockopt(zmq.RCVMORE):
                break
        print data
        to_receive -= 1
    slave.close()
    ctx.term()

if __name__ == "__main__":
    main()
