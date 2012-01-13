#!/usr/bin/python -Ot

import string
import sys
import os
import select
import fcntl, FCNTL
import struct
import time
import signal
import socket
import msock

def sig_alarm_handler(signum,frame):
  rais_ex="alarm_event"
  raise rais_ex,signum

signal.signal(signal.SIGCHLD,signal.SIG_IGN)

nserv=msock.i_sock_server()
ok=0
ok+=nserv.add_socket(8000)
ok+=nserv.add_socket(8001)
if ok != 2:
  print "Error..."
  sys.exit(-1)
signal.signal(signal.SIGALRM,sig_alarm_handler)
n=0
signal.alarm(2)
while 1:
  try:
    sockl=nserv.wait()
  except "alarm_event",num:
    print "Alarm %d !"%(num)
    signal.alarm(2)
  else:
    if sockl:
      sock,w=sockl[0]
      sock.accept()
      mpid=os.fork()
      n=n+1
      if not mpid:
        print "Got: %s"%(sock.receive())
        sock.send("return")
        sock.close()
        os._exit(0)
      print "%d"%(n)
nserv.del_socket(8000)
nserv.del_socket(8001)
sys.exit(0)
