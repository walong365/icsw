#!/usr/bin/python -Ot

import sys
import os,os.path
import getopt
import commands
import re
import shutil
import tempfile
import shutil
import copy
import stat
import pprint

LINUXRC_NAME="linuxrc"

stage1_dir_dict={"root":1,"tmp":1,"dev":1,"etc/pam.d":1,"proc":1,"sys":0,
                 "var/empty":0,"var/run":1,"var/log":1,"dev/pts":1,"sbin":1,"usr/lib":1}
stage1_file_dict={"free":1,"ethtool":1,"sh":1,"bash":1,"echo":1,"cp":1,"mount":1,"cat":1,"ls":1,"mount":1,"mkdir":1,
                  "tar":1,"gunzip":1,"umount":1,"rmdir":1,"egrep":1,"fgrep":1,"grep":1,"rm":1,"chmod":1,"ps":1,
                  "sed":1,"dmesg":1,"ping":1,"mknod":1,"true":1,"false":1,"logger":1,"modprobe":1,"modprobe.old":1,
                  "lsmod":1,"lsmod.old":1,"rmmod":1,"rmmod.old":1,"depmod":1,"depmod.old":1,"insmod":1,"insmod.old":1,"mkfs.ext2":1,
                  "ifconfig":1,"pivot_root":1,"init":1,"route":1,"tell_mother":1,"bzip2":1,"bunzip2":1,"cut":1,"tr":1,"chroot":1,
                  "whoami":1,"killall":1,"seq":1,"inetd":0,"xinetd":0,"in.rshd":1,"tcpd":1,"in.rlogind":1,"hoststatus":1,"chown":1,
                  "wc":1,"arp":1,"tftp":1,"mkfifo":1,"ldconfig":1,"sleep":1}

stage2_dir_dict={"root":1,"tmp":1,"dev":1,"etc/pam.d":1,"proc":1,"sys":0,
                 "var/empty":0,"var/run":1,"var/log":1,"dev/pts":1,"sbin":1,"usr/lib":1}
stage2_file_dict={"ethtool":1,"sh":1,"strace":1,"bash":1,"echo":1,"cp":1,"mount":1,"cat":1,"ls":1,"mount":1,"mkdir":1,
                  "df":1,"tar":1,"gzip":1,"gunzip":1,"umount":1,"rmdir":1,"egrep":1,"fgrep":1,"grep":1,"basename":1,
                  "rm":1,"chmod":1,"ps":1,"touch":1,"sed":1,"dd":1,"sync":1,"dmesg":1,"ping":1,"mknod":1,"usleep":1,
                  "sleep":1,"login":1,"true":1,"false":1,"logger":1,"fsck":1,"modprobe":1,"modprobe.old":1,"lsmod":1,
                  "lsmod.old":1,"rmmod":1,"rmmod.old":1,"depmod":1,"depmod.old":1,"insmod":1,"insmod.old":1,"mkfs.ext2":1,
                  "mkfs.ext3":1,"mkfs.xfs":1,"fdisk":1,"cfdisk":1,"sfdisk":1,"ifconfig":1,"mkfs.reiserfs":1,"mkswap":1,
                  "reboot":1,"halt":1,"shutdown":1,"init":1,"route":1,"tell_mother":1,"lilo":1,"grub-install":1,"grub":1,
                  "syslogd":1,"bzip2":1,"bunzip2":1,"cut":1,"tr":1,"chroot":1,"whoami":1,"killall":1,"head":1,"tail":1,
                  "seq":1,"inetd":0,"in.rshd":1,"tcpd":1,"in.rlogind":1,"hoststatus":1,"ldconfig":1,"sort":1,"dirname":1,
                  "chown":1,"wc":1,"portmap":1,"klogd":1,"arp":1,"ln":1,"find":1,"tftp":1,"uname":1,"xinetd":0}

def find_module(md,dir,files):
    mod_list=["%s.o"%(x) for x in md.keys()]+["%s.ko"%(x) for x in md.keys()]
    for f in files:
        act_f="%s/%s"%(dir,f)
        if os.path.isfile(act_f):
            if f in mod_list:
                md[f.split(".")[0]]=act_f
    
