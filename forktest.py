#!/usr/bin/python -Ot

import os
import time
import sys

mp=os.fork()
if mp==0:
#  print "child.."
  sys.__stdout__.close()
  sys.__stderr__.close()
  sys.__stdin__.close()
  os._exit(1)

print mp
ret=os.wait()
print ret
time.sleep(2)
