#!/usr/bin/python -Ot

import sys
import pyipc
import os

def main():
  pid=os.getpid()
  mq=pyipc.MessageQueue(100)
  mq.send_p([pid,"test"],type=1)
  data=mq.receive_p(type=pid,flags=0)
  print data

if __name__=="__main__":
  main()
  
