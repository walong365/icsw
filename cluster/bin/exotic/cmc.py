#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# This file is part of rms-tools
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

import termios, sys
try:
    import readline
except ImportError:
    readline=None
import re,os
import getopt
import string
import MySQLdb
import MySQLdb.cursors, MySQLdb.converters
import time
import configfile
import posix
import types

def is_ip(str):
    ok=1
    try:
        ipl=str.split(".")
    except:
        ok=0
    else:
        if len(ipl)==4:
            for ipd in ipl:
                try:
                    ipdi=int(ipd)
                except:
                    pass
                else:
                    if ipdi < 0 or ipdi > 255:
                        ok=0
        else:
            ok=0
    return ok

def ip_and(ip,ms):
    ok=1
    rets=""
    ips=ip.split(".")
    mss=ms.split(".")
    if len(ips) == 4 and len(mss) == 4:
        for idx in range(4):
            ips[idx]=str(int(ips[idx])&int(mss[idx]))
        rets=".".join(ips)
    else:
        print "Only IPv4 ! ",ip,ms
        ok=0
    return ok,rets


def get_name(instr):
    gns=re.match("^([a-zA-Z\d]+)(.*)$",instr)
    if gns:
        return gns.group(1),gns.group(2)
    else:
        return None,instr

def split_line(instr,endchar=None,slist=None):
    #print "***",instr
    if endchar:
        lpart=["?"]
        rpart=[endchar]
    else:
        lpart=[""]
        rpart=[""]
    if slist is None:
        slist=[("{","}",0),("(",")",0),("[","]",0),("'","'",1),('"','"',1)]
    modes=[0]
    escstr="\\"
    nstr=""
    list=[]
    nest=0
    esc=0
    idx=0
    endfound=0
    for c in instr:
#    print idx,c
        idx=idx+1
        if c==rpart[nest] and not esc:
            list.append((nest,0,modes.pop(),rpart.pop(),nstr))
            lpart.pop()
            #print nest,lpart,rpart,":",nstr
            nest=nest-1
            nstr=""
            if endchar:
                if c==endchar:
                    endfound=1
            if nest < 0 or endfound: break
        else:
            found=0
            if not esc:
                for lp,rp,mode in slist:
                    if c==lp:
                        lpart.append(lp)
                        rpart.append(rp)
                        modes.append(mode)
                        list.append((nest,1,0,lp,nstr))
                        found=1
                        #print nest,lpart,rpart,":",nstr
                        nest=nest+1
                        nstr=""
                        break
            if not found:
                if esc:
                    esc=0
                else:
                    if c==escstr:
                        esc=1
                nstr=nstr+c
    rest=instr[idx:]
    if not endchar and nest==0:
        if len(nstr):
            list.append((0,0,0,'',nstr))
        list.append((0,0,0,'',''))
        endfound=1
    #for lev,side,mode,sep,str in list:
    #  if side:
    #    print "> %s%s %s<"%(2*"-"*lev,str,sep)
    #  else:
    #    print "> %s%s<"%(2*"-"*lev,str)
    #    print "> %s%s<"%(2*"-"*(lev-1),sep)
    res=[]
    actstr=""
    actlev=0
    lastmode=0
    rsep="?"
    for lev,side,mode,sep,str in list:
        if lev==actlev:
            if len(actstr):
                if len(rsep):
                    if actstr[-1]==rsep:
                        actstr=actstr[0:-1]
                res.append((actstr,lsep,rsep,lastmode))
                actstr=""
            if len(str.strip()):
                res.append((str,"","",0))
            lsep=sep
            actstr=""
            if side==1:
                lastmode=mode
        else:
            if side:
                actstr=actstr+str+sep
            else:
                actstr=actstr+str+sep
                lastmode=mode
                rsep=sep
    #for r in res:
    #  print r
    return res,rest,endfound

