#!/usr/bin/python-init -Ot

import xmlrpclib
import sys
import SimpleXMLRPCServer
import time

NUM_TESTS = 0

class my_class(object):
    def __init__(self):
        self.value = 4

def main():
    my_client = xmlrpclib.ServerProxy("http://localhost:8081/monitor/test")
    # stresstest
    print my_client.rpm_list()
    s_time = time.time()
    for idx in xrange(NUM_TESTS):
        my_client.pow(4, 5)
    e_time = time.time()
    print NUM_TESTS, e_time - s_time, (e_time - s_time) / NUM_TESTS
    print my_client.system.listMethods()
    print dir(my_client)

if __name__ == "__main__":
    main()
