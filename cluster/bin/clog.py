#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2012,2013 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
# 
# This file belongs to cluster-backbone
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

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import logging_tools
import argparse
from initat.cluster.backbone.models import devicelog, log_source, log_status, device
from django.db.models import Q

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--mode", type=str, default="list", choices=["list", "create"], help="operation mode [%(default)s]")
    my_parser.add_argument("-s", type=str, default="i", choices=log_status.objects.values_list("identifier", flat=True), help="log status [%(default)s]")
    my_parser.add_argument("-d", type=str, default=device.objects.get(Q(device_group__cluster_device_group=True)).name, choices=device.objects.all().values_list("name", flat=True).order_by("name"), help="device to create log_entry [%(default)s]")
    my_parser.add_argument("-f", type=str, default="", choices=device.objects.all().values_list("name", flat=True).order_by("name"), help="device to show logs for [%(default)s]")
    my_parser.add_argument("text", nargs="*")
    def_log_source = log_source.objects.get(Q(identifier='user'))
    opts = my_parser.parse_args()
    ret_code = -1
    if opts.mode == "list":
        if opts.f:
            def_query = Q(device__name=opts.f)
        else:
            def_query = Q()
        all_logs = devicelog.objects.filter(def_query).select_related("log_source", "log_status", "user", "device").order_by("-date")
        print "%s found:" % (logging_tools.get_plural("Log entry", all_logs.count()))
        new_entry = logging_tools.new_form_list()
        for cur_dl in all_logs:
            new_entry.append([
                logging_tools.form_entry(unicode(cur_dl.date), header="date"),
                logging_tools.form_entry(unicode(cur_dl.device), header="device"),
                logging_tools.form_entry(unicode(cur_dl.log_source), header="source"),
                logging_tools.form_entry(unicode(cur_dl.log_status), header="status"),
                logging_tools.form_entry(unicode(cur_dl.user), header="user"),
                logging_tools.form_entry(unicode(cur_dl.text), header="text"),
            ])
        print unicode(new_entry)
        ret_code = 0
    elif opts.mode == "create":
        if not opts.text:
            print "no text entered"
        else:
            log_dev = device.objects.get(Q(name=opts.d))
            new_log_entry = devicelog.new_log(log_dev, def_log_source, log_status.objects.get(Q(identifier=opts.s)), " ".join(opts.text))
            ret_code = 0
            print "created '%s'" % (unicode(new_log_entry))
    else:
        print "Uknown mode '%s'" % (opts.mode)
    sys.exit(ret_code)
    # old code
