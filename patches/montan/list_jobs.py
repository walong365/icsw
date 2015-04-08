#!/usr/bin/env python
#
#   (C) 2001 by Argonne National Laboratory.
#       See COPYRIGHT in top-level directory.
#

from sys     import argv, exit, exc_info
from os      import environ, getuid, close, listdir
from os.path import isfile
from socket  import socket, fromfd, AF_UNIX, SOCK_STREAM
from re      import sub
from signal  import signal, alarm, SIG_DFL, SIGINT, SIGTSTP, SIGCONT, SIGALRM
from mpdlib  import mpd_set_my_id, mpd_send_one_msg, mpd_recv_one_msg, \
                    mpd_get_my_username, mpd_raise, mpdError, mpd_send_one_line
import commands
import getopt

def get_running_jobs():
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"),
                          ("SGE_CELL", "/etc/sge_cell")]:
        if not environ.has_key(v_name):
            if isfile(v_src):
                environ[v_name] = file(v_src, "r").read().strip()
            else:
                print "error Cannot assign environment-variable '%s', exiting..." % (v_name)
                exit(1)
    arch = commands.getoutput("/%s/util/arch" % (environ["SGE_ROOT"]))
    stat, jobs = commands.getstatusoutput("/%s/bin/%s/qstat" % (environ["SGE_ROOT"], arch))
    if not stat:
        job_stuff = [x.strip().split() for x in jobs.split("\n")][2:]
        jobs = []
        for what in job_stuff:
            if what[4].lower().count("r"):
                if len(what) == 10:
                    jobs.append("%s.%s" % (what[0], what[9]))
                else:
                    jobs.append("%s.1" % (what[0]))
    else:
        jobs = []
    jobs.sort()
    return jobs

def mpdlistjobs():
    mpd_set_my_id("mpdlistjobs_")
    try:
        opts, args = getopt.getopt(argv[1:], "u:h", ["help", "sss"])
    except:
        print "Something went wrong while parsing arguments: %s (%s)" % (str(exc_info()[0]),
                                                                         str(exc_info()[1]))
        exit(-1)
    username = None
    uname    = ""
    jobid    = ""
    sjobid   = ""
    jobalias = ""
    sss_switch = False
    for opt, arg in opts:
        if opt in  ["-h", "--help"]:
            print "usage: mpdlistjobs [-u | --user username] [-a | --alias jobalias] ",
            print "[-j | --jobid jobid]"
            print "  (only use one of jobalias or jobid)"
            print "lists jobs being run by an mpd ring, all by default, or filtered"
            print "by user, mpd job id, or alias assigned when the job was submitted"
            exit(-1)
        elif opt in ["-u"]:
            username = arg
        elif opt in ["-j", "--jobid"]:
            jobid = arg
            sjobid = jobid.split("@")    # jobnum and originating host
        elif opt in ["-a", "--alias"]:
            jobalias = arg
        elif opt in ["--sss"]:
            sss_switch = True
    if username:
        consoleNames = ["/tmp/mpd2.console_%s" % (username)]
        single_user = True
    else:
        consoleNames = ["/tmp/%s" % (x) for x in listdir("/tmp") if x.startswith("mpd2.")]
        single_user = False
    job_dict = {}
    for consoleName in consoleNames:
        username = consoleName.split("_")[1]
        conSocket = socket(AF_UNIX,SOCK_STREAM)  # note: UNIX socket
        try:
            conSocket.connect(consoleName)
        except Exception, errmsg:
            if single_user:
                mpd_raise("cannot connect to local mpd '%s'" % (consoleName))
        else:
                # mpd_raise("cannot connect to local mpd; errmsg: %s" % (str(errmsg)) )
            msgToSend = "realusername=%s\n" % username
            mpd_send_one_line(conSocket,msgToSend)

            msgToSend = { "cmd" : "mpdlistjobs" }
            mpd_send_one_msg(conSocket,msgToSend)
            msg = recv_one_msg_with_timeout(conSocket,5)
            if not msg:
                mpd_raise("no msg recvd from mpd before timeout")
            if msg["cmd"] != "local_mpdid":     # get full id of local mpd for filters later
                mpd_raise("did not recv local_mpdid msg from local mpd; instead, recvd: %s" % msg)
            else:
                if len(sjobid) == 1:
                    sjobid.append(msg["id"])
            while 1:
                msg = mpd_recv_one_msg(conSocket)
                if not msg.has_key("cmd"):
                    raise RuntimeError, "mpdlistjobs: INVALID msg=:%s:" % (msg)
                if msg["cmd"] == "mpdlistjobs_info" and msg.has_key("sge_job_id"):
                    msg["console_name"] = consoleName
                    msg["username"] = username
                    job_dict.setdefault("%s.%s" % (msg["sge_job_id"], msg["sge_task_id"]), []).append(msg)
                else:
                    break  # mpdlistjobs_trailer
    jobs_running = get_running_jobs()
    print "Found %d jobs in SGE: %s" % (len(jobs_running), ", ".join(jobs_running))
    job_ids = job_dict.keys()
    if job_ids:
        # get process list
        job_ids.sort()
        print "Found %d jobs running via MPD: %s" % (len(job_ids), ", ".join([str(x) for x in job_ids]))
        kill_jobs = [x for x in job_ids if x not in jobs_running]
        if kill_jobs:
            print "Found %d jobs to kill: %s" % (len(kill_jobs), ", ".join(kill_jobs))
            for kill_job in kill_jobs:
                job_stuff = job_dict[kill_job][0]
                consoleName = job_stuff["console_name"]
                try:
                    conSocket.connect(consoleName)
                except Exception, errmsg:
                    print "cannot connect to local mpd (%s); possible causes:" % consoleName
                    print "    1. no mpd running on this host"
                    print "    2. mpd is running but was started without a 'console' (-n option)"
                else:
                    msgToSend = 'realusername=%s\n' % job_stuff["username"]
##                     mpd_send_one_line(conSocket,msgToSend)
##                     smjobid = job_stuff["jobid"].split()
##                     while len(smjobid) < 3:
##                         smjobid.append("")
##                     mpd_send_one_msg(conSocket, {"cmd"      : "mpdkilljob",
##                                                  "jobnum"   : smjobid[0],
##                                                  "mpdid"    : "%s@%s" % (smjobid[0], smjobid[1]),
##                                                  "jobalias" : "",
##                                                  "username" : username})
##                     msg = recv_one_msg_with_timeout(conSocket,5)
##                     if not msg:
##                         print "no msg recvd from mpd before timeout"
##                     else:
##                         if msg["cmd"] != "mpdkilljob_ack":
##                             if msg["cmd"] == "already_have_a_console":
##                                 print "mpd already has a console (e.g. for long ringtest); try later"
##                             else:
##                                 print "unexpected message from mpd: %s" % (msg)
##                         if not msg["handled"]:
##                             print 'job not found'
            
def signal_handler(signum,frame):
    if signum == SIGALRM:
        pass
    else:
        exit(-1)

def recv_one_msg_with_timeout(sock,timeout):
    oldTimeout = alarm(timeout)
    msg = mpd_recv_one_msg(sock)    # fails WITHOUT a msg if sigalrm occurs
    alarm(oldTimeout)
    return(msg)

if __name__ == "__main__":
    signal(SIGINT,signal_handler)
    signal(SIGALRM,signal_handler)
    try:
        mpdlistjobs()
    except mpdError, errmsg:
        print "mpdlistjobs failed: %s" % (errmsg)
