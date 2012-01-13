#!/usr/bin/python -Ot

import sys
import pyipc
import struct
import string
import time
import getopt

STATE_CRITICAL  =  2
STATE_WARNING   =  1
STATE_OK        =  0
STATE_UNKNOWN   = -1
STATE_DEPENDENT = -2

STR_LEN         = 64

def main():
  ipc_sfmt="l"+str(STR_LEN)+"s"
  ipc_fmt="4l"+ipc_sfmt+ipc_sfmt
  mq=pyipc.MessageQueue(100,pyipc.IPC_CREAT|0666)
  try:
    opts,args=getopt.getopt(sys.argv[1:],"vhf")
  except:
    print "Commandline error!"
    sys.exit(STATE_CRITICAL)
  verbose=0
  for opt,arg in opts:
    if opt=="-f":
      print "Flushing queue..."
      num=0
      while 1:
        data=mq.receive()
        print struct.unpack(ipc_fmt,data)
        break
        if data:
          num+=1
        else:
          break
      print "Flushed %d messages"%(num)
      sys.exit(STATE_CRITICAL)
  fmt="4ll64sl64s"
  # Flush list
  flist=[]
  i=0
  while 1:
    # check flush-list
    print len(flist)
    while len(flist) > 10:
      checkid=flist.pop(0)
      # check if message was delivered
      data=mq.receive(type=checkid)
      #print checkid,data
      #print flist,flist.pop(0)
    i+=1
    data=mq.receive(type=1,flags=0)
    dtype,pid,port,cont,hlen,host,clen,command=struct.unpack(fmt,data)
    pid=int(pid)
    port=int(port)
    host=host[0:hlen]
    command=command[0:clen]
    print "Got command %s for host %s (port %d)"%(command,host,port)
    rstring=host+command+str(port)
    #time.sleep(3)
    sendpack=struct.pack(fmt,pid,0,0,0,0,"",len(rstring),rstring)
    flist.append(pid)
    mq.send(sendpack)

if __name__=="__main__":
  main()
