#!/usr/bin/python-init -Otu

import zmq

def main():
    c = zmq.Context()
    s = c.socket(zmq.DEALER)
    s.setsockopt(zmq.IDENTITY, "client")
    s.connect("ipc:///tmp/bla")
    s.send_unicode("test")
    print s.recv_unicode()

if __name__ == "__main__":
    main()
