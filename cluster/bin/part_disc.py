#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import os
import os.path
import sys
import re
import string
import getopt
import errno
import stat
import commands
import MySQLdb
import MySQLdb.cursors, MySQLdb.converters
import mysql_tools

class part:
    mount=""
    part=""
    idx=0
    size=0
    # id
    id=0
    # 1 is ext2, 2 is reiserfs, 3 is ext3
    fs=0
    ext=0
    empty=0
    bootable=0
    def __init__(self,idx,device,mount="",size=0,fs=0,id="0x83",ext=0,empty=0,bootable=0,flags="defaults"):
        self.idx=idx
        self.device=device
        self.part=device+str(idx)
        self.mount=mount
        self.size=size
        self.fs=fs
        self.id=id
        self.ext=ext
        self.empty=empty
        self.bootable=bootable
        self.flags=flags
    def write(self):
        if self.ext:
            print "part %-10s is  extened"%(self.part)
        elif self.empty:
            print "part %-10s is    empty"%(self.part)
        else:
            if self.id=="0x82":
                print "part %-10s is     swap, size %10d MB on %s"%(self.part,self.size,self.mount)
            else:
                if self.size==0:
                    sstr="%10s   "%("<fill>")
                else:
                    sstr="%10d MB"%(self.size)
                if self.fs:
                    fst=self.fs
                else:
                    fst="other"
                print "part %-10s is %8s, size %s on %s"%(self.part,fst,sstr,self.mount)
    def sfdisk(self):
        if self.empty:
            outstr=";"
        else:
            outstr=","
            if not self.ext and self.size:
                outstr+="%d"%(self.size)
            outstr+=",%s"%(self.id)
            if self.bootable:
                outstr+=",*"
        print outstr
    def fstab(self):
        if not (self.ext or self.empty):
            if self.id=="0x82":
                print "%-16s %-26s %-16s %-16s %d %d"%(self.part,"swap","swap",self.flags,0,0)
            else:
                if self.fs:
                    dump_it=0
                    if self.mount=="/":
                        isroot=1
                    else:
                        isroot=2
                        if self.mount not in ["/boot"]:
                            dump_it=1
                    print "%-16s %-26s %-16s %-16s %d %d"%(self.part,self.mount,self.fs,self.flags,dump_it,isroot)
    def sql_str(self,db_con,p_idx,dev_dict):
        # determine freq/passno
        fs_freq,fs_passno=(0,0)
        if self.id != "0x82":
            if self.fs:
                fs_freq=0
                if self.mount=="/":
                    fs_passno=1
                else:
                    fs_passno=2
                    if self.mount not in ["/boot"]:
                        fs_freq=1
        hex_id_l=("%02x"%(int(self.id[2:],16))).lower()
        hex_id_s=("%x"%(int(self.id[2:],16))).lower()
        if self.fs:
            db_con.dc.execute("SELECT * FROM partition_fs WHERE name='%s'"%(MySQLdb.escape_string(self.fs)))
        else:
            db_con.dc.execute("SELECT * FROM partition_fs WHERE hexid='%s' OR hexid='%s'"%(hex_id_l,hex_id_s))
        fsp=db_con.dc.fetchall()
        if len(fsp):
            fsp_idx=fsp[0]["partition_fs_idx"]
        else:
            fsp_idx=0
        if self.empty:
            db_con.dc.execute("SELECT * FROM partition_fs WHERE identifier='d'")
            fsp_idx=db_con.dc.fetchone()["partition_fs_idx"]
            sq_str="%d,'%s','00',%d,'%s',%d,%d,%d,%d,%d"%(dev_dict[self.device],MySQLdb.escape_string(self.mount),self.size,MySQLdb.escape_string(self.flags),self.idx,self.bootable,fs_freq,fs_passno,fsp_idx)
        else:
            sq_str="%d,'%s','%s',%d,'%s',%d,%d,%d,%d,%d"%(dev_dict[self.device],MySQLdb.escape_string(self.mount),MySQLdb.escape_string(hex_id_s),self.size,MySQLdb.escape_string(self.flags),self.idx,self.bootable,fs_freq,fs_passno,fsp_idx)
        return sq_str
    def proc(self):
        print "%-16s %-26s %-16s %-16s %d %d"%("proc","/proc","proc","defaults",0,0)
    def proc_sql(self,db_con,part_idx):
        sq_str="%d,'proc','/proc','defaults'"%(part_idx)
        return sq_str