def get_module_dependencies(kern_dir,mod_list):
    mod_dict={}
    for m in mod_list:
        mod_dict[m.split(".")[0]]=None
    os.path.walk(kern_dir,find_module,mod_dict)
    dep_file="%s/lib/modules/"%(kern_dir)
    dep_file="%s/%s/modules.dep"%(dep_file,os.listdir(dep_file)[0])
    #print dep_file
    req_dep=[x for x in mod_dict.values() if x]
    if os.path.isfile(dep_file):
        dep_lines=[x.replace("\t"," ").strip() for x in open(dep_file,"r").read().split("\n") if x.strip()]
        dep_lines2=[]
        #print dep_lines
        add_next_line=0
        for dep_line in dep_lines:
            if dep_line.endswith("\\"):
                anl=1
                dep_line=dep_line[:-1]
            else:
                anl=0
            if add_next_line:
                dep_lines2[-1]+=" %s"%(dep_line)
            else:
                dep_lines2+=[dep_line]
            add_next_line=anl
        #print dep_lines2
        dep_dict=dict([q for q in [(os.path.normpath("%s/%s"%(kern_dir,y))).split(":") for y in dep_lines2 if y] if len(q)==2])
        #print dep_dict
        auto_dep=copy.deepcopy(req_dep)
        auto_dep.sort()
        while 1:
            next_dep=copy.deepcopy(auto_dep)
            for dep in auto_dep:
                if dep_dict.has_key(dep):
                    #print dep,dep_dict[dep]
                    for next_d in dep_dict[dep].split():
                        act_d=os.path.normpath("%s/%s"%(kern_dir,next_d))
                        if act_d not in next_dep and act_d not in req_dep:
                            next_dep+=[act_d]
            next_dep.sort()
            if auto_dep == next_dep:
                break
            auto_dep=copy.deepcopy(next_dep)
        auto_dep=[x for x in auto_dep if x not in req_dep]
    else:
        auto_dep=[]
    return mod_dict.values()+auto_dep

def which(file,sp):
    for p in sp:
        full="%s/%s"%(p,file)
        if os.path.isfile(full):
            break
    else:
        full=None
    if full:
        act=os.path.normpath(full)
        full=[full]
        # follow symlinks
        while os.path.islink(act):
            next=os.path.normpath(os.readlink(act))
            if not next.startswith("/"):
                next=os.path.normpath("%s/%s"%(os.path.dirname(act),next))
            if verbose > 1:
                print "  following link from %s to %s"%(act,next)
            act=next
            full+=[act]
    if full:
        return [os.path.normpath(x) for x in full]
    else:
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
                if len(x.split()) > 2:
                    #print "***",x,len(x.split())
                    lib=x.split()[2]
                    if not lib.startswith("(") and not lib in lib_l:
                        lib_l+=[lib]
    for lib in lib_l:
        new_lib=None
        if lib.startswith("/lib/tls"):
            new_lib="/lib/%s"%(lib.split("/")[-1])
        elif lib.startswith("/lib64/tls"):
            new_lib="/lib64/%s"%(lib.split("/")[-1])
        if new_lib:
            if new_lib not in lib_l:
                lib_l+=[new_lib]
    # eliminate symlinks from lib-list
    lib_l2=[]
    for lib in lib_l:
        while os.path.islink(lib):
            next=os.readlink(lib)
            if not next.startswith("/"):
                next=os.path.normpath("%s/%s"%(os.path.dirname(lib),next))
            if verbose > 1:
                print "  following link from %s to %s"%(lib,next)
            lib=next
        lib_l2+=[lib]
    lib_l2.sort()
    return lib_l2