class mlc:
    comlist=[]
    quit_flag=0
    varlist={}
    def __init__(self):
        self.comlist=[]
        self.varlist={}
        self.quit_flag=0
    def add_command(self,com):
        self.comlist.append(com)
    def get_command(self,name):
        for c in self.comlist:
            if c.name==name:
                return c
        return None
    def is_command(self,name):
        return name in [x.name for x in self.comlist]
    def call_command(self,name,rest):
        rbuffer=re.split("\s+",rest.strip())
        #print rest
        for c in self.comlist:
            if c.name==name:
                return c.func(rbuffer)
        else:
            print "Command "+name+" not known"
        return 0
    def mainloop(self,lines=None):
        actl=0
        inbuff=""
        while self.quit_flag==0:
            if len(lines):
                line=lines.pop(0)
                #actl=actl+1
                #print actl,line
            else:
                actl=actl+1
                line=getinput("%d >"%(actl))
            instr=line.strip()
            if len(instr) and not re.match("^#.*$",instr):
                inbuff=string.strip("%s %s"%(inbuff,instr))
                endf=1
                while endf:
                    endf=0
                    lsplit,restbuff,endf=split_line(inbuff.strip(),";")
                    if endf:
                        inbuff=restbuff
                    #print len(lsplit),"inbuff:",inbuff
                    fbuffer=""
                    for lse,lsep,rsep,mode in lsplit:
                        fbuffer+=lsep+lse+rsep
                    fbuffer=fbuffer.strip()
                    if len(fbuffer)==0:
                        endf=0
                    if endf:
                        #print "Nc3"
                        ret=self.call_command3(fbuffer)
        return
    def proc_inputc(self,str):
        endf=1
        while endf:
            endf=0
            lsplit,restbuff,endf=split_line(str.strip(),";")
            if endf:
                str=restbuff
                #print len(lsplit),"inbuff:",inbuff
            fbuffer=""
            for lse,lsep,rsep,mode in lsplit:
                fbuffer+=" "+lsep+lse+rsep
            fbuffer=fbuffer.strip()
            if len(fbuffer)==0:
                endf=0
            if endf:
                #print "Sc3",fbuffer
                ret=self.call_command3(fbuffer,in_template=1)
        return str
    def call_command3(self,buff,need_ret=0,in_template=0):
        ret=-666
        buff=buff.strip()
        eqm=re.match("^\$([a-zA-Z\d_]+)\s*=(.*)$",buff)
        if eqm:
            eq_mode=1
            var_name=eqm.group(1)
            buff=eqm.group(2)
        else:
            eq_mode=0
        tcsplit,rbuff,tsuc=split_line(buff,endchar=None,slist=[('"','"',1)])
        if tsuc:
            ret=""
            for astr,ls,rs,tmode in tcsplit:
                #print tmode,astr
                if tmode==0:
                    rep=1
                    while rep:
                        rep=0
                        comsplit,restbuff,suc=split_line(astr,endchar=None,slist=[("{","}",0)])
                        #print "+++",fbuffer,restbuff,comsplit
                        nbuff=""
                        if suc:
                            for lse,lsep,rsep,mode in comsplit:
                                if lsep=="{":
                                    rep=1
                                    nbuff=nbuff+str(self.call_command3(lse,1))
                                else:
                                    nbuff=nbuff+lse
                                nbuff=nbuff.strip()
                            #print nbuff
                            # replace variables
                            if nbuff:
                                varc=1
                                while varc:
                                    var=re.match("^(.*)\$(.*)$",nbuff)
                                    if var:
                                        rep=1
                                        varname,rest=get_name(var.group(2))
                                        rest=rest.strip()
                                        vrep=0
                                        if len(rest):
                                            if rest[0]=="[":
                                                varsplit,restbuff2,suc2=split_line(rest[1:],endchar="]",slist=[])
                                                vrep=1
                                                rest=restbuff2
                                        if self.varlist.has_key(varname):
                                            realvar=self.varlist[varname]
                                        else:
                                            print "Variable "+varname+" not defined"
                                            realvar=""
                                        if vrep:
                                            localvars={}
                                            idx=0
                                            varsplit,d1,d2,d3=varsplit[0]
                                            for vrval in re.split("\s+",varsplit):
                                                idx=idx+1
                                                localvars[str(idx)]=vrval
                                            #print localvars
                                            lvarc=1
                                            while lvarc:
                                                lvarc=0
                                                lvar=re.match("^(.*)\$(\d+)(.*)$",realvar)
                                                if lvar:
                                                    lvarc=1
                                                    realvar=lvar.group(1)+localvars[lvar.group(2)]+lvar.group(3)
                                            ret=self.proc_inputc(realvar)
                                            if len(ret.strip()):
                                                print "RET:",ret
                                            nbuff=var.group(1)+" "+rest
                                        else:
                                            nbuff=var.group(1)+realvar+" "+rest
                                    else:
                                        varc=0
                                nbuff=nbuff.lstrip()
                                if len(nbuff):
                                    comname,fbuffer=get_name(nbuff)
                                    if self.is_command(comname):
                                        astr=str(self.call_command(comname,fbuffer))
                                    else:
                                        if in_template:
                                            try:
                                                comname_int=int(comname)
                                            except:
                                                print "Unknown command in template "+comname
                                        else:
                                            if not eq_mode:
                                                if comname:
                                                    print "Unknown command "+comname
                                                else:
                                                    print "Unknown command <comname NULL>"
                                        astr=nbuff
                                else:
                                    fbuffer=""
                                    astr=""
                        else:
                            print "Some error occured while parsing %s"%(buff)
                            rep=0
                ret+=" "+astr
            ret=ret.strip()
            #print "res:",ret
        else:
            print "Some error occured while parsing %s"%(buff)
        #print ret,eq_mode
        if eq_mode:
            self.varlist[var_name]=str(ret)
        return ret
        ret=self.call_command(comname,fbuffer)
        #print "******",buff
        if buff[0]=='"' and buff[-1]=='"':
            return buff[1:-1]
        ret=-666
        cok=0
        comname,fbuffer=get_name(buff)
        if len(fbuffer):
            if fbuffer[0]==" ":
                if self.is_command(comname):
                    cok=1
                else:
                    print "No command named %s found !"%(comname)
            else:
                if buff[0]=="$":
                    buff=buff[1:]
                    if self.varlist.has_key(buff):
                        ret=self.varlist[buff]
                else:
                    print "Error reading commandname %s, input was %s !"%(comname,buff)
        else:
            if self.is_command(comname):
                cok=1
            else:
                print "No command named %s found !"%(comname)
    def call_command2(self,buff,need_ret=0):
        buff=buff.strip()
        #print "******",buff
        if buff[0]=='"' and buff[-1]=='"':
            return buff[1:-1]
        ret=-666
        cok=0
        comname,fbuffer=get_name(buff)
        if len(fbuffer):
            if fbuffer[0]==" ":
                if self.is_command(comname):
                    cok=1
                else:
                    print "No command named %s found !"%(comname)
            else:
                if buff[0]=="$":
                    buff=buff[1:]
                    if self.varlist.has_key(buff):
                        ret=self.varlist[buff]
                else:
                    print "Error reading commandname %s, input was %s !"%(comname,buff)
        else:
            if self.is_command(comname):
                cok=1
            else:
                print "No command named %s found !"%(comname)
        if cok:
            fbuffer=fbuffer.strip()
            com=self.get_command(comname)
            if need_ret and com.ret_value==0:
                print "Command %s has no return value !"%(comname)
            else:
                rep=1
                while rep:
                    rep=0
                    comsplit,restbuff,suc=split_line(fbuffer,endchar=None,slist=[("{","}",0)])
                    #print "+++",fbuffer,restbuff,comsplit
                    nbuff=""
                    if suc:
                        for lse,lsep,rsep,mode in comsplit:
                            if lsep=="{":
                                rep=1
                                nbuff=nbuff+str(self.call_command2(lse,1))
                            else:
                                nbuff=nbuff+lse
                            nbuff=nbuff.strip()
                        #print nbuff
                        # replace variables
                        varc=1
                        while varc:
                            var=re.match("^(.*)\$(.*)$",nbuff)
                            if var:
                                rep=1
                                varname,rest=get_name(var.group(2))
                                nbuff=var.group(1)+self.varlist[varname]+rest
                            else:
                                varc=0
                        fbuffer=nbuff.strip()
                    else:
                        print "Some error occured while parsing %s"%(fbuffer)
                        rep=0
                ret=self.call_command(comname,fbuffer)
        return ret