def main():
    global p_types
    p_types={}
    try:
        opts,args=getopt.getopt(sys.argv[1:],"hf:pvdD",["help","fstab","sfdisk"])
    except:
        print "Commandline error!"
        sys.exit(2)
    for lt in [re.split("\s+",x.strip(),1) for x in commands.getoutput("/sbin/sfdisk -T").lower().split("\n")[2:]]:
        a,b=lt
        p_types[b]=a
    #print p_types
    infile=None
    do_sfdisk=None
    do_fstab=None
    do_proc=None
    verbose=None
    showdev=None
    db_con=None
    for opt,arg in opts:
        if opt in ("-h","--help"):
            print "Usage: %s [-f infile] [-h|--help] [--fstab|--sfdisk] [-p] [-v] [-d]"%(os.path.basename(sys.argv[0]))
            print " -h,--help         this help"
            print " -f infile         sets the inputfile"
            print " --fstab           generate output for fstab"
            print " --sfdisk          generate output for sfdisk"
            print " -p                create additional proc-line for fstab"
            print " -v                show configuration"
            print " -d                show device"
            print " -D                inserts into database"
        if opt=="-f":
            infile=arg
        if opt=="--fstab":
            do_fstab=1
        if opt=="--sfdisk":
            do_sfdisk=1
        if opt=="-p":
            do_proc=1
        if opt=="-v":
            verbose=1
        if opt=="-d":
            showdev=1
        if opt=="-D":
            db_con=mysql_tools.db_con()
    if len(args) > 0:
        print "Commandline error!"
        sys.exit(2)

    if not infile:
        print "Need inputfile!"
        sys.exit(2)

    try:
        inf=open(infile,"r")
    except:
        print "Can't open file %s: %s"%(infile,sys.exc_info()[0])
        sys.exit(2)
    lines=inf.readlines()
    inf.close()
    devlist=[]
    device=None
    lnum=0
    if db_con:
        part_name=os.path.basename(infile)
        # check for old db-entires
        sql_str="SELECT * FROM partition_table WHERE name='%s'"%(MySQLdb.escape_string(part_name))
        db_con.dc.execute(sql_str)
        for pt in db_con.dc.fetchall():
            print "Found old db-entry for partition_table '%s', deleting ...."%(part_name)
            db_con.dc.execute("SELECT * FROM partition_disc WHERE partition_table=%d"%(pt["partition_table_idx"]))
            for pd in db_con.dc.fetchall():
                print "  Found disc %s, deleting ..."%(pd["disc"])
                db_con.dc.execute("DELETE FROM partition WHERE partition_disc=%d"%(pd["partition_disc_idx"]))
            db_con.dc.execute("DELETE FROM partition_disc WHERE partition_table=%d"%(pt["partition_table_idx"]))
            db_con.dc.execute("DELETE FROM sys_partition WHERE partition_table=%d"%(pt["partition_table_idx"]))
            db_con.dc.execute("DELETE FROM partition_table WHERE partition_table_idx=%d"%(pt["partition_table_idx"]))
        sql_str="INSERT INTO partition_table VALUES(0,'%s','%s',0,null)"%(MySQLdb.escape_string(part_name),MySQLdb.escape_string("Auto-generated %s by make_part_info/part_disc.py"%(part_name)))
        db_con.dc.execute(sql_str)
        part_idx=db_con.dc.insert_id()
        dev_dict={}
    parts=[]
    for actl in [x.strip() for x in lines]:
        lnum+=1
        try:
            if len(actl) > 0 and not re.match("^\s*#.*$",actl):
                ls=actl.split()#re.split("\s+",actl)
                #print actl,ls
                if ls[0]=="device":
                    extflag=0
                    idx=0
                    device=ls[1]
                    devlist.append(device)
                    if db_con:
                        sql_str="INSERT INTO partition_disc VALUES(0,%d,'%s',0,null)"%(part_idx,MySQLdb.escape_string(device))
                        db_con.dc.execute(sql_str)
                        dev_dict[device]=db_con.dc.insert_id()
                elif ls[0]=="dummy":
                    idx+=1
                    parts+=[part(idx,device,empty=1)]
                elif ls[0]=="swap":
                    if len(ls) > 2:
                        raise "p_error"
                    idx+=1
                    parts+=[part(idx,device,size=int(ls[1]),id="0x82")]
                elif ls[0]=="ext":
                    if extflag:
                        print "Extended flag already defined, exiting..."
                        raise "p_error"
                    extflag=1
                    if idx > 3:
                        print "Too many primary partitions, exiting..."
                        raise "p_error"
                    else:
                        idx+=1
                        if len(ls)==1:
                            parts+=[part(idx,device,id="0xf",ext=1)]
                        else:
                            parts+=[part(idx,device,id=ls[1],ext=1)]
                        if idx < 4:
                            for i in range(idx,4):
                                idx+=1
                                parts+=[part(idx,device,empty=1)]
                else:
                    mpoint=ls.pop(0)
                    if not mpoint[0] == "/":
                        raise "p_error"
                    id="0x83"
                    psize=int(ls.pop(0))
                    st=None
                    ptype=ls.pop(0)
                    if not ptype.startswith("0x"):
                        if not ptype in ["ext2","ext3","reiserfs","xfs"]:
                            raise "p_error"
                        else:
                            st=ptype
                            id="0x83"
                    else:
                        id=ptype
                    bf=0
                    flags="defaults"
                    while len(ls):
                        act_p=ls.pop(0)
                        if (act_p)=="*":
                            bf=1
                        else:
                            flags=act_p
                    idx+=1
                    parts+=[part(idx,device,mount=mpoint,size=psize,fs=st,id=id,bootable=bf,flags=flags)]
        except "p_error":
            print "Parse error in line %d (%s)!"%(lnum,actl)
            sys.exit(1)
    for p in parts:
        if verbose:
            p.write()
    if showdev:
        if len(devlist):
            print ", ".join(devlist)
        else:
            print "None"
    if do_sfdisk:
        for p in parts:
            p.sfdisk()
    if do_fstab:
        for p in parts:
            p.fstab()
        if do_proc:
            parts[0].proc()
    if db_con:
        for p in parts:
            sql_str=p.sql_str(db_con,part_idx,dev_dict)
            db_con.dc.execute("INSERT INTO partition VALUES(0,%s,null)"%(sql_str))
        if do_proc:
            sql_str=parts[0].proc_sql(db_con,part_idx)
            db_con.dc.execute("INSERT INTO sys_partition VALUES(0,%s,null)"%(sql_str))
            
    
if __name__=="__main__":
    main()
