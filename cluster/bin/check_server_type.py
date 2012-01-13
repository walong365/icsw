#!/usr/bin/python -Ot

import process_tools
import mysql_tools
import getopt
import sys
import os,os.path

def main():
    try:
        opts,args=getopt.getopt(sys.argv[1:],"hli",["help"])
    except getopt.GetoptError,bla:
        print "Commandline error (%s) !"%(str(bla))
        sys.exit(-2)
    pname=os.path.basename(sys.argv[0])
    list_servers,show_idx=(0,0)
    for opt,arg in opts:
        if opt in ["-h","--help"]:
            print "Usage: %s [options] SERVER_TYPE"%(pname)
            print "where options is one or more of"
            print "  -l    list defined server-properties"
            print "  -i    show server idx (or zero)"
            print "Defined return-codes:"
            print "  -2    commandline or SQL error"
            print "  -1    datasbase error (too many servers)"
            print "   0    no server / normal return-code"
            print "   1    real server"
            print "   2    virtual server"
            sys.exit(0)
        if opt=="-l":
            list_servers=1
        if opt=="-i":
            show_idx=1
    if len(args) != 1:
        print "Need server-type argument !" 
        sys.exit(-2)
    server_type=args[0]
    try:
        db_con=mysql_tools.db_con()
    except MySQLdb.OperationError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(-2)
    if list_servers:
        db_con.dc.execute("SELECT c.name FROM config c, config_type ct WHERE ct.config_type_idx=c.config_type AND ct.identifier='S'")
        all_sp=[x["name"] for x in db_con.dc.fetchall()]
        all_sp.sort()
        print "%d server properties found: "%(len(all_sp))
        print "\n".join([" - %s"%(x) for x in all_sp])
        ret_code=0
    else:
        num_servers,server_idx,s_type,s_str=process_tools.is_server(db_con.dc,server_type,1)
        if num_servers==0:
            ret_code=0
            out_str="no '%s'-server"%(server_type)
        elif num_servers > 1:
            ret_code=-1
            out_str="too many '%s'-servers found (database error ?)"
        else:
            if s_type=="real":
                ret_code=1
            else:
                ret_code=2
            out_str=s_str
        if show_idx:
            if ret_code > 0:
                out_str="%d"%(server_idx)
            else:
                out_str="0"
        print out_str
    del db_con
    sys.exit(ret_code)
    
if __name__=="__main__":
    main()
    