class command:
    name=""
    func=0
    ret_value=0
    def __init__(self,name,func,ret_value):
        self.name=name
        self.func=func
        self.ret_value=ret_value

def getpass(prompt="pw:"):
    fd = sys.stdin.fileno()
    try:
        #    termios.tcsetattr(fd, TERMIOS.TCSADRAIN, new)
        passwd = raw_input(prompt)
    finally:
        pass
#    termios.tcsetattr(fd, TERMIOS.TCSADRAIN, old)
    return passwd

def priv_check_nd(dict):
    if not re.match("^([a-fA-F\d]{2}:){5}[a-fA-F\d]{2}$",dict["macadr"]):
        print "Wrong syntax '%s' for the MAC-Address"%(dict["macadr"])
        ok=0
    else:
        ok=1
    return ok

def priv_check_ip(dict):
    ok=1
    if int(dict["network"]) > 0:
        dbcon.dc_priv.execute("SELECT * FROM network WHERE network_idx="+str(dict["network"]))
        nwdict=dbcon.dc_priv.fetchone()
        nmask=nwdict["netmask"]
        nwork=nwdict["network"]
        ip=dict["ip"]
        ok1,r1=ip_and(ip,nmask)
        ok2,r2=ip_and(nwork,nmask)
        if ok1*ok2:
            if not r1==r2:
                print "IP-Address %s not in network %s (netmask %s)"%(ip,nwork,nmask)
                ok=0
        else:
            ok=0
    return ok

