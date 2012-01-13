#!/usr/bin/python -Ot

import MySQLdb
import MySQLdb.cursors
import string
import sys
import os
import getopt
import configfile
import time
import types

def string_pl(what):
    if len(what)==1:
        return ""
    else:
        return "s"
    
def convert_db():
    # machinelog transfer
    # transfers the classical machine/udi layout to the new device layout
    # copy all machines to device
    mync.execute("SELECT m.machine_idx,d.device_idx FROM machine m, device d WHERE m.name=d.name")
    for entry in mync.fetchall():
        #mync.execute("UPDATE machineconfig SET device=%d WHERE machine=%d"%(entry["device_idx"],entry["machine_idx"]))
        mync.execute("UPDATE bootlog SET device=%d WHERE machine=%d"%(entry["device_idx"],entry["machine_idx"]))
        mync.execute("UPDATE macbootlog SET device=%d WHERE machine=%d"%(entry["device_idx"],entry["machine_idx"]))
    return
    mync.execute("DELETE FROM device_type")
    for id,stri in [("H","Computer"),("AM","APC Masterswitch"),("NB","Netbotz device"),("S","Manageable switch")]:
        mync.execute("INSERT INTO device_type VALUES(0,'%s','%s',null)"%(id,stri))
    mync.execute("DELETE FROM device_group")
    mync.execute("SELECT * from machinegroup")
    for entry in mync.fetchall():
        mync.execute("INSERT INTO device_group VALUES(%d,'%s','%s',null)"%(entry["machinegroup_idx"],entry["name"],entry["descr"]))
    mync.execute("DELETE FROM device")
    # machines
    mync.execute("SELECT * from machine m")
    new_key_dict={"machinegroup":"device_group","ns_host":"ns_device","host_location":"device_location","host_class":"device_class"}
    drop_list=["machine_idx"]
    add_dict={"device_type":1}
    for entry in mync.fetchall():
        set_array=[]
        for key in entry.keys():
            if key not in drop_list:
                if type(entry[key])==types.StringType:
                    new_e="'%s'"%(MySQLdb.escape_string(entry[key]))
                else:
                    new_e=str(entry[key])
                if key in new_key_dict.keys():
                    key=new_key_dict[key]
                set_array.append("%s=%s"%(key,new_e))
        for key in add_dict.keys():
            new_e=str(add_dict[key])
            set_array.append("%s=%s"%(key,new_e))
                #print key,new_e
        c_str=",".join(set_array)
        #print "-------------"
        #print c_str
        mync.execute("INSERT INTO device SET %s"%(c_str))
    # masterswitches
    mync.execute("SELECT * from mswitch m")
    new_key_dict={"machinegroup":"device_group","ns_host":"ns_device","host_location":"device_location","host_class":"device_class"}
    drop_list=["mswitch_idx","pswitch","poutlet"]
    add_dict={"device_type":2}
    for entry in mync.fetchall():
        set_array=[]
        for key in entry.keys():
            if key not in drop_list:
                if type(entry[key])==types.StringType:
                    new_e="'%s'"%(MySQLdb.escape_string(entry[key]))
                else:
                    new_e=str(entry[key])
                if key in new_key_dict.keys():
                    key=new_key_dict[key]
                set_array.append("%s=%s"%(key,new_e))
        for key in add_dict.keys():
            new_e=str(add_dict[key])
            set_array.append("%s=%s"%(key,new_e))
                #print key,new_e
        c_str=",".join(set_array)
        mync.execute("INSERT INTO device SET %s"%(c_str))
    # netbotzes
    mync.execute("SELECT * from netbotz m")
    new_key_dict={"machinegroup":"device_group","ns_host":"ns_device","host_location":"device_location","host_class":"device_class"}
    drop_list=["netbotz_idx"]
    add_dict={"device_type":3}
    for entry in mync.fetchall():
        set_array=[]
        for key in entry.keys():
            if key not in drop_list:
                if type(entry[key])==types.StringType:
                    new_e="'%s'"%(MySQLdb.escape_string(entry[key]))
                else:
                    new_e=str(entry[key])
                if key in new_key_dict.keys():
                    key=new_key_dict[key]
                set_array.append("%s=%s"%(key,new_e))
        for key in add_dict.keys():
            new_e=str(add_dict[key])
            set_array.append("%s=%s"%(key,new_e))
                #print key,new_e
        c_str=",".join(set_array)
        mync.execute("INSERT INTO device SET %s"%(c_str))
    # switches
    mync.execute("SELECT * from switch m")
    new_key_dict={"machinegroup":"device_group","ns_host":"ns_device","host_location":"device_location","host_class":"device_class","descr":"comment"}
    drop_list=["switch_idx","pswitch","poutlet"]
    add_dict={"device_type":4}
    for entry in mync.fetchall():
        set_array=[]
        for key in entry.keys():
            if key not in drop_list:
                if type(entry[key])==types.StringType:
                    new_e="'%s'"%(MySQLdb.escape_string(entry[key]))
                else:
                    new_e=str(entry[key])
                if key in new_key_dict.keys():
                    key=new_key_dict[key]
                set_array.append("%s=%s"%(key,new_e))
        for key in add_dict.keys():
            new_e=str(add_dict[key])
            set_array.append("%s=%s"%(key,new_e))
                #print key,new_e
        c_str=",".join(set_array)
        mync.execute("INSERT INTO device SET %s"%(c_str))
    # delete netdeviceip table
    mync.execute("SELECT n.netdevice_idx,i.netip_idx FROM netdevice n, netip i, netdeviceip ni WHERE ni.netip=i.netip_idx AND ni.netdevice=n.netdevice_idx")
    for entry in mync.fetchall():
        nd_idx=entry["netdevice_idx"]
        ni_idx=entry["netip_idx"]
        mync.execute("UPDATE netip SET netdevice=%d WHERE netip_idx=%d"%(nd_idx,ni_idx))
    # change references from netdevices (udi version)
    for mt,tn in [("H","machine"),("AM","mswitch"),("NB","netbotz"),("S","switch")]:
        mync.execute("SELECT n.netdevice_idx,d.device_idx FROM netdevice n, device d, %s a, udi u WHERE n.udi=u.udi_idx AND d.name=a.name AND u.device=a.%s_idx AND u.dev_type='%s'"%(tn,tn,mt))
        for entry in mync.fetchall():
            mync.execute("UPDATE netdevice SET device=%d WHERE netdevice_idx=%d"%(entry["device_idx"],entry["netdevice_idx"]))
    # change references to mswitches
    mync.execute("SELECT d.device_idx,ms.mswitch_idx FROM device d, mswitch ms WHERE ms.name=d.name")
    for entry in mync.fetchall():
        mync.execute("UPDATE device SET mswitch=%d WHERE mswitch=%d"%(entry["device_idx"],entry["mswitch_idx"]))
        mync.execute("UPDATE msoutlet SET device=%d WHERE mswitch=%d"%(entry["device_idx"],entry["mswitch_idx"]))
    # change network types
    mync.execute("UPDATE network SET network_type=1 WHERE is_boot=1")
    mync.execute("UPDATE network SET network_type=2 WHERE is_production=1")
    mync.execute("UPDATE network SET network_type=3 WHERE is_slave=1")
    mync.execute("UPDATE network SET network_type=4 WHERE is_boot=0 AND is_slave=0 AND is_production=0")
    # change machineconfig entries
    mync.execute("SELECT m.machine_idx,d.device_idx FROM machine m, device d WHERE m.name=d.name")
    for entry in mync.fetchall():
        mync.execute("UPDATE machineconfig SET device=%d WHERE machine=%d"%(entry["device_idx"],entry["machine_idx"]))
        mync.execute("UPDATE bootlog SET device=%d WHERE machine=%d"%(entry["device_idx"],entry["machine_idx"]))
        mync.execute("UPDATE macbootlog SET device=%d WHERE machine=%d"%(entry["device_idx"],entry["machine_idx"]))
    return
    mync.execute("SELECT m.machinelog_idx,m.machine FROM machinelog m")
    for entry in mync.fetchall():
        mync.execute("SELECT u.udi_idx FROM machine m, udi u WHERE u.dev_type='H' AND u.device=m.machine_idx AND m.machine_idx=%d"%(entry["machine"]))
        idx=mync.fetchone()["udi_idx"]
        c_str="UPDATE machinelog SET udi=%d WHERE machinelog_idx=%d"%(idx,entry["machinelog_idx"])
        mync.execute(c_str)
    return
    mync.execute("DELETE FROM udi")
    for table,mtype,addstr in [("machine","H","Host"),("mswitch","AM","APC"),("switch","S","Switch"),("netbotz","NB","Netbotz")]:
        idx_name=table+"_idx"
        selstr="SELECT d.%s FROM %s d"%(idx_name,table)
        mync.execute(selstr)
        for idx in [x[idx_name] for x in mync.fetchall()]:
            selstr="SELECT n.netdevice_idx FROM netdevice n WHERE n.machine=%d AND n.mach_type='%s'"%(idx,mtype)
            mync.execute(selstr)
            n_idx=[x["netdevice_idx"] for x in mync.fetchall()]
            print mtype,idx,n_idx
            uid_stuff="INSERT INTO udi VALUES(0,%d,'%s',null)"%(idx,mtype)
            mync.execute(uid_stuff)
            ins_id=mync.insert_id()
            for act_idx in n_idx:
                nd_stuff="UPDATE netdevice SET udi=%d WHERE netdevice_idx=%d"%(ins_id,act_idx)
                mync.execute(nd_stuff)
    return

if __name__=="__main__":
    global mync
    #print ":",compose_ip("254.254.254.254","192.168.1.0","255.255.255.0","192.168.1.255")
    csuc,cfile=configfile.readconfig("/usr/local/mysql/etc/mysql.cf",1)
    if not csuc:
        csuc,cfile=configfile.readconfig("/usr/local/cluster/etc/cluster.cf",1)
    if not csuc:
        print "Can´t find configfile !"
        sys.exit(-2)
    db=MySQLdb.connect(cfile["MYSQL_HOST"],user=cfile["MYSQL_USER"],passwd=cfile["MYSQL_PASSWD"],db=cfile["MYSQL_DATABASE"])
    mync=MySQLdb.cursors.DictCursor(db)
    convert_db()