def populate_it(temp_dir,dir_dict,file_dict,ignore_errors):
    pam_dict={"rlogin":0,
              "su":0,
              "rsh":0,
              "rexec":0,
              "login":0,
              "other":0}
    root_64bit=get_system_bitcount("/")
    pam_dir="/lib%s/security"%({0:"",1:"64"}[root_64bit])
    main_lib_dir="/lib%s"%({0:"",1:"64"}[root_64bit])
    dir_dict[pam_dir]=1
    dir_dict["/etc/xinetd.d"]=0
    sev_dict={"W":0,"E":0}
    if ignore_errors:
        err_sev="W"
    else:
        err_sev="E"
    if verbose:
        print "checking availability of %d directories ..."%(len(dir_dict.keys()))
    # check availability of directories
    for dir,severity in [(os.path.normpath("/%s"%(x)),{0:"W",1:"E"}[y]) for x,y in dir_dict.iteritems()]:
        if not os.path.isdir(dir):
            print " %s dir '%s' not found"%(severity,dir)
            sev_dict[severity]+=1
    if verbose:
        print "checking availability of %d files ..."%(len(file_dict.keys()))
    new_file_dict={}
    path=[x for x in os.environ["PATH"].split(":")]
    for f,severity in [(x,{0:"W",1:err_sev}[y]) for x,y in file_dict.iteritems()]:
        full_path=which(f,path)
        if not full_path:
            print " %s file '%s' not found"%(severity,os.path.basename(f))
            sev_dict[severity]+=1
        else:
            for full in full_path:
                if full not in new_file_dict.keys():
                    new_file_dict[full]=severity
    pam_conf_dir="/etc/pam.d/"
    if verbose:
        print "checking availability of %d files for pam in '%s' ..."%(len(pam_dict.keys()),pam_conf_dir)
    for f,severity in [(x,{0:"W",1:err_sev}[y]) for x,y in pam_dict.iteritems()]:
        full_path=which(f,[pam_conf_dir])
        if not full_path:
            print " %s file '%s' not found"%(severity,os.path.basename(f))
            sev_dict[severity]+=1
        else:
            for full in full_path:
                if full not in new_file_dict.keys():
                    new_file_dict[full]=severity
    for p,severity in [(x,{0:"W",1:"E"}[y]) for x,y in pam_dict.iteritems()]:
        f_path="/%s/%s"%(pam_conf_dir,p)
        pam_lib_list=[]
        if os.path.isfile(f_path):
            libs=[z[2] for z in [y.split() for y in [x.strip() for x in open(f_path,"r").read().split("\n")] if not y.startswith("#") and y] if len(z) > 2]
            for lib in libs:
                if lib not in pam_lib_list:
                    pam_lib_list+=[lib]
    if verbose:
        print "Resolving libraries ..."
    pam_lib_list=[os.path.normpath("//%s/%s"%(pam_dir,x)) for x in pam_lib_list]
    for special_lib in os.listdir(main_lib_dir):
        if special_lib.startswith("libnss") or special_lib.startswith("libnsl"):
            pam_lib_list+=[os.path.normpath("//%s/%s"%(main_lib_dir,special_lib))]
    new_libs=get_lib_list(new_file_dict.keys()+pam_lib_list)+pam_lib_list
    lib_dict={}
    if verbose:
        print "  ... found %d distinct libraries"%(len(new_libs))
        for new_lib in new_libs:
            lib_dict[new_lib]="E"
    if verbose:
        print "resolving directories of %d files and libraries ..."%(len(lib_dict.keys())+len(new_file_dict.keys()))
    dir_list=dir_dict.keys()
    for nd in [os.path.dirname(x) for x in lib_dict.keys()+new_file_dict.keys()]:
        if not nd in dir_list:
            dir_list+=[nd]
    if verbose:
        print " ... found %d distinct directories"%(len(dir_list))
    for dev_file in ["console","ram","ram0","ram1","ram2","null","zero","fd0","log","xconsole","ptmx"]:
        new_file_dict[os.path.normpath("/dev/%s"%(dev_file))]="E"
    for etc_file in ["nsswitch.conf","host.conf","services","protocols","login.defs"]:
        new_file_dict[os.path.normpath("/etc/%s"%(etc_file))]="W"
    print "Number of dirs / files / libraries: %d / %d / %d"%(len(dir_list),len(new_file_dict.keys()),len(new_libs))
    print "Starting creating of directory-history under '%s' ..."%(temp_dir)
    for dir in ["%s/%s"%(temp_dir,x) for x in dir_list]:
        if not os.path.isdir(dir):
            os.makedirs(dir)
    os.chmod("%s/tmp"%(temp_dir),01777)
    major,minor,micro,release,serial=sys.version_info
    #pprint.pprint(lib_dict)
    strip_files=[]
    for file in new_file_dict.keys():
        dest_file="%s/%s"%(temp_dir,file)
        if os.path.islink(file):
            os.symlink(os.readlink(file),dest_file)
        elif os.path.isfile(file):
            shutil.copy2(file,dest_file)
            if os.path.isfile(dest_file) and not os.path.islink(dest_file):
                strip_files+=[dest_file]
        elif os.path.exists(file):
            file_stat=os.stat(file)
            if stat.S_ISCHR(file_stat.st_mode):
                # character device
                if minor < 3:
                    f_major=commands.getoutput("ls -l %s | tr -s ' ' | cut -d ' ' -f 5 | cut -d ',' -f 1"%(file))
                    f_minor=commands.getoutput("ls -l %s | tr -s ' ' | cut -d ' ' -f 6 | cut -d ',' -f 1"%(file))
                    commands.getstatusoutput("mknod %s c %s %s"%(dest_file,f_major,f_minor))
                else:
                    os.mknod(dest_file,0600|stat.S_IFCHR,
                             os.makedev(os.major(file_stat.st_rdev),
                                        os.minor(file_stat.st_rdev)))
            elif stat.S_ISBLK(file_stat.st_mode):
                # block device
                if minor < 3:
                    f_major=commands.getoutput("ls -l %s | tr -s ' ' | cut -d ' ' -f 5 | cut -d ',' -f 1"%(file))
                    f_minor=commands.getoutput("ls -l %s | tr -s ' ' | cut -d ' ' -f 6 | cut -d ',' -f 1"%(file))
                    commands.getstatusoutput("mknod %s b %s %s"%(dest_file,f_major,f_minor))
                else:
                    os.mknod(dest_file,0600|stat.S_IFBLK,
                             os.makedev(os.major(file_stat.st_rdev),
                                        os.minor(file_stat.st_rdev)))
            #shutil.copy2(file,dest_file)
    for file in lib_dict.keys():
        dest_file="%s/%s"%(temp_dir,file)
        if os.path.islink(file):
            os.symlink(os.readlink(file),dest_file)
        elif os.path.isfile(file):
            shutil.copy2(file,dest_file)
            if os.path.isfile(dest_file) and not os.path.islink(dest_file):
                strip_files+=[dest_file]
    if strip_files:
        strip_stat,strip_out=commands.getstatusoutput("strip -s %s"%(" ".join(strip_files)))
    # generate special files
    sfile_dict={"/etc/passwd":["root::0:0:root:/root:/bin/bash",
                               "bin::1:1:bin:/bin/:/bin/bash",
                               "daemon::2:2:daemon:/sbin:/bin/bash"],
                "/etc/group":["root:x:0:root",
                              "bin:x:1:root,bin,daemon",
                              "tty:x:5:",
                              "wheel:x:10:"],
                "/etc/inetd.conf":["shell   stream  tcp     nowait  root  /usr/sbin/tcpd in.rshd -L ",
                                   "login   stream  tcp     nowait  root    /usr/sbin/tcpd  in.rlogind"],
                "/etc/xinetd.conf":["defaults",
                                    "{",
                                    "        instances               = 60",
                                    "        log_type                = SYSLOG authpriv",
                                    "        log_on_success  = HOST PID",
                                    "        log_on_failure  = HOST",
                                    "        cps   = 25 30",
                                    "}",
                                    "service shell",
                                    "{",
                                    "        disable = no",
                                    "        socket_type    = stream",
                                    "        wait   = no",
                                    "        user   = root",
                                    "        log_on_success  += USERID",
                                    "        log_on_failure    += USERID",
                                    "        server   = /usr/sbin/in.rshd",
                                    "}"],
                "/etc/hosts.allow":["ALL: ALL"],
                "/etc/ld.so.conf":["/usr/x86_64-suse-linux/lib64",
                                   "/usr/x86_64-suse-linux/lib",
                                   "/usr/local/lib",
                                   "/lib64",
                                   "/lib",
                                   "/lib64/tls",
                                   "/lib/tls",
                                   "/usr/lib64",
                                   "/usr/lib",
                                   "/usr/local/lib64"]
                }
    for sfile_name,sfile_content in sfile_dict.iteritems():
        open("%s/%s"%(temp_dir,sfile_name),"w").write("\n".join(sfile_content+[""]))
    # ldconfig call
    commands.getstatusoutput("chroot %s /sbin/ldconfig"%(temp_dir))
    # check size (not really needed, therefore commented out)
    #blks_total,blks_used,blks_free=commands.getstatusoutput("df --sync -k %s"%(temp_dir))[1].split("\n")[1].strip().split()[1:4]
    #blks_initrd=commands.getstatusoutput("du -ks %s"%(temp_dir))[1].split("\n")[0].strip().split()[0]
    #print blks_total,blks_used,blks_free,blks_initrd
    if not sev_dict["E"]:
        print "INITDIR %s"%(temp_dir)
    #shutil.rmtree(temp_dir)
    return 1

