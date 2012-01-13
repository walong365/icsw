#!/usr/bin/python-init -Ot

import xmlrpclib
import sys
import SimpleXMLRPCServer
import commands
import time
import SocketServer
import threading

class my_server(SocketServer.ThreadingMixIn, SimpleXMLRPCServer.SimpleXMLRPCServer):
    threading.currentThread().setName("server")
    pass
        
class my_handler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = ["/monitor", "/monitor/test"]
    def log_message(self, what, *args):
        print "****", threading.currentThread().getName()
        print what, args

class my_class(object):
    def __init__(self):
        self.value = 1 / 0
        self.value = 4
        
def rpm_list():
    time.sleep(10)
    return "1", 2, {"COMPLEX_DICT" : 4}, my_class()
    
def main():
    my_srv = my_server(("", 8081), requestHandler=my_handler)
    my_srv.register_introspection_functions()
    my_srv.register_function(pow)
    my_srv.register_function(rpm_list, "rpm_list")
    my_srv.serve_forever()
    pass

if __name__ == "__main__":
    main()
    