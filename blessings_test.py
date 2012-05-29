#!/usr/bin/python-init -Otu

import blessings
import time

def main():
    term = blessings.Terminal()
    print "{t.red}red{t.green}asdsad{t.normal}rest".format(t=term)
    with term.location(0, term.height - 1):
        for x in xrange(10):
            print ("xd" * (x + 1) * 20)[0:term.width - 1]
    time.sleep(60)

if __name__ == "__main__":
    main()