def find_free_loopdevice():
    lo_start,lo_end,lo_found=(0,8,-1)
    for lo in range(lo_start,lo_end):
        lo_dev="/dev/loop%d"%(lo)
        stat,out=commands.getstatusoutput("losetup %s 2>&1 >& /dev/null"%(lo_dev))
        if stat==256:
            lo_found=lo
            break
    return lo_found

def get_system_bitcount(root_dir):
    init_file="%s/sbin/init"%(root_dir)
    if not os.path.isfile(init_file):
        print "'%s' is not the root of a valid system (/sbin/init not found), exiting..."%(root_dir)
        sys.exit(1)
    stat,out=commands.getstatusoutput("file %s"%(init_file))
    if stat:
        print "error determining the filetype of %s (%d): %s"%(init_file,stat,out)
        sys.exit(1)
    elf_str,elf_bit=out.split(":")[1].strip().split()[0:2]
    if elf_str.lower() != "elf":
        print "error binary type '%s' unknown, exiting..."%(elf_str)
        sys.exit(1)
    if elf_bit.lower().startswith("32"):
        sys_64bit=0
    else:
        sys_64bit=1
    return sys_64bit
        
def main():
    script=sys.argv[0]
    script_basename=os.path.basename(script)
    # check runmode
    if script_basename.endswith("local.py"):
        main_local()
    else:
        main_normal()

