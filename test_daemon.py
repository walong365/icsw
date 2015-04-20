#!/usr/bin/python-init -Otu

import daemon
import time
import imp
import threading
import setproctitle
import sys
import pprint
import importlib


def main():
    name = "initat.mother.main"
    print setproctitle.setproctitle("icsw.mother")
    print setproctitle.getproctitle()
    sys.argv = ["mother.py", "-d"]
    _t = threading.currentThread()
    print _t.getName()
    print dir(_t)
    _d = importlib.import_module(name)
    # print "++", _d.main()
    # _d.main()
    # print "***"
    # return 0
    with daemon.DaemonContext(detach_process=True):
        _d.main()
        time.sleep(400)
    print "+"


if __name__ == "__main__":
    main()
