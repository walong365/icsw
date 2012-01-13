#!/usr/bin/python -Ot

import os
import os.path
import sys
import commands
import re

verbose=0

def which(file,sp):
    for p in sp:
        full="%s/%s"%(p,file)
        if os.path.isfile(full):
            break
    else:
        full=None
    if full:
        act=full
        full=[full]
        # follow symlinks
        while os.path.islink(act):
            next=os.readlink(act)
            if not next.startswith("/"):
                next=os.path.normpath("%s/%s"%(os.path.dirname(act),next))
            if verbose:
                print "following link from %s to %s"%(act,next)
            act=next
            full+=[act]
    return full

def get_lib_list(in_f):
    stat,out=commands.getstatusoutput("ldd %s"%(" ".join(in_f)))
    lib_l=[]
    out_l=[x.strip() for x in out.split("\n")]
    found_list=[]
    for x in out_l:
        if x.endswith(":") and x[:-1] in in_f:
            act_bin=x[:-1]
            found_list+=[act_bin]
        else:
            if re.search("not a dynamic",x):
                pass
            else:
                lib=x.split()[2]
                if not lib.startswith("(") and not lib in lib_l:
                    lib_l+=[lib]
    #print found_list
    #print in_f
    # eliminate symlinks from lib-list
    lib_l2=[]
    for lib in lib_l:
        while os.path.islink(lib):
            next=os.readlink(lib)
            if not next.startswith("/"):
                next=os.path.normpath("%s/%s"%(os.path.dirname(lib),next))
            if verbose:
                print "following link from %s to %s"%(lib,next)
            lib=next
        lib_l2+=[lib]
    lib_l2.sort()
    return lib_l2

def main():
    mode=sys.argv[1]
    i_list=sys.argv[2:]
    res_list=[]
    if mode=="-s":
        # resolve symlinks
        path=os.environ["PATH"].split(":")
        for f in i_list:
            full_path=which(f,path)
            if not full_path:
                sys.stderr.write("Not found: %s\n"%(f))
            else:
                for full in full_path:
                    if full not in res_list:
                        res_list+=[full]
        res_list.sort()
    elif mode=="-d":
        # get directories
        for f in i_list:
            act_dir=os.path.dirname(f)
            if not act_dir in res_list:
                res_list+=[act_dir]
        res_list.sort()
    elif mode=="-l":
        # get libraries
        res_list=get_lib_list(i_list)
    elif mode=="-p":
        pam_dir=i_list.pop(0)
        # handle pam-stuff
        for p in i_list:
            f_path="/etc/pam.d/%s"%(p)
            if os.path.isfile(f_path):
                libs=[z[2] for z in [y.split() for y in [x.strip() for x in open(f_path,"r").read().split("\n")] if not y.startswith("#") and y] if len(z) > 2]
                
                for lib in libs:
                    if lib not in res_list:
                        res_list+=[lib]
        res_list=get_lib_list(["/%s/%s"%(pam_dir,x) for x in res_list])
    print " ".join(res_list)

if __name__=="__main__":
    main()
    