def main_local():
    global verbose
    script=sys.argv[0]
    try:
        opts,args=getopt.getopt(sys.argv[1:],"hs:d:i",["help"])
    except getopt.GetoptError,why:
        print "Error parsing commandline : %s"%(str(why))
        sys.exit(1)
    stage_num,verbose,temp_dir,ignore_errors=(1,1,None,0)
    for opt,arg in opts:
        if opt in ["-h","--help"]:
            print "Usage : %s [OPTIONS] kerneldir"%(os.path.basename(script))
            print "  where OPTIONS is one or more of"
            print " -h, --help      this help"
            print " -s 1|2          set stage to build, defaults to %d"%(stage_num)
            print " -d TEMPDIR      temporary directory for creating of the stage-disc"
            print " -v              be verbose"
            print " -i              ignore errors"
            sys.exit(0)
        if opt=="-i":
            ignore_errors=1
        if opt=="-v":
            verbose+=1
        if opt=="-d":
            temp_dir=arg
        if opt=="-s":
            try:
                stage_num=max(1,min(2,int(arg)))
            except:
                print "Cannot parse stage_number '%s', exiting..."%(arg)
                sys.exit(1)
    if not temp_dir:
        print "Error, need temp_dir ..."
        sys.exit(1)
    print "Generating stage%d initrd ..."%(stage_num)
    if stage_num==1:
        stage_ok=populate_it(temp_dir,stage1_dir_dict,stage1_file_dict,ignore_errors)
    else:
        stage_ok=populate_it(temp_dir,stage2_dir_dict,stage2_file_dict,ignore_errors)
    sys.exit(stage_ok)

