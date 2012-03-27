#!/usr/bin/python-init -Ot

import ConfigParser
import os

def main():
    conf = ConfigParser.ConfigParser()
    if os.path.isfile("ptest"):
        conf.read("ptest")
    print type(conf.get("ALL", "NUM_PINGS"))
    if not conf.has_section("ALL"):
        conf.add_section("ALL")
    conf.set("ALL", "NUM_PINGS", {"a" : 4})
    conf.write(open("ptest", "w"))

if __name__ == "__main__":
    main()
    