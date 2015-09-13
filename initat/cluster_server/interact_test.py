#!/usr/bin/python-init -Otu

from __future__ import print_function

import os
import shlex
import subprocess
import select
import time


class IAClass(object):
    def __init__(self, cmd):
        self.cmd = cmd
        self._po = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )

    def wait(self):
        def anything_read(filenos):
            _any = False
            for _rl in filenos:
                _c = _rl.read(1)
                if _c:
                    _stdout.append(_c)
                    _any = True
            return _any

        while True:
            # global buffer
            _stdout = []
            while True:
                _rlist, _wlist, _xlist = select.select([self._po.stdout, self._po.stderr], [], [self._po.stdout, self._po.stderr], 0.1)
                if _rlist:
                    if not anything_read(_rlist):
                        break
                else:
                    break
            if _stdout:
                print(*_stdout, end="", sep="")
            _ret = self._po.poll()
            if _ret is not None:
                self.retcode = _ret
                break
            # time.sleep(0.1)


def main():
    print ("Interactive test")
    # _iac = IAClass("zypper dup")
    _iac = IAClass("zypper in zaz")
    _iac.wait()
    _iac = IAClass("ls -la")
    _iac.wait()

if __name__ == "__main__":
    main()