class db_con:
    con=0
    sc=0
    dc=0
    def_dict={}
    ref_dict={}
    need_dict={}
    unique_dict={}
    ips_dict={}
    priv_check_dict={}
    def __init__(self,config):
        self.con=MySQLdb.connect(config["MYSQL_HOST"],user=config["MYSQL_USER"],passwd=config["MYSQL_PASSWD"],db=config["MYSQL_DATABASE"])
        self.sc=MySQLdb.cursors.Cursor(self.con)
        self.dc=MySQLdb.cursors.DictCursor(self.con)
        self.dc_priv=MySQLdb.cursors.DictCursor(self.con)
        self.def_dict={}
        self.ref_dict={}
        self.need_dict={}
        self.unique_dict={}
        self.ips_dict={}
        self.priv_check_dict={}
        self.new_ref_dict("device",{"device_group":("device_group",["name"]),
                                    "device_type":("device_type",["identifier","description"]),
                                    "ng_device":("ng_device",["name"]),
                                    "device_location":("device_location",["location"]),
                                    "device_class":("device_class",["classname"]),
                                    "mswitch":("device",["name"]),
                                    "newstate":("status",["status"]),
                                    "device_shape":("device_shape",["name"]),
                                    "switch":("device",["name"])
                                    })
        self.new_ref_dict("config",{"config_type":("config_type",["name"])})
        self.new_ref_dict("config_str",{"config":("config",["name"])})
        self.new_ref_dict("config_int",{"config":("config",["name"])})
        self.new_ref_dict("config_blob",{"config":("config",["name"])})
        self.new_ref_dict("device_config",{"config":("config",["name"]),
                                          "device":("device",["name"])})
        self.new_ref_dict("netip",{"network":("network",["name"]),
                                   "netdevice":("netdevice",["devname",{"device":("device",["name"])}])
                                   })
        self.new_ref_dict("ng_contact",{"snperiod":("ng_period",["name"]),"hnperiod":("ng_period",["name"])})
        #self.new_ref_dict("ng_ccgroup",{"ng_contact":("ng_contact",[{"ng_contact":("user",["login"])}]),
        #                                "ng_contactgroup":("ng_contactgroup",["name"])})
        self.new_ref_dict("ng_service_templ",{"nsc_period":("ng_period",["name"]),"nsn_period":("ng_period",["name"])})
        self.new_ref_dict("ng_sst",{"ng_service_templ":("ng_service_templ",["name"]),"ng_service":("ng_service",["name"])})
        self.new_ref_dict("ng_sst_host",{"ng_service":("ng_service",["name"]),"ng_service_templ":("ng_service_templ",["name"]),"ng_device":("ng_device",["name"])})
        self.new_ref_dict("ng_sst_device",{"ng_service":("ng_service",["name"]),
                                           "ng_service_templ":("ng_service_templ",["name"]),
                                           "device":("device",["name"])})
        self.new_ref_dict("ng_cgservicet",{"ng_contactgroup":("ng_contactgroup",["name"]),
                                           "ng_service_templ":("ng_service_templ",["name"])})
        self.new_ref_dict("ng_device",{"ng_period":("ng_period",["name"]),
                                       "ng_service_templ":("ng_service_templ",["name"])})
        self.new_ref_dict("ng_device_contact",{"device_group":("device_group",["name"]),
                                               "ng_contactgroup":("ng_contactgroup",["name"])})
        self.new_ref_dict("ggroup",{"export":("device_config",["device"])})
        self.new_ref_dict("user",{"ggroup":("ggroup",["ggroupname"])})
        self.new_ref_dict("ggroupcap",{"ggroup":("ggroup",["ggroupname"]),
                                       "capability":("capability",["name"])})
        self.new_ref_dict("netdevice",{"device":("device",["name"])})
        self.new_ref_dict("rrd_set",{"device":("device",["name"])})
        self.new_ref_dict("rrd_data",{"rrd_set":("rrd_set",["filename"])})
        self.new_ref_dict("ng_eh_device",{"ng_ext_host":("ng_ext_host",["icon_image","icon_image_alt"]),
                                          "device":("device",["name"])})
        self.new_ref_dict("device_connection",{"parent":("device",["name"]),
                                               "child":("device",["name"])})
        self.new_ref_dict("ng_mach_disable",{"device":("device",["name"])})
        self.new_ref_dict("session_data",{"user_idx":("user",["login"])})
        self.new_ref_dict("bootlog",{"device":("device",["name"])})
        self.new_ref_dict("macbootlog",{"device":("device",["name"])})
        self.new_ref_dict("devicelog",{"device":("device",["name"]),
                                       "user":("user",["login"]),
                                       "log_source":("log_source",["identifier","name"]),
                                       "log_status":("log_status",["identifier","name"])})
        self.new_ref_dict("serverlog",{"device":("device",["name"])})
        self.new_ref_dict("nb_event_log",{"netbotz":("netbotz",["name"]),
                                          "cluster_event":("cluster_event",["name"]),
                                          "nb_event":("nb_event",["lower_bound","upper_bound"])})
        self.new_ref_dict("msoutlet",{"mswitch":("mswitch",["name"]),
                                      "device":("device",["name"]),
                                      "slave_device":("device",["name"])})
        self.new_ref_dict("network",{"network_type":("network_type",["identifier","description"])
                                     })
        self.new_ref_dict("package",{"architecture":("architecture",["architecture"]),
                                     "vendor":("vendor",["vendor"]),
                                     "distribution":("distribution",["distribution"])
                                     })
        self.new_ref_dict("pi_connection",{"package":("package",["name","version","release"]),
                                           "image":("image",["name"])
                                           })
        self.new_ref_dict("inst_package",{"package":("package",["name","version","release"])}
                          )
        self.new_ref_dict("instp_device",{"inst_package":("inst_package",["location"]),
                                          "device":("device",["name"])}
                          )
        self.new_ref_dict("peer_information",{"s_netdevice":("netdevice",[{"device":("device",["name"])},"devname"]),
                                              "d_netdevice":("netdevice",[{"device":("device",["name"])},"devname"])}
                          )
        self.new_need_dict("genstuff",["name","value"])
        self.new_need_dict("status",["status"])
        self.new_need_dict("device",["name","device_group"])
        self.new_need_dict("switch",["name"])
        self.new_need_dict("netip",["ip","network"])
        self.new_need_dict("ng_period",["name","alias"])
        self.new_need_dict("ng_contact",["contact","snperiod","hnperiod"])
        self.new_need_dict("ng_contactgroup",["name","alias"])
        self.new_need_dict("ng_service_templ",["nsc_period","nsn_period"])
        self.new_need_dict("ng_service",["name","command","alias"])
        self.new_need_dict("ng_sst",["name","ng_service_templ","ng_service"])
        self.new_need_dict("ng_sst_host",["ng_service","ng_service_templ","ng_device"])
        self.new_need_dict("ng_sst_machine",["ng_service","ng_service_templ","machine"])
        self.new_need_dict("ng_cgservicet",["ng_contactgroup","ng_service_templ"])
        self.new_need_dict("ng_device",["name","ng_period","ng_service_templ"])
        self.new_need_dict("ng_device_contact",["device_group","ng_contactgroup"])
        self.new_need_dict("netdevice",["device","devname"])
        self.new_need_dict("network",["identifier","name","network","netmask","broadcast"])
        self.new_unique_dict("status",["status"])
        self.new_unique_dict("machine",["name"])
        self.new_unique_dict("switch",["name"])
        self.new_unique_dict("device_group",["name"])
        self.new_unique_dict("mswitch",["name"])
        self.new_unique_dict("switch",["name"])
        self.new_unique_dict("ng_period",["name","alias"])
        self.new_unique_dict("ng_contact",["name","alias"])
        self.new_unique_dict("ng_contactgroup",["name","alias"])
        self.new_unique_dict("ng_service_templ",["name"])
        self.new_unique_dict("ng_service",["name","alias"])
        self.new_unique_dict("ng_sst",["name"])
        self.new_unique_dict("ng_device",["name"])
        self.new_unique_dict("network",["info"])
        self.new_ips_dict("netip",["ip"])
        self.new_ips_dict("network",["network","netmask","broadcast","gateway"])
        self.new_priv_check("netdevice",priv_check_nd)
        self.new_priv_check("netip",priv_check_ip)

    def new_ref_dict(self,name,n_dict):
        self.ref_dict[name]=n_dict
    def new_need_dict(self,name,n_dict):
        self.need_dict[name]=n_dict
    def new_ips_dict(self,name,n_dict):
        self.ips_dict[name]=n_dict
    def new_unique_dict(self,name,n_dict):
        self.unique_dict[name]=n_dict
    def new_priv_check(self,name,func):
        self.priv_check_dict[name]=func
    def close(self):
        self.dc_priv.close()
        self.dc.close()
        self.sc.close()
    def sql_string(self,name,dict,nkeys=None,full=0):
        if not name in self.def_dict.keys():
            self.get_description(name)
        t_dict,def_dict,orig_keys=self.def_dict[name]
        if nkeys:
            orig_keys=nkeys
        rets=""
        for okey in orig_keys:
            rets+=","
            if full:
                rets+=okey+"="
            if t_dict[okey] in ["int","tinyint"]:
                rets+=str(dict[okey])
            elif t_dict[okey] in ["double"]:
                rets+=str(dict[okey])
            elif t_dict[okey] in ["char","varchar","timestamp","text","time"]:
                rets+="'"+dict[okey]+"'"
            elif t_dict[okey]=="blob":
                outstr=dict[okey]
                if outstr:
                    rets+="'%s'"%(MySQLdb.escape_string(outstr))
                else:
                    rets+="''"
            else:
                print "Unknown type for field: %s"%(t_dict[okey])
                rets+="''"
                #sys.exit(0)
        return rets[1:]
    def get_description(self,name):
        self.dc.execute("DESCRIBE "+name)
        t_dict={}
        def_dict={}
        orig_keys=[]
        for d in self.dc.fetchall():
            field_name=d["Field"]
            tfmm=re.match("^(.*)\(.*\).*$",d["Type"])
            if tfmm:
                tfm=tfmm.group(1)
            else:
                tfm=d["Type"]
            t_dict[field_name]=tfm
            orig_keys.append(field_name)
            default=d["Default"]
            if default is None:
                if tfm=="int":
                    default="0"
                elif tfm=="double":
                    default="0."
                elif tfm=="float":
                    default="0."
                elif tfm=="varchar":
                    default=""
                elif tfm=="text":
                    default=""
                elif tfm=="time":
                    default=""
                elif tfm=="char":
                    default=""
                elif tfm=="timestamp":
                    default=""
                elif tfm=="datetime":
                    default=""
                elif tfm=="blob":
                    default=""
                else:
                    print "????",d
            def_dict[field_name]=default
            if field_name==name+"_idx":
                def_dict[field_name]=0
            self.def_dict[name]=(t_dict,def_dict,orig_keys)
    def alter(self,name,o_dict,tags):
        print "Altering with tags "+tags
        n_dict={}
        for ak in o_dict.keys():
            n_dict[ak]=o_dict[ak]
        ec=0
        for sp in tags.split(" "):
            ok=1
            sps=re.match("^([^:]+):(.*)$",sp)
            if sps:
                field=sps.group(1)
                value=sps.group(2)
                n_dict[field]=value
            else:
                print "Missing delimeter ':' in %s"%(sp)
        ok,r_dict=self.check(name,n_dict,alter=1)
        return ok,r_dict
    def check(self,name,parlist,alter=0):
        if not name in self.def_dict.keys():
            self.get_description(name)
        t_dict,def_dict,orig_keys=self.def_dict[name]
        idxf=name+"_idx"
        ok=1
        resd={}
        needs=[]
        if self.need_dict.has_key(name):
            needs.extend(self.need_dict[name])
        set=[]
        for f in orig_keys:
            resd[f]=def_dict[f]
        if type(parlist) != types.DictionaryType:
            ndict={}
            # generate dictionary (if necessary)
            for sp in parlist.split(" "):
                sps=re.match("^([^:]+):(.*)$",sp)
                if sps:
                    field=sps.group(1)
                    value=sps.group(2)
                    ndict[field]=value
                else:
                    print "Missing delimeter ':' in "+sp
                    ok=0
        else:
            ndict=parlist
        if ok:
            for field in ndict.keys():
                #print field,"*",t_dict[field],type(ndict[field]),ndict[field]
                value=ndict[field]
                if type(ndict[field]) == types.StringType and ndict[field] != "blob":
                    if re.match("^\*([\w]+)\.\[(.*)\]$",value):
                        refm=re.match("^\*([\w]+)\.\[(.*)\]$",value)
                        tables=[]
                        t_idx=0
                        tables.append(refm.group(1))
                        sql_str="SELECT %s_idx FROM "%(tables[t_idx])
                        sel_tab=[]
                        d_refs=refm.group(2).strip().split(",")
                        #print "Double ref",d_refs
                        for d_ref in d_refs:
                            refm1=re.match("^(.*)=(.*)$",d_ref)
                            if refm1:
                                value1=refm1.group(2)
                                refm2=re.match("^(\w+):\*(\w+)\.(\w+)$",refm1.group(1))
                                if refm2:
                                    t_idx+=1
                                    tables.append(refm2.group(2))
                                    sel_tab.append("t0.%s=t%d.%s_idx AND t%d.%s='%s'"%(refm2.group(1),t_idx,tables[t_idx],t_idx,refm2.group(3),value1))
                                    pass
                                else:
                                    sel_tab.append("t0.%s='%s'"%(refm1.group(1),value1))
                            else:
                                print "Can't parse : ",d_ref
                        table_a=[]
                        for i in range(t_idx+1):
                            table_a.append(tables[i]+" t%d"%(i))
                        sql_str+=", ".join(table_a)+" WHERE "+" AND ".join(sel_tab)
                        self.dc_priv.execute(sql_str)
                        refl=self.dc_priv.fetchall()
                        if len(refl)==1:
                            value=refl[0].values()[0]
                        else:
                            if len(refl):
                                print "To many matching references found %s:%s"%(field,value)
                            else:
                                print "No matching reference found %s:%s"%(field,value)
                    elif re.match("^\*([\w]+)\.([\w]+)=(.*)$",value):
                        refm=re.match("^\*([\w]+)\.([\w]+)=(.*)$",value)
                        table=refm.group(1)
                        tfield=refm.group(2)
                        equal=refm.group(3)
                        if equal.startswith("_"):
                            equal=equal[1:].replace("_"," ")
                        #print equal
                        self.dc_priv.execute("SELECT "+table+"_idx FROM "+table+" WHERE "+tfield+"='"+equal+"'")
                        refl=self.dc_priv.fetchall()
                        if len(refl)==1:
                            value=refl[0].values()[0]
                        else:
                            if len(refl):
                                print "To many matching references found %s:%s"%(field,value)
                            else:
                                print "No matching reference found %s:%s"%(field,value)
                    else:
                        if len(value):
                            if value[0]=="_":
                                value=string.replace(value[1:len(value)],"_"," ")
                if field in orig_keys:
                        resd[field]=value
                        set.append(field)
                        # remove from needed fields if necessary
                        if field in needs:
                            needs.remove(field)
                        # check for uniqueness
                        if self.unique_dict.has_key(name):
                            if field in self.unique_dict[name]:
                                if alter:
                                    self.dc_priv.execute("SELECT "+field+" FROM "+name+" WHERE "+field+"='"+value+"' AND NOT "+idxf+"="+str(ndict[idxf]))
                                else:
                                    self.dc_priv.execute("SELECT "+field+" FROM "+name+" WHERE "+field+"='"+value+"'")
                                if len(self.dc_priv.fetchall()):
                                    print "Unique value %s already used for field %s"%(value,field)
                                    ok=0
                        # check type
                        if t_dict[field]=="int" or t_dict[field]=="tinyint":
                            try:
                                ivalue=int(value)
                            except:
                                print "Value %s for field %s is not an integer"%(value,field)
                                ok=0
                        # check validity of IP-Adresses
                        if self.ips_dict.has_key(name):
                            if field in self.ips_dict[name]:
                                if not is_ip(value):
                                    print "Error for ip-field %s, value %s"%(field,value)
                                    ok=0
                else:
                    print "Unknown field "+field
                    ok=0
            if len(needs):
                print "Some needed fields are missing: %s"%(", ".join(needs))
                ok=0
            if not alter:
                self.dc_priv.execute("SELECT "+idxf+" FROM "+name)
                fu=[x.values()[0] for x in self.dc_priv.fetchall()]
                if not idxf in set:
                    if len(fu):
                        resd[idxf]=max(fu)+1
                    else:
                        resd[idxf]=1
                else:
                    if resd[idxf] in fu:
                        print "Wrong index number %d"%(int(resd[idxf]))
                        ok=0
            datestr=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.time()))
            if not "date" in set:
                resd["date"]=datestr
            if self.priv_check_dict.has_key(name):
                if ok:
                    ok=self.priv_check_dict[name](resd)
        return ok,resd
    def show(self,name,entry=None,native=1,what_to_show=[]):
        if not name in self.def_dict.keys():
            self.get_description(name)
        if self.ref_dict.has_key(name):
            r_dict=self.ref_dict[name]
        else:
            r_dict={}
        t_dict,def_dict,orig_keys=self.def_dict[name]
        if entry==None:
            entry=def_dict
        idx_name=name+"_idx"
        if native:
            outstr="--(%4d )--"%(entry[idx_name])+("--- %s"%(name+" "+"-"*40))[0:40]
        else:
            outstr="------------"+("--- %s"%(name+" "+"-"*40))[0:40]
        if entry.has_key("date"):
            outstr+=" "+str(entry["date"])+" -----"
        print outstr
        for attr in orig_keys:
            if len(what_to_show)==0 or attr in what_to_show:
                if not attr in [idx_name,"date"]:
                    stype=0
                    if t_dict[attr]=="int":
                        actt="I"
                    elif t_dict[attr]=="tinyint":
                        actt="t"
                    elif t_dict[attr]=="double":
                        actt="d"
                    elif t_dict[attr]=="char":
                        actt="c"
                    elif t_dict[attr]=="varchar":
                        actt="C"
                    elif t_dict[attr]=="text":
                        actt="C"
                    elif t_dict[attr] in ["time","datetime"]:
                        actt="D"
                    elif t_dict[attr]=="bool":
                        actt="b"
                    elif t_dict[attr]=="timestamp":
                        actt="T"
                    elif t_dict[attr]=="float":
                        actt="f"
                    elif t_dict[attr]=="blob":
                        actt="b"
                        stype=1
                    else:
                        actt="?"
                    rstr_array=[]
                    if r_dict.has_key(attr):
                        idx=entry[attr]
                        t_list,e_list=r_dict[attr]
                        for l_entry in e_list:
                            if type(l_entry) == types.StringType:
                                if idx:
                                    sel_str="SELECT "+l_entry+" FROM "+t_list+" WHERE "+t_list+"_idx="+str(idx)
                                    self.dc_priv.execute(sel_str)
                                    fetch_line=self.dc_priv.fetchone()
                                    if fetch_line:
                                        rstr_array.append(str(fetch_line.values()[0]))
                                    else:
                                        rstr_array.append("[BROKEN]")
                            elif type(l_entry) == types.DictionaryType:
                                for n_attr in l_entry.keys():
                                    nt_list,ne_list=l_entry[n_attr]
                                    for nl_entry in ne_list:
                                        sel_str="SELECT a."+nl_entry+" FROM "+nt_list+" a, "+t_list+" b WHERE b."+t_list+"_idx="+str(idx)+" AND a."+n_attr+"_idx=b."+n_attr
                                        self.dc_priv.execute(sel_str)
                                        fetch_line=self.dc_priv.fetchone()
                                        if fetch_line:
                                            rstr_array.append(str(fetch_line.values()[0]))
                                        else:
                                            rstr_array.append("[BROKEN]")
                    outstr=entry[attr]
                    if stype:
                        if outstr:
                            outstr="len: %d bytes"%(len(outstr))
                        else:
                            outstr="len: 0 bytes"
                    if len(rstr_array):
                        print "%30s %s %s ( %s )"%(attr,actt,outstr,", ".join(rstr_array))
                    else:
                        print "%30s %s %s"%(attr,actt,outstr)

