#!/usr/bin/python-init -Otu

import zmq

def main():
    c = zmq.Context()
    s = c.socket(zmq.ROUTER)
    s.bind("ipc:///tmp/bla")
    s.setsockopt(zmq.LINGER, 0)
    s.setsockopt(zmq.HWM, 5)
    while True:
        in_data = []
        while True:
            in_data.append(s.recv())
            if not s.getsockopt(zmq.RCVMORE):
                break
        print in_data
        s.send_unicode(in_data[0], zmq.SNDMORE)
        s.send_unicode(in_data[1])

if __name__ == "__main__":
    main()
    