def main_normal():
    global verbose
    script=sys.argv[0]
    local_script="%s_local.py"%(script[:-3])
    try:
        opts,args=getopt.getopt(sys.argv[1:],"hs:6m:r:vki",["help"])
    except getopt.GetoptError,why:
        print "Error parsing commandline : %s"%(str(why))
        sys.exit(1)
    mods,kernel_64bit,initsize,root_dir,verbose,keep_dirs,ignore_errors=([],0,0,"/",0,0,0)
    for opt,arg in opts:
        if opt in ["-h","--help"]:
            print "Usage : %s [OPTIONS] kerneldir"%(os.path.basename(script))
            print "  where OPTIONS is one or more of"
            print " -h, --help      this help"
            print " -m MODS         comma-separated list of kernel-modules to include in the first stage"
            print " -s SIZE         set the size for the initial ramdisk, is automatically extracted from .config"
            print " -6              force 64bit Kernel"
            print " -r DIR          set rootdir to DIR, default is '%s'"%(root_dir)
            print " -v              be verbose"
            print " -k              keep stage1/2 directories after generation"
            print " -i              ignore errors"
            sys.exit(0)
        if opt=="-i":
            ignore_errors=1
        if opt=="-k":
            keep_dirs=1
        if opt=="-v":
            verbose+=1
        if opt=="-m":
            mods=[x.strip() for x in arg.split(",")]
        if opt=="-6":
            kernel_64bit=1
        if opt=="-s":
            try:
                initsize=int(arg)
            except:
                print "Cannot parse initsize '%s', exiting..."%(arg)
                sys.exit(1)
        if opt=="-r":
            if os.path.isdir(arg):
                root_dir=arg
            else:
                print "'%s' is not a directory, exiting..."
                sys.exit(1)
    if len(args) != 1:
        print "Need exactly one directory as argument (given: %d)"%(len(args))
        sys.exit(1)
    kernel_dir=args[0]
    if not os.path.isdir(kernel_dir):
        print "Need a directory as argument ('%s' is not a directory)"%(kernel_dir)
        sys.exit(1)
    act_mods=[]
    for mod in mods:
        if mod.endswith(".o"):
            mod=mod[:-2]
        elif mod.endswith(".ko"):
            mod=mod[:-3]
        act_mods+=[mod]
    # check type of build-dir linux (32/64 bit)
    build_arch_64bit=get_system_bitcount(root_dir)
    local_arch_64bit=get_system_bitcount("/")
    if build_arch_64bit > local_arch_64bit:
        print "don't known how to build a 64bit initrds on a 32bit System, exiting..."
        sys.exit(1)
    # try to get kernel config
    if os.path.isfile("%s/.config"%(kernel_dir)):
        conf_lines=[y for y in [x.strip() for x in open("%s/.config"%(kernel_dir),"r").read().split("\n") if x.strip()] if not y.strip().startswith("#")]
        conf_dict=dict([x.split("=",1) for x in conf_lines])
    else:
        conf_dict={}
    # set initsize if not already set
    if not initsize:
        initsize=int(conf_dict.get("CONFIG_BLK_DEV_RAM_SIZE","16384"))
    # check for 64bit Kernel
    if not kernel_64bit:
        kernel_64bit=conf_dict.has_key("CONFIG_X86_64")
    # check for kernel version
    kverdirs=os.listdir("%s/lib/modules"%(kernel_dir))
    if len(kverdirs) > 1:
        print "More than one KernelVersionDirectory found: %s"%(", ".join(kverdirs))
        sys.exit(1)
    elif len(kverdirs) == 0:
        print "No KernelVersionDirectory found below '%s/lib/modules'"%(kernel_dir)
        sys.exit(1)
    kverdir=kverdirs[0]
    bit_dict={0:"32",1:"64"}
    # check availability of stages
    stage_dir="/usr/local/cluster/lcs/"
    for stage in range(1,4):
        fname="/%s/stage%d"%(stage_dir,stage)
        if not os.path.isfile(fname):
            print "Cannot find stage %d file %s"%(stage,fname)
            sys.exit(1)
    free_lo_dev=find_free_loopdevice()
    if free_lo_dev == -1:
        print "Cannot find free loopdevice, exiting..."
        sys.exit(1)
    loop_dev="/dev/loop%d"%(free_lo_dev)
    print "Kernel directory is '%s', initsize is %d kbytes"%(kernel_dir,initsize)
    print "  kernel_version is %s, %s-bit kernel"%(kverdir,bit_dict[kernel_64bit])
    print "  build_dir is '%s', %s-bit linux"%(root_dir,bit_dict[build_arch_64bit])
    print "  local_system is a %s-bit linux"%(bit_dict[local_arch_64bit])
    print "  will use loopdevice %s to build stage1 initrd"%(loop_dev)
    # get kernel-module dependencies
    if act_mods:
        all_mods=get_module_dependencies(kernel_dir,act_mods)
        print "  %d kernel-modules given: %s; %d modules have to be installed"%(len(act_mods),", ".join(act_mods),len(all_mods))
    else:
        all_mods=[]
        print "  no kernel-modules given"
    if root_dir != "/":
        loc_src,loc_dst=(script,"%s/%s"%(root_dir,os.path.basename(local_script)))
        print "  copying %s to %s"%(loc_src,loc_dst)
        shutil.copy(loc_src,loc_dst)
    # setting up loopdevice for stage1
    stage1_file="/%s/initrd"%(kernel_dir)
    stage2_file="/%s/initrd_stage2.gz"%(kernel_dir)
    if os.path.isfile(stage2_file):
        os.unlink(stage2_file)
    major,minor,micro,release,serial=sys.version_info
    if minor < 3:
        tempfile.tempdir="/%s/tmp/"%(root_dir)
        stage1_dir=tempfile.mktemp(".stage1_dir")
        stage2_dir=tempfile.mktemp(".stage2_dir")
        os.mkdir(stage1_dir)
        os.mkdir(stage2_dir)
    else:
        stage1_dir=tempfile.mkdtemp(".stage1_dir","/%s/tmp/.rdc_"%(root_dir))
        stage2_dir=tempfile.mkdtemp(".stage2_dir","/%s/tmp/.rdc_"%(root_dir))
    stat_out=[]
    stat_out+=[("dd",commands.getstatusoutput("dd if=/dev/zero of=%s bs=1024 count=%d"%(stage1_file,initsize)))]
    stat_out+=[("losetup",commands.getstatusoutput("losetup %s %s"%(loop_dev,stage1_file)))]
    stat_out+=[("mkfs.ext2",commands.getstatusoutput("mkfs.ext2 -F -v -m 0 -b 1024 %s %d"%(stage1_file,initsize)))]
    stat_out+=[("mount",commands.getstatusoutput("mount -o loop -t ext2 %s %s"%(stage1_file,stage1_dir)))]
    if [x for name,(x,y) in stat_out if x]:
        print "Something went wrong during setupt of stage1:"
        for name,(x,y) in stat_out:
            print "%s (%d) : \n%s"%(name,x,"\n".join([" - %s"%(z) for z in y.split("\n")]))
    stage_targ_dirs=[stage1_dir,stage2_dir]
    stage_dirs=[]
    for stage in range(1,3):
        print "Generating stage%d initrd ..."%(stage)
        act_stage_dir=stage_targ_dirs[stage-1]
        loc_root_dir="/".join([""]+act_stage_dir.split("/")[-2:])
        loc_args=""
        if ignore_errors:
            loc_args+=" -i "
        print "chroot %s /%s %s -d %s -s %d"%(root_dir,os.path.basename(local_script),loc_args,loc_root_dir,stage)
        if root_dir != "/":
            stat,out=commands.getstatusoutput("chroot %s /%s %s -d %s -s %d"%(root_dir,os.path.basename(local_script),loc_args,loc_root_dir,stage))
        else:
            stat,out=commands.getstatusoutput("%s %s -s %d -d %s "%(local_script,loc_args,stage,loc_root_dir))
        if verbose:
            print "\n".join([" - %s"%(x) for x in out.split("\n")])
        #print stat,out
        act_stage_dir=[y.split()[1].strip() for y in [x.strip() for x in out.strip().split("\n")] if y.startswith("INITDIR")]
        if act_stage_dir:
            stage_dirs+=["%s/%s"%(root_dir,act_stage_dir[0])]
        else:
            #print out
            print "Error generating stage%d dir"%(stage)
            print "\n".join(["  - %s"%(x) for x in out.split("\n") if x.strip().startswith("E ")])
    stage_dirs_ok=(len(stage_dirs)==2)
    if stage_dirs_ok:
        # add stagefiles
        stage_dest=["/%s/%s"%(stage_dirs[0],LINUXRC_NAME),"/%s/%s"%(stage_dirs[1],LINUXRC_NAME),"/%s/sbin/stage3"%(stage_dirs[0])]
        for i in range(0,3):
            shutil.copy2("/%s/stage%d"%(stage_dir,i+1),stage_dest[i])
            os.chmod(stage_dest[i],0744)
            os.chown(stage_dest[i],0,0)
        # add kernel-modules to stage1
        kmod_dir="/%s/lib/modules/%s/kernel/drivers"%(stage_dirs[0],kverdir)
        os.makedirs(kmod_dir)
        if all_mods:
            for mod in [x for x in all_mods if x]:
                shutil.copy2(mod,kmod_dir)
    # umount stage1_dir
    commands.getstatusoutput("umount %s"%(stage1_file))
    commands.getstatusoutput("losetup -d %s"%(loop_dev))
    if stage_dirs_ok:
        # zip stage1
        commands.getstatusoutput("gzip -f -9 %s"%(stage1_file))
        # create stage2
        commands.getstatusoutput("tar cpsjf %s -C %s ."%(stage2_file,stage_targ_dirs[1]))
    # cleaning up
    if root_dir != "/":
        os.unlink(loc_dst)
    if not keep_dirs:
        for dir in stage_dirs:
            print "removing directory %s ..."%(dir)
            shutil.rmtree(dir)
    return

if __name__=="__main__":
    main()