def getinput(prompt=":"):
    fd=sys.stdin.fileno()
    while 1:
        ret=""
        try:
            ret=raw_input(prompt)
        except KeyboardInterrupt:
            print "Ctrl-C -> use 'quit;'"
        except EOFError:
            print "Ctrl-D -> use 'quit;'"
        else:
            pass
        break
    return ret

def help_command(rest):
    for com in cmcl.comlist:
        print com.name
    return

def quit_command(rest):
    cmcl.quit_flag=1

def new_command(rst):
    ret=0
    if len(rst):
        ln=rst[0]
        idx_fn=ln+"_idx"
        try:
            dbcon.dc.execute("SELECT "+idx_fn+" FROM "+ln)
        except MySQLdb.ProgrammingError:
            print "List "+ln+" is not defined"
        else:
            ok,dict=dbcon.check(ln," ".join(rst[1:]))
            #print ok,dict
            if ok:
                sql_str=dbcon.sql_string(ln,dict)
                #print dict
                #print sql_str
                sql_str="INSERT INTO "+ln+" VALUES ("+sql_str+")"
                dbcon.dc.execute(sql_str)
                try:
                    ret=int(dbcon.dc.insert_id())
                except:
                    ret=int(dbcon.dc.lastrowid)
            else:
                print "Can't add new entry to "+ln
    return ret

