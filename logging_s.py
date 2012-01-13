#!/usr/bin/python -Ot

import asyncore
import socket
import time
import os

class s_obj(asyncore.dispatcher):
    def __init__(self,socket=None):
        asyncore.dispatcher.__init__(self,sock=socket)
        self.buffer=""
        self.w_ok=0
        print "st:",time.time()
    def handle_connect(self):
        print "hc"
    def writable(self):
        return self.w_ok
    def handle_accept(self):
        sock,source=self.accept()
        new_s=s_obj(sock)
    def handle_write(self):
        #self.send("00000004okdd")
        self.w_ok=0
        print "et:",time.time()
        #pass
    def handle_read(self):
        self.buffer+=self.recv(200000)
        print "sb",self.buffer
        if len(self.buffer) > 8:
            b_len=len(self.buffer[0:8])
            self.w_ok=1
        #self.send("00000002ok")
    #def connect(self,adr):
    #    print "con",adr
    pass

def main():
    a=s_obj()
    b=s_obj()
    a.create_socket(socket.AF_INET,socket.SOCK_STREAM)
    b.create_socket(socket.AF_UNIX,socket.SOCK_DGRAM)
    try:
        os.unlink("/tmp/pylog")
    except:
        pass
    print a.bind(("",8008))
    print b.bind("/tmp/pylog")
    a.listen(5)
    #b.listen(5)
    asyncore.loop()
    time.sleep(20)

if __name__=="__main__":
    main()
    
