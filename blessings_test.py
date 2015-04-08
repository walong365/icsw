#!/usr/bin/python-init -Otu

import blessings
import time
import tty, sys, termios

def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def main():
    term = blessings.Terminal()
    print "{t.red}red{t.green}asdsad{t.normal}rest".format(t=term)
    with term.location(0, term.height - 1):
        for x in xrange(30):
            print ("xd" * (x + 1) * 4)[0:term.width - 1]
    print getch()
    a = raw_input()
    print a
    time.sleep(60)

if __name__ == "__main__":
    main()