def del_command(rst):
    if len(rst):
        if not len(rst[0]):
            rst=[]
    if len(rst) > 1:
        ln=rst.pop(0)
        idx_fn=ln+"_idx"
        try:
            dbcon.dc.execute("SELECT "+idx_fn+" FROM "+ln)
        except MySQLdb.ProgrammingError:
            print "List "+ln+" is not defined"
        else:
            if len(rst) == 1  and rst[0]=="-1":
                sql_str="DELETE FROM "+ln
                suc=dbcon.dc.execute(sql_str)
                if suc == 0:
                    print "Successfully deleted all entries from "+ln
                else:
                    print "Some error occured while trying to delete all entries from "+ln
            else:
                idx_array=[x.values()[0] for x in dbcon.dc.fetchall()]
                if len(idx_array):
                    cr,what_to_show=get_range(rst,min(idx_array),max(idx_array))
                    sql_str="DELETE FROM "+ln+" WHERE (%s="%(idx_fn)+(" OR %s="%(idx_fn)).join([str(x) for x in cr])+")"
                    #print "Trying to delete entry %d"%(num)
                    suc=dbcon.dc.execute(sql_str)
                    if suc:
                        print "Successfully deleted entry"
                    else:
                        print "Some error occured while trying to delete entries"
    return 1

