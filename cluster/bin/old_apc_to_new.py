#!/usr/bin/python -Ot
import os
import os.path
import sys
import struct
import socket
import select
import string
import re
import time
import signal
import getopt
import msock
import Queue
import threading
import types
import pty
import pinger
import configfile
import MySQLdb
import MySQLdb.cursors
import commands
import logging_tools
import gdbm
import shutil
import tempfile

def main():
    csuc,cfile=configfile.readconfig("/usr/local/cluster/etc/mysql.cf",1)
    if not csuc:
        print "Can't find configfile !"
        sys.exit(-2)
    db=MySQLdb.connect(cfile["MYSQL_HOST"],user=cfile["MYSQL_USER"],passwd=cfile["MYSQL_PASSWD"],db=cfile["MYSQL_DATABASE"])
    mync=MySQLdb.cursors.DictCursor(db)
    mync.execute("SELECT d.device_idx,d.mswitch,d.outlet FROM device d WHERE d.outlet")
    mach_d={}
    for a in mync.fetchall():
        mach_d[8*a["mswitch"]+a["outlet"]]=a
    mync.execute("SELECT m.device,m.outlet,m.msoutlet_idx FROM msoutlet m")
    outlet_d={}
    for a in mync.fetchall():
        outlet_d[8*a["device"]+a["outlet"]]=a
    #print mach_d
    #print outlet_d
    for devk in mach_d.keys():
        act_d=mach_d[devk]
        mync.execute("UPDATE msoutlet SET slave_device=%d WHERE msoutlet_idx=%d"%(act_d["device_idx"],outlet_d[devk]["msoutlet_idx"]))

if __name__=="__main__":
    main()
