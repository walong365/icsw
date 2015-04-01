#!/usr/bin/python-init -Otu

import time
import logging_tools
import os
import sys

def log(what):
    logging_tools.my_syslog("%d: %s" % (os.getpid(),
                                        what))
    try:
        sys.stdout.write(what)
    except:
        logging_tools.my_syslog("%d: cannot write to stdout" % (os.getpid()))

def main():
    log("go")
    for i in xrange(60):
        time.sleep(1)
        #print "."
    log("end")
    
if __name__ == "__main__":
    main()
    
