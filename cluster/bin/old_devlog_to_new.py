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
    for tab_name in ["config_int","config_str","config_blob"]:
        mync.execute("DELETE FROM %s"%(tab_name))
    mync.execute("SELECT * FROM log_source ls")
    ls_dict={}
    for x in mync.fetchall():
        ls_dict[x["identifier"]]=x
    mync.execute("SELECT * FROM devicelog l")
    all_logs=mync.fetchall()
    for log in all_logs:
        if log["creator"]==0:
            new_ls=ls_dict["user"]["log_source_idx"]
        elif log["creator"]==1:
            new_ls=ls_dict["node"]["log_source_idx"]
        elif log["creator"]==2:
            new_ls=ls_dict["mother"]["log_source_idx"]
        else:
            new_ls=0
        sql_str="UPDATE devicelog set log_source=%d WHERE devicelog_idx=%d"%(new_ls,log["devicelog_idx"])
        print sql_str
        mync.execute(sql_str)

if __name__=="__main__":
    main()