##    try:
##        opts,args=getopt.getopt(sys.argv[1:],"hlevs:d:au:n:")
##    except:
##        print "Error parsing commandline: %s"%(" ".join(sys.argv[:]))
##        sys.exit(1)
##    db_con=mysql_tools.db_con()
##    # get default-user and default device
##    db_con.dc.execute("SELECT u.user_idx,u.login FROM user u LIMIT 1")
##    user=db_con.dc.fetchone()
##    user_name,user_idx=(user["login"],user["user_idx"])
##    db_con.dc.execute("SELECT * FROM user")
##    log_users={}
##    for x in db_con.dc.fetchall():
##        log_users[x["user_idx"]]=x
##    #device,device_name=(0,"Cluster")
##    # get user-logsource
##    db_con.dc.execute("SELECT s.log_source_idx FROM log_source s WHERE s.identifier='user'")
##    user_log_source=db_con.dc.fetchone()["log_source_idx"]
##    db_con.dc.execute("SELECT * FROM log_source")
##    log_sources={}
##    for x in db_con.dc.fetchall():
##        log_sources[x["log_source_idx"]]=x
##    # get log-status
##    db_con.dc.execute("SELECT * FROM log_status")
##    #log_status={}
##    ls_idx={}
##    for x in db_con.dc.fetchall():
##        ls_idx[x["log_status_idx"]]=x
##        #log_status[x["name"]]=x["log_status_idx"]
##    def_log_status=log_status.keys()[0]
##    num_limit=100
##    for opt,arg in opts:
##        if opt=="-h":
##            print "Usage: %s [ OPTIONS ]"%(os.path.basename(sys.argv[0]))
##            print " -d DEVICES     selects the device (default: %s)"%(device_name)
##            print " -u USER        sets the user of used to add the logentry (default: %s)"%(user_name)
##            print " -a             add log to device selected via -d (or to the cluster)"
##            print " -s STATUS      sets the status for the log-entry (on of %s, default is %s)"%(", ".join(log_status.keys()),def_log_status)
##            print " -n NUM         sets the number of lines to retrive for -l (default is %d)"%(num_limit)
##            print " -v             shows all devicegroups/devices and stuff"
##            print " -l             lists the device-log of the selected device"
##            print " -e             lists the device-log of the selected device with extended logs"
##            sys.exit(0)
##        if opt=="-n":
##            try:
##                num_limit=max(1,int(arg))
##            except:
##                print "Cannot parse number %s"%(arg)
##                sys.exit(-1)
##            else:
##                print "Setting nuber of lines to %d"%(num_limit)
##        if opt=="-v":
##            #for x in
##            db_con.dc.execute("SELECT d.name,d.device_idx,dg.name AS dgname,dt.description,DATE_FORMAT(MAX(l.date),'%a, %d. %b %Y %H:%i:%s') AS latest_log,DATE_FORMAT(MIN(l.date),'%a, %d. %b %Y %H:%i:%s') AS first_log,COUNT(l.devicelog_idx) as logcount FROM device d INNER JOIN device_group dg INNER JOIN device_type dt LEFT JOIN devicelog l ON (l.device=d.device_idx ) WHERE d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx GROUP BY dg.name,d.name")
##            out_list=[]
##            for x in db_con.dc.fetchall():
##                out_list+=[[x["name"],x["device_idx"],x["dgname"],x["description"],x["logcount"],x["latest_log"],x["first_log"]]]
##            f_str=[("-","%s"),("","%d"),("-","%s"),("-","%s"),("","%d"),("-","%s"),("-","%s")]
##            write_out(out_list,["DevName","Idx","DevGrpName","DevType","logs","latest","first"],f_str)
##        if opt=="-s":
##            if log_status.has_key(arg):
##                def_log_status=arg
##                print "Using log-status %s"%(def_log_status)
##            else:
##                print "Log-status %s not found in list %s"%(arg,", ".join(log_status.keys()))
##                sys.exit(-1)
##        if opt=="-d":
##            db_con.dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'"%(arg))
##            #device=db_con.dc.fetchone()
##            if device:
##                #device,device_name=(device["device_idx"],arg)
##                print "Selected device %s (%d)"%(device_name,device)
##            else:
##                print "No device named '%s' found in database"%(arg)
##                sys.exit(-1)
##        if opt=="-u":
##            db_con.dc.execute("SELECT u.user_idx FROM user u WHERE u.login='%s'"%(arg))
##            user=db_con.dc.fetchone()
##            if user:
##                user_name,user_idx=(arg,user["user_idx"])
##                print "Selected user %s (%d)"%(user_name,user_idx)
##            else:
##                print "No user named '%s' found in database"%(arg)
##                sys.exit(-1)
##        if opt=="-a":
##            if device==0:
##                dev_name="Cluster"
##            else:
##                db_con.dc.execute("SELECT d.name FROM device d WHERE d.device_idx=%d"%(device))
##                dev_name=db_con.dc.fetchone()["name"]
##            print "Adding logentry to device %s using user %s"%(dev_name,user_name)
##            print " - enter NOLOG to enter nothing"
##            while 1:
##                ret=getinput(" - text: ")
##                if ret:
##                    break
##            if ret=="NOLOG":
##                print " adding no log-entry"
##            else:
##                db_con.dc.execute("INSERT INTO devicelog VALUES(0,%d,%d,%d,%d,'%s',null)"%(device,user_log_source,user_idx,log_status[def_log_status],MySQLdb.escape_string(ret)))
##                print "Insert log with log-text '%s' at index %d"%(ret,db_con.dc.insert_id())
##        if opt in ["-l","-e"]:
##            db_con.dc.execute("SELECT l.devicelog_idx,l.log_source,l.user,l.log_status,l.text,DATE_FORMAT(l.date,'%%a, %%d. %%b %%Y %%H:%%i:%%s') AS etime,DATE_FORMAT(el.date,'%%a, %%d. %%b %%Y %%H:%%i:%%s') AS eltime,el.user AS eluser, el.users,el.subject,el.description,el.extended_log_idx FROM devicelog l LEFT JOIN extended_log el ON el.devicelog=l.devicelog_idx WHERE l.device=%d ORDER BY l.date DESC,el.date ASC LIMIT %d"%(device,num_limit))
##            out_list=[]
##            last_idx=0
##            for x in db_con.dc.fetchall():
##                act_idx=x["devicelog_idx"]
##                if act_idx != last_idx:
##                    out_list+=[["Log",x["etime"],act_idx,log_sources[x["log_source"]]["name"],log_users.get(x["user"],{"login":"---"})["login"],ls_idx[x["log_status"]]["name"],x["text"]]]
##                    last_idx=act_idx
##                if x["description"] and opt=="-e":
##                    out_list+=[" EL %s %5d, User: %s, users: %s"%(x["eltime"],x["extended_log_idx"],log_users.get(x["eluser"],{"login":"---"})["login"],x["subject"])]
##                    line_num=0
##                    for line in [y for y in x["description"].split("\n") if len(y.strip())]:
##                        line_num+=1
##                        out_list+=["        line # %3d : %s"%(line_num,line)]
##            f_str=[("-","%s"),("-","%s"),("","%d"),("-","%s"),("","%s"),("","%s"),("-","%s")]
##            write_out(out_list,["Type","Date","idx","source","user","status","text"],f_str)
##    del db_con
    
if __name__ == "__main__":
    main()
    
