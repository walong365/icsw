#!/usr/bin/python -Ot

import sys
import string
import telnetlib
import time
import re
import os
import msock
import threading
import Queue

class message:
    type=""
    thread=""
    c_pid=None
    s_time=None
    arg=None
    def __init__(self,type="?",c_pid=None,s_time=None,arg=()):
        self.type=type
        self.thread=threading.currentThread().getName()
        self.c_pid=c_pid
        if s_time:
            self.s_time=s_time
        else:
            self.s_time=time.time()
        self.arg=arg

class internal_message(message):
    def __init__(self,arg=""):
        message.__init__(self,"I",arg=(arg))

class send_message(message):
    def __init__(self,arg=""):
        message.__init__(self,"ST",arg=(arg))

class apc:
    ip=0
    tn=0
    idx=0
    short_name=""
    full_name=""
    login=""
    password=""
    outlets={}
    def __init__(self,s_name,f_name,sc,ip,idx=0,login="apc",passw="apc"):
        self.ip=ip
        self.sc=sc
        self.short_name=s_name
        self.full_name=f_name
        # index in database
        self.idx=idx
        self.tn=None
        self.login=login
        self.password=passw
        # outlet 0 is the masterswitch itself
        self.outlets=None
    def write_to_database(self,dc):
        if self.idx:
            if self.outlets:
                if self.outlets.has_key(0):
                    act_out=self.outlets[0]
                    dc.execute("UPDATE device SET power_on_delay="+str(act_out["power_on_delay"])+", reboot_delay="+str(act_out["reboot_delay"])+" WHERE device_idx="+str(self.idx))
                dc.execute("SELECT m.msoutlet_idx,m.outlet FROM msoutlet m WHERE m.device=%d"%(self.idx))
                act_outs={}
                for od in dc.fetchall():
                    act_outs[int(od["outlet"])]=int(od["msoutlet_idx"])
                for outs in range(1,9):
                    if self.outlets.has_key(outs):
                        act_out=self.outlets[outs]
                        if outs in act_outs.keys():
                            dc.execute("UPDATE msoutlet SET state='"+act_out["state"]+"',power_on_delay="+str(act_out["power_on_delay"])+",power_off_delay="+str(act_out["power_off_delay"])+",reboot_delay="+str(act_out["reboot_delay"])+" WHERE msoutlet_idx="+str(act_outs[outs]))
                        else:
                            dc.execute("INSERT INTO msoutlet VALUES("+",".join(["0",str(self.idx),str(outs),"'"+act_out["state"]+"'",str(act_out["power_on_delay"]),str(act_out["power_off_delay"]),str(act_out["reboot_delay"]),"null"])+")")

    def set_date_time(self):
        if self.tn:
            self.process_string("33")
            self.send_line("1",wfp=0)
            self.send_line(time.strftime("%m/%d/%Y"))
            self.send_line("2",wfp=0)
            self.send_line(time.strftime("%H:%M:%S"))
            self.process_string("3EE")
    def set_machine(self,outlet,machine):
        if self.outlets:
            if self.outlets.has_key(outlet):
                self.outlets[outlet]["machine"]=machine
    #print self.outlets
    def start_telnet(self,debug=0):
        try:
            self.tn=telnetlib.Telnet(self.ip)
        except:
            ok=0
            self.tn=None
        else:
            ok=1
            try:
                self.tn.set_debuglevel(debug)
                self.tn.read_until("Name : ")
                self.send_line(self.login,wfp=0)
                self.tn.read_until("Password  : ")
                self.send_line(self.password,wfp=0)
                self.wait_for_prompt()
            except:
                ok=0
        return ok
    def rescan(self):
        def time_to_int(str):
            if str=="immediate":
                return 0
            elif str.endswith("minute"):
                return int(str.split(" ")[0])*60
            elif str.endswith("minutes"):
                return int(str.split(" ")[0])*60
            elif str.endswith("second"):
                return int(str.split(" ")[0])
            elif str.endswith("seconds"):
                return int(str.split(" ")[0])
            elif str.startswith("never"):
                return -1
            else:
                return str
        if self.tn:
            self.outlets=None
            head_line=re.compile("^.*(outlet).*(name).*(pwr on).*(pwr off).*(reboot).*$")
            self.process_string("1")
            self.process_string("9")
            sr=self.send_line("2")
            self.outlets={}
            head_found=0
            line_num=0
            for line in sr:
                print line
                line_num+=1
                line=line.lower()
                #print "%3d : %s"%(line_num,line)
                if head_found:
                    if line_num > head_line+1 and line_num < head_line+10:
                        actout={}
                        outnum=int(line[outlet_idx].strip())
                        actout["state"]=line[outlet_idx+3:outlet_idx+7].strip()
                        actout["name"]=line[name_idx:pwron_idx-1].strip()
                        actout["power_on_delay"]=time_to_int(line[pwron_idx:pwroff_idx-1].strip())
                        actout["power_off_delay"]=time_to_int(line[pwroff_idx:reboot_idx-1].strip())
                        actout["reboot_delay"]=time_to_int(line[reboot_idx:].strip())
                        self.outlets[outnum]=actout
                    elif line_num == head_line+10:
                        actout={}
                        actout["name"]=line[name_idx:pwron_idx-1].strip()
                        actout["power_on_delay"]=time_to_int(line[pwron_idx:pwroff_idx-1].strip())
                        actout["reboot_delay"]=time_to_int(line[reboot_idx:].strip())
                        self.outlets[0]=actout
                else:
                    lm=head_line.match(line)
                    if lm:
                        head_found=1
                        head_line=line_num
                        outlet_idx=line.index(lm.group(1))
                        name_idx=line.index(lm.group(2))
                        pwron_idx=line.index(lm.group(3))
                        pwroff_idx=line.index(lm.group(4))
                        reboot_idx=line.index(lm.group(5))
            self.process_string("EE")
    def wait_for_prompt(self,wp=1):
        if self.tn:
            idx,mobj,resp=self.tn.expect(['\015\012> ',' cancel : '])
            #if wp==1:
            #  resp=self.tn.read_until('\015\012> ')
            #elif wp==2:
            #  resp=self.tn.read_until(' cancel : ')
            #print "****",idx
            return resp.split("\n")
        else:
            return None
    def close_telnet(self):
        if self.tn:
            self.process_string("X")
            self.tn.close()
        self.tn=None
    def send_escape(self,wfp=1):
        if self.tn:
            self.tn.write('\033\012')
            if wfp:
                try:
                    self.wait_for_prompt()
                except:
                    print "Error:",self.ip
    def send_line(self,what,wfp=1):
        ret=None
        if self.tn:
            self.tn.write(what+'\011\012')
            if wfp:
                ret=self.wait_for_prompt(wfp)
        if ret:
            #print "\n".join(ret)
            pass
        return ret
    def process_string(self,str):
        if self.tn:
            for s in str:
                #print self.ip,s,os.getpid()
                if s=="Y":
                    self.send_line("YES")
                elif s=="E":
                    self.send_escape()
                elif s=="C":
                    self.send_line('\003')
                elif s=="X":
                    self.send_line("4",wfp=0)
                else:
                    self.send_line(s)