def echo_command(rst):
    print " ".join(rst)
    return

def varlist_command(rst):
    for vn in cmcl.varlist.keys():
        print "var '%s' : %s"%(vn,cmcl.varlist[vn])
    return

def alter_command(rst):
    verbose=0
    if len(rst):
        if not len(rst[0]):
            rst=[]
    if len(rst) > 2:
        ln=rst.pop(0)
        idx=int(rst.pop(0))
        idx_fn=ln+"_idx"
        try:
            dbcon.dc.execute("SELECT "+idx_fn+" FROM "+ln)
        except MySQLdb.ProgrammingError:
            print "List "+ln+" is not defined"
        else:
            dbcon.dc.execute("SELECT * FROM "+ln+" WHERE "+idx_fn+"="+str(idx))
            act_dict=dbcon.dc.fetchone()
            tags=" ".join(rst)
            if verbose:
                print "Before altering:"
                dbcon.show(ln,act_dict)
            ok,new_dict=dbcon.alter(ln,act_dict,tags)
            if ok:
                diff_dict={}
                nkeys=[]
                for ak in act_dict.keys():
                    if act_dict[ak] != new_dict[ak]:
                        diff_dict[ak]=new_dict[ak]
                        #print ak,act_dict[ak],new_dict[ak]
                        nkeys.append(ak)
                if len(nkeys):
                    sql_str=dbcon.sql_string(ln,diff_dict,nkeys,full=1)
                    sql_str="UPDATE "+ln+" SET "+sql_str+" WHERE "+idx_fn+"="+str(act_dict[idx_fn])
                    #print sql_str
                    suc=dbcon.dc.execute(sql_str)
                    if suc:
                        print "Successfully altered"
                        if verbose:
                            print "After altering:"
                            dbcon.show(ln,new_dict)
                    else:
                        print "Something went wrong"
                else:
                    print "Nothing to alter"
            else:
                print "Unable to alter entry"
    else:
        print "Wrong list or too less arguments [ LIST NUM TAGS... ]"
    return

