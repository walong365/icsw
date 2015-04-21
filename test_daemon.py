#!/usr/bin/python-init -Otu

import daemon
import time
import imp
import threading
import setproctitle
import sys
import pprint
import importlib
import os


def main():
    name = "initat.mother.main"
    print
    sys.argv = ["mother.py", "-d"]
    # print "++", _d.main()
    # _d.main()
    # print "***"
    # return 0
    for idx in xrange(5):
        if not os.fork():
            with daemon.DaemonContext():  # detach_process=True):
                setproctitle.setproctitle("icsw.mother")
                importlib.import_module(name).main()
                print "done"
        print "wait.."
        time.sleep(5)


if __name__ == "__main__":
    main()
