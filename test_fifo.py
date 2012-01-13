#!/usr/bin/python-init -Ot

import os
import sys

def main():
    if len(sys.argv) > 1:
        for f_n in ["in", "out"]:
            if os.path.isfile("/tmp/%s" % (f_n)):
                os.unlink("/tmp/%s" % (f_n))
        # server test
        file("/tmp/bla", "w+").write("smsg" * 200000)
    else:
        # client test
        while True:
            in_bytes = file("/tmp/bla", "r").read()
            if in_bytes:
                print "Got: %d" % (len(in_bytes))
                break
    
if __name__ == "__main__":
    main()
