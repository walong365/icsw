#!/usr/bin/python -Ot

import string,sys,os
import socket
import msock
import time
import getopt


sock=msock.i_sock(autoclose=1)
sock.connect("miraculix",8000)
sock.send(string.join(sys.argv[1:]," "))
print "Got: %s"%(sock.receive())
sock.close()