def send_thread(main_queue,own_queue):
    def log_hook(arg):
        print "LH:",arg
    def error_hook(arg):
        print "EH:",arg
    def got_hook(arg):
        print "GH:",arg
    sc=msock.telnet_relayer(log_hook,error_hook,got_hook)
    while 1:
        it=own_queue.get()
        if it.type=="I":
            if it.arg=="exit":
                break
        else:
            if it.type=="ST":
                host,arg=it.arg
                print it.type,host,arg
                send_str=arg
                sc.new_connection(host,23,add_data=())
    sc.close()
    
if __name__=="__main__":
    scq=Queue.Queue(100)
    exq=Queue.Queue(100)
    #tap=apc("???","???",scq,"127.0.0.1")
    threading.Thread(name="send",target=send_thread,args=[exq,scq]).start()
    scq.put(send_message(("127.0.0.1","bla"+"\012")))
    #if tap.start_telnet():
        #tap.set_date_time()
        #tap.rescan()
        #tap.tn.interact()
        #tap.process_string("121CX")
        #tap.process_string("1213YEEEX")
        #tap.send_line("1")
        #tap.send_line("2")
        #tap.send_line("1")
        #tap.send_line("3")
        #tap.send_line("YES")
        #tap.send_escape()
        #tap.send_escape()
        #tap.send_escape()
        #tap.send_line("4",wfp=0)
   #     tap.close_telnet()
   #     for out in tap.outlets.keys():
    #        print out,tap.outlets[out]
    #print "OK"
else:
    print "Error"