def get_range(rst,lbound,ubound):
    rest_a=[]
    i_range=[]
    rt1=re.compile("^(\d+)$")
    rt2=re.compile("^(\d+)-(\d+)$")
    for rs in rst:
        ar=None
        lb=None
        ub=None
        rsc=rs
        if rsc.startswith("-"):
            lb=lbound;
            rsc=rsc[1:]
        if rsc.endswith("-"):
            ub=ubound
            rsc=rsc[:-1]
        if lb and ub:
            rest_a.append(rs)
            #print "Can't parse '%s', skipping..."%(rsc)
        elif not (lb or ub):
            m1=rt1.match(rsc)
            m2=rt2.match(rsc)
            if m1:
                ar=[int(m1.group(1))]
            elif m2:
                lb=int(m2.group(1))
                ub=int(m2.group(2))
                lb2=min(lb,ub)
                ub2=max(lb,ub)
                ar=range(lb2,ub2+1)
            else:
                rest_a.append(rs)
                #print "Can't parse '%s', skipping..."%(rsc)
        else:
            m1=rt1.match(rsc)
            if m1:
                if lb:
                    ub=int(m1.group(1))
                else:
                    lb=int(m1.group(1))
                lb2=min(lb,ub)
                ub2=max(lb,ub)
                ar=range(lb2,ub2+1)
            else:
                rest_a.append(rs)
                #print "Can't parse: '%s', skipping..."%(rsc)
        if ar is not None:
            #print ":",rsc,"->",ar
            i_range+=[x for x in ar if x not in i_range]
        i_range.sort()
    if not len(i_range):
        i_range=range(lbound,ubound+1)
    #print i_range
    return i_range,rest_a
    
def list_command(rst):
    if len(rst):
        if not len(rst[0]):
            rst=[]
    if len(rst):
        ln=rst.pop(0)
        idx_fn=ln+"_idx"
        try:
            dbcon.dc.execute("SELECT "+idx_fn+" FROM "+ln)
        except MySQLdb.ProgrammingError:
            print "List "+ln+" is not defined"
        except MySQLdb.OperationalError:
            print "List "+ln+" ist not a native list"
            dbcon.dc.execute("SELECT * FROM "+ln)
            for dset in dbcon.dc.fetchall():
                dbcon.show(ln,dset,native=0)
        else:
            idx_array=[x.values()[0] for x in dbcon.dc.fetchall()]
            if len(idx_array):
                cr,what_to_show=get_range(rst,min(idx_array),max(idx_array))
                # get (or refresh, at least...) description
                dbcon.get_description(ln)
                sql_str="SELECT * FROM "+ln+" WHERE (%s="%(idx_fn)+(" OR %s="%(idx_fn)).join([str(x) for x in cr])+") ORDER by "+idx_fn
                dbcon.dc.execute(sql_str)
                if 0 in cr:
                    dbcon.show(ln)
                for dset in dbcon.dc.fetchall():
                    dbcon.show(ln,dset,what_to_show=what_to_show)
    else:
        print "Defined lists in ClusterDataBase:"
        dbcon.dc.execute("SHOW TABLES")
        for ln in [x.values()[0] for x in dbcon.dc.fetchall()]:
            dbcon.dc.execute("DESCRIBE "+ln)
            idx_name=ln+"_idx"
            if idx_name in [x["Field"] for x in dbcon.dc.fetchall()]:
                dbcon.dc.execute("SELECT %s_idx FROM %s"%(ln,ln))
                idxf=[x.values()[0] for x in dbcon.dc.fetchall()]
                if len(idxf):
                    print "  %30s (%5d entries, %5d is lowest and %5d highest index)"%(ln,len(idxf),min(idxf),max(idxf))
                else:
                    print "  %30s (%5s entries)"%(ln,"no")
            else:
                dbcon.dc.execute("SELECT * FROM "+ln)
                num=len(dbcon.dc.fetchall())
                print "  %30s (%5d entries, foreign table [maybe from NAGIOS?])"%(ln,num)
    return

def main():
    global dbcon,cmcl
    try:
        opts,args=getopt.getopt(sys.argv[1:],"f:h",["--help"])
    except:
        print "Commandline error !"
        sys.exit(2)
    infile=None
    for opt,arg in opts:
        if opt in ("-h","--help"):
            print "usage: %s [OPTIONS] "%(os.path.basename(sys.argv[0]))
            print "where OPTIONS is one or more of"
            print " -h,--help        this help"
            print " -f file          read as input"
            sys.exit(0)
        if opt=="-f":
            infile=arg
    cf1n="/etc/sysconfig/cluster/mysql.cf"
    csuc,cfile=configfile.readconfig(cf1n,1)
    if not csuc:
        print "Unable to read configfile %s"%(cf1n)
        csuc,cfile=configfile.readconfig(cf2n,1)
        if not csuc:
            print "Unable to read configfile %s"%(cf2n)
    if not csuc:
        print "No config found, exiting..."
        sys.exit(0)
    print "Welcome to the cluster managment console Version 0.2.0 (dynamic)"
    dbcon=db_con(cfile)
    cmcl=mlc()
    cmcl.add_command(command("help",help_command,0))
    cmcl.add_command(command("quit",quit_command,0))
    cmcl.add_command(command("list",list_command,0))
    cmcl.add_command(command("new",new_command,1))
    cmcl.add_command(command("alter",alter_command,0))
    cmcl.add_command(command("del",del_command,0))
    cmcl.add_command(command("echo",echo_command,0))
    cmcl.add_command(command("varlist",varlist_command,0))
    prelines=[]
    if infile:
        if os.path.isfile(infile):
            try:
                file=open(infile,"r")
                while 1:
                    line=file.readline()
                    if not line:
                        break
                    else:
                        if len(line.strip()):
                            prelines.append(line.strip())
                file.close()
                print "Read %d non-empty lines from infile %s."%(len(prelines),infile)
            except:
                print "Something went wrong reading infile %s, deleting all read lines..."%(infile)
                prelines=[]
        else:
            print "Infile %s not found !"%(infile)
    home=posix.environ["HOME"]
    hfile=home+"/.cmc_history"
    if os.path.exists(hfile) and readline:
        readline.read_history_file(hfile)
    cmcl.mainloop(prelines)
    if readline:
        readline.write_history_file(hfile)
    dbcon.close()

if __name__=="__main__":
    main()

