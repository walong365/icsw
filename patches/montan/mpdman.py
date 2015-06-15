#!/usr/bin/env python
#
#   (C) 2001 by Argonne National Laboratory.
#       See COPYRIGHT in top-level directory.
#

from os       import environ, getpid, pipe, fork, fdopen, read, write, close, dup2, \
                     chdir, execvpe, kill, waitpid, strerror, setpgrp, WNOHANG, X_OK, \
                     path, access
from errno    import EINTR
from sys      import exit
from socket   import gethostname, fromfd, AF_INET, SOCK_STREAM
from select   import select, error
from re       import findall, sub
from signal   import signal, SIGINT, SIGKILL, SIGUSR1, SIGTSTP, SIGCONT, SIGCHLD, SIG_DFL
from md5      import new
from cPickle  import loads
from urllib   import quote
from resource import setrlimit  # others imported in set_limits as needed
from mpdlib   import mpd_set_my_id, mpd_print, mpd_print_tb, \
                     mpd_send_one_msg, mpd_send_one_msg_noprint, mpd_recv_one_msg, \
                     mpd_send_one_line, mpd_send_one_line_noprint, mpd_recv_one_line, \
                     mpd_get_inet_listen_socket, mpd_get_inet_socket_and_connect, \
                     mpd_get_my_username, mpd_raise, mpdError, mpd_version, \
                     mpd_socketpair, mpd_get_ranks_in_binary_tree

global clientPid, clientExited, clientExitStatus, clientExitStatusSent

from syslog    import syslog, openlog, closelog, LOG_DAEMON, LOG_INFO, LOG_ERR

def log(what):
    syslog(LOG_INFO, what)

def mpdman():
    global clientPid, clientExited, clientExitStatus, clientExitStatusSent
    clientExited = 0
    clientExitStatusSent = 0
    signal(SIGCHLD,sigchld_handler)

    myHost = environ['MPDMAN_MYHOST']
    myRank = int(environ['MPDMAN_RANK'])
    myId = myHost + '_mpdman_' + str(myRank)
    spawned = int(environ['MPDMAN_SPAWNED'])
    if spawned:
        myId = myId + '_s'
    mpd_set_my_id(myId)
    try:
        chdir(environ['MPDMAN_CWD'])
    except Exception, errmsg:
        errmsg =  '%s: invalid dir: %s' % (myId,environ['MPDMAN_CWD'])
        # print errmsg    ## may syslog it in some cases ?
    clientPgm = environ['MPDMAN_CLI_PGM']
    clientPgmArgs = loads(environ['MPDMAN_PGM_ARGS'])
    clientPgmEnv = loads(environ['MPDMAN_PGM_ENVVARS'])
    clientPgmLimits = loads(environ['MPDMAN_PGM_LIMITS'])
    mpd_print(0000, 'entering mpdman to exec %s' % (clientPgm) )
    jobid = environ['MPDMAN_JOBID']
    nprocs = int(environ['MPDMAN_NPROCS'])
    mpdPort = int(environ['MPDMAN_MPD_LISTEN_PORT'])
    mpdConfPasswd = environ['MPDMAN_MPD_CONF_SECRETWORD']
    environ['MPDMAN_MPD_CONF_SECRETWORD'] = ''  ## do NOT pass it on to clients
    conHost = environ['MPDMAN_CONHOST']
    conPort = int(environ['MPDMAN_CONPORT'])
    lhsHost = environ['MPDMAN_LHSHOST']
    lhsPort = int(environ['MPDMAN_LHSPORT'])
    host0 = environ['MPDMAN_HOST0']        # only used by right-most man
    port0 = int(environ['MPDMAN_PORT0'])   # only used by right-most man
    myPort = int(environ['MPDMAN_MY_LISTEN_PORT'])
    mpd_print(0000, "lhost=%s lport=%d h0=%s p0=%d" % (lhsHost,lhsPort,host0,port0) )
    listenFD = int(environ['MPDMAN_MY_LISTEN_FD'])
    listenSocket = fromfd(listenFD,AF_INET,SOCK_STREAM)
    close(listenFD)
    socketsToSelect = { listenSocket : 1 }    # initial value
    mpdFD = int(environ['MPDMAN_TO_MPD_FD'])
    mpdSocket = fromfd(mpdFD,AF_INET,SOCK_STREAM)
    close(mpdFD)
    socketsToSelect[mpdSocket] = 1
    lineLabels = int(environ['MPDMAN_LINE_LABELS'])
    gdb = int(environ['MPDMAN_GDB'])
    startStdoutLineLabel = 1
    startStderrLineLabel = 1
    myLineLabel = str(myRank) + ': '
    stdinGoesToWho = environ['MPDMAN_STDIN_GOES_TO_WHO']

    # set up pmi stuff early in case I was spawned
    KVSs = {}
    kvsname_template = 'kvs_' + host0 + '_' + str(port0) + '_'
    default_kvsname = kvsname_template + '0'
    default_kvsname = sub('\.','_',default_kvsname)  # chg magpie.cs to magpie_cs
    default_kvsname = sub('\-','_',default_kvsname)  # chg node-0 to node_0
    KVSs[default_kvsname] = {}
    cli_environ = {}
    for k in clientPgmEnv.keys():
        if k.startswith('MPI_APPNUM'):
            KVSs[default_kvsname][k] = clientPgmEnv[k]
        else:
            cli_environ[k] = clientPgmEnv[k]
    kvs_next_id = 1
    jobEndingEarly = 0
    pmiCollectiveJob = 0
    spawnedCnt = 0
    doingBNR = 0  ## BNR
    pmiSocket = 0   # obtained in later

    if nprocs == 1:  # one-man ring
        lhsSocket = mpd_get_inet_socket_and_connect(host0,port0)  # to myself
        (rhsSocket,rhsAddr) = listenSocket.accept()
    else:
        if myRank == 0:
            for i in range(2):    # accept lhs and rhs
                (tempSocket,tempAddr) = listenSocket.accept()
                msg = mpd_recv_one_msg(tempSocket)
                if msg['cmd'] == 'i_am_lhs':
                    (lhsSocket,lhsAddr) = (tempSocket,tempAddr)
                else:
                    (rhsSocket,rhsAddr) = (tempSocket,tempAddr)
        else:
            lhsSocket = mpd_get_inet_socket_and_connect(lhsHost,lhsPort)
            mpd_send_one_msg(lhsSocket, { 'cmd' : 'i_am_rhs' } )
            if myRank == (nprocs-1):              # right-most man
                rhsSocket = mpd_get_inet_socket_and_connect(host0,port0)
                mpd_send_one_msg(rhsSocket, { 'cmd' : 'i_am_lhs' } )
            else:
                (rhsSocket,rhsAddr) = listenSocket.accept()
                msg = mpd_recv_one_msg(rhsSocket)  # drain out the i_am_... msg
    socketsToSelect[lhsSocket] = 1
    socketsToSelect[rhsSocket] = 1

    if myRank == 0:
        conSocket = mpd_get_inet_socket_and_connect(conHost,conPort)  # for cntl msgs
        socketsToSelect[conSocket] = 1
        if spawned:
            msgToSend = { 'cmd' : 'spawned_child_is_up',
                          'spawned_id' : environ['MPDMAN_SPAWNED'] }
            mpd_send_one_msg(conSocket,msgToSend)
            msg = mpd_recv_one_msg(conSocket)
            if msg['cmd'] != 'preput_info_for_child':
                mpd_print(1,'invalid msg from parent :%s:' % msg)
                exit(-1)
            try:
                for k in msg['kvs'].keys():
                    KVSs[default_kvsname][k] = msg['kvs'][k]
            except:
                mpd_print(1,'failed to insert preput_info')
                exit(-1)
            msg = mpd_recv_one_msg(conSocket)
            if not msg  or  not msg.has_key('cmd')  or  msg['cmd'] != 'ringsize':
                mpd_raise(1, 'spawned: bad msg from con; got: %s' % (msg) )
            universeSize = msg['ringsize']
            mpd_send_one_msg(rhsSocket,msg)  # forward it on
        else:
            msgToSend = { 'cmd' : 'man_checking_in' }
            mpd_send_one_msg(conSocket,msgToSend)
            msg = mpd_recv_one_msg(conSocket)
            if not msg  or  not msg.has_key('cmd')  or  msg['cmd'] != 'ringsize':
                mpd_raise(1, 'invalid msg from con; expecting ringsize got: %s' % (msg) )
            if environ.has_key('MPI_UNIVERSE_SIZE'):
                universeSize = int(environ['MPI_UNIVERSE_SIZE'])
            else:
                universeSize = msg['ringsize']
            mpd_send_one_msg(rhsSocket,msg)
        ## NOTE: if you spawn a non-MPI job, it may not send this msg
        ## in which case the pgm will hang
        stdoutToConSocket = mpd_get_inet_socket_and_connect(conHost,conPort)
        if spawned:
            msgToSend = { 'cmd' : 'child_in_stdout_tree', 'from_rank' : myRank }
            mpd_send_one_msg(stdoutToConSocket,msgToSend)
        stderrToConSocket = mpd_get_inet_socket_and_connect(conHost,conPort)
        if spawned:
            msgToSend = { 'cmd' : 'child_in_stderr_tree', 'from_rank' : myRank }
            mpd_send_one_msg(stderrToConSocket,msgToSend)
    else:
        conSocket = 0

    msg = mpd_recv_one_msg(lhsSocket)    # recv msg containing ringsize
    if not msg  or  not msg.has_key('cmd')  or  msg['cmd'] != 'ringsize':
        mpd_raise(1, 'invalid msg from lhs; expecting ringsize got: %s' % (msg) )
    if myRank != 0:
        mpd_send_one_msg(rhsSocket,msg)
        if not environ.has_key('MPI_UNIVERSE_SIZE'):
            universeSize = msg['ringsize']

    (clientListenSocket,clientListenPort) = mpd_get_inet_listen_socket('',0)
    (pipe_read_cli_stdin, pipe_write_cli_stdin )  = pipe()
    (pipe_read_cli_stdout,pipe_write_cli_stdout) = pipe()
    (pipe_read_cli_stderr,pipe_write_cli_stderr) = pipe()
    (pipe_cli_end,pipe_man_end) = pipe()
    (pmiListenSocket,pmiPort) = mpd_get_inet_listen_socket(myHost,0)
    clientPid = fork()
    if clientPid == 0:
        mpd_set_my_id(gethostname() + '_man_before_exec_client_' + `getpid()`)
        lhsSocket.close()
        rhsSocket.close()
        listenSocket.close()
        if conSocket:
            conSocket.close()
        pmiListenSocket.close()
        setpgrp()

        close(pipe_write_cli_stdin)
        dup2(pipe_read_cli_stdin,0)  # closes fd 0 (stdin) if open

        # to simply print on the mpd's tty:
        #     comment out the next lines
        close(pipe_read_cli_stdout)
        dup2(pipe_write_cli_stdout,1)  # closes fd 1 (stdout) if open
        close(pipe_write_cli_stdout)
        close(pipe_read_cli_stderr)
        dup2(pipe_write_cli_stderr,2)  # closes fd 2 (stderr) if open
        close(pipe_write_cli_stderr)

        msg = read(pipe_cli_end,2)
        if msg != 'go':
            mpd_raise('%s: invalid go msg from man :%s:' % (myId,msg) )
        close(pipe_cli_end)

        clientPgmArgs = [clientPgm] + clientPgmArgs
        cli_environ['PATH'] = environ['MPDMAN_CLI_PATH']
        cli_environ['PMI_PORT'] = '%s:%s' % (myHost,pmiPort)
        cli_environ['PMI_SIZE'] = str(nprocs)
        cli_environ['PMI_RANK'] = str(myRank)
        cli_environ['PMI_DEBUG'] = str(0)
        if spawned:
            cli_environ['PMI_SPAWNED'] = '1'
        else:
            cli_environ['PMI_SPAWNED'] = '0'
        cli_environ['MPD_TVDEBUG'] = str(0)                                    ## BNR
        cli_environ['MPD_JID'] = environ['MPDMAN_JOBID']                       ## BNR
        cli_environ['MPD_JSIZE'] = str(nprocs)                                 ## BNR
        cli_environ['MPD_JRANK'] = str(myRank)                                 ## BNR
        ##### cli_environ['MAN_MSGS_FD'] = cli_environ['PMI_FD'] # same as PMI_FD    ## BNR
        cli_environ['CLIENT_LISTENER_FD'] = str(clientListenSocket.fileno())   ## BNR
        errmsg = set_limits(clientPgmLimits)
        if errmsg:
            pmiSocket = mpd_get_inet_socket_and_connect(myHost,pmiPort)
            reason = quote(str(errmsg))
            pmiMsgToSend = 'cmd=execution_problem reason=%s\n' % (reason)
            mpd_send_one_line(pmiSocket,pmiMsgToSend)
            exit(0)
        if environ.has_key("MPDMAN_ACT_CPU"):
            act_cpu = int(environ["MPDMAN_ACT_CPU"])
            log("using cpu %d for %s" % (act_cpu, clientPgm))
        else:
            act_cpu = None
        try:
            if act_cpu is not None:
                clientPgmArgs = ["/usr/sbin/runon", "%d" % (act_cpu)] + clientPgmArgs
                clientPgm = "/usr/sbin/runon"
            #log("execvpe %s %s" % (str(act_cpu), str(clientPgmArgs)))
            mpd_print(0000, 'execing clientPgm=:%s:' % (clientPgm) )
            if gdb:
                fullDirName = environ['MPDMAN_FULLPATHDIR']
                gdbdrv = path.join(fullDirName,'mpdgdbdrv.py')
                if not access(gdbdrv,X_OK):
                    print 'mpdman: cannot execute mpdgdbdrv %s' % gdbdrv
                    exit(0)
                clientPgmArgs.insert(0,clientPgm)
                execvpe(gdbdrv,clientPgmArgs,cli_environ)    # client
            else:
                execvpe(clientPgm,clientPgmArgs,cli_environ)    # client
        except Exception, errmsg:
            ## mpd_raise('execvpe failed for client %s; errmsg=:%s:' % (clientPgm,errmsg) )
            # print '%s: could not run %s; probably executable file not found' % (myId,clientPgm)
            pmiSocket = mpd_get_inet_socket_and_connect(myHost,pmiPort)
            reason = quote(str(errmsg))
            pmiMsgToSend = 'cmd=execution_problem reason=%s\n' % (reason)
            mpd_send_one_line(pmiSocket,pmiMsgToSend)
            exit(0)
        exit(0)
    msgToSend = { 'cmd' : 'client_pid', 'jobid' : jobid,
                  'manpid' : getpid(), 'clipid' : clientPid, 'rank' : myRank }
    mpd_send_one_msg(mpdSocket,msgToSend)
    close(pipe_read_cli_stdin)
    close(pipe_write_cli_stdout)
    close(pipe_write_cli_stderr)
    clientStdoutFD = pipe_read_cli_stdout
    # clientStdoutFile = fdopen(clientStdoutFD,'r')
    socketsToSelect[clientStdoutFD] = 1
    clientStderrFD = pipe_read_cli_stderr
    # clientStderrFile = fdopen(clientStderrFD,'r')
    socketsToSelect[clientStderrFD] = 1
    clientListenSocket.close()
    numWithIO = 2    # stdout and stderr so far
    numConndWithIO = 2
    waitPids = [clientPid]

    socketsToSelect[pmiListenSocket] = 1

    # begin setup of stdio tree
    (parent,lchild,rchild) = mpd_get_ranks_in_binary_tree(myRank,nprocs)
    spawnedChildSockets = []
    childrenStdoutTreeSockets = []
    childrenStderrTreeSockets = []
    if lchild >= 0:
        numWithIO += 2    # stdout and stderr from child
        msgToSend = { 'cmd' : 'info_for_parent_in_tree',
                      'to_rank' : str(lchild),
                      'parent_host' : myHost,
                      'parent_port' : myPort }
        mpd_send_one_msg(rhsSocket,msgToSend)
    if rchild >= 0:
        numWithIO += 2    # stdout and stderr from child
        msgToSend = { 'cmd' : 'info_for_parent_in_tree',
                      'to_rank' : str(rchild),
                      'parent_host' : myHost,
                      'parent_port' : myPort }
        mpd_send_one_msg(rhsSocket,msgToSend)
    if myRank == 0:
        parentStdoutSocket = stdoutToConSocket
        parentStderrSocket = stderrToConSocket
    else:
        parentStdoutSocket = 0
        parentStderrSocket = 0

    if environ.has_key('MPDMAN_RSHIP'):
        rship = environ['MPDMAN_RSHIP']
        # (rshipSocket,rshipPort) = mpd_get_inet_listen_socket('',0)
        rshipPid = fork()
        if rshipPid == 0:
            environ['MPDCP_MSHIP_HOST'] = environ['MPDMAN_MSHIP_HOST']
            environ['MPDCP_MSHIP_PORT'] = environ['MPDMAN_MSHIP_PORT']
            environ['MPDCP_MSHIP_NPROCS'] = str(nprocs)
            environ['MPDCP_CLI_PID'] = str(clientPid)
            try:
                execvpe(rship,[rship],environ)
            except Exception, errmsg:
                # make sure my error msgs get to console
                dup2(parentStdoutSocket.fileno(),1)  # closes fd 1 (stdout) if open
                dup2(parentStderrSocket.fileno(),2)  # closes fd 2 (stderr) if open
                mpd_raise('execvpe failed for copgm %s; errmsg=:%s:' % (rship,errmsg) )
            exit(0)
        # rshipSocket.close()
        waitPids.append(rshipPid)

    pmiBarrierInRecvd = 0
    holdingPMIBarrierLoop1 = 0
    if myRank == 0:
        holdingEndBarrierLoop1 = 1
        holdingJobgoLoop1 = 1
    else:
        holdingEndBarrierLoop1 = 0
        holdingJobgoLoop1 = 0
    jobStarted = 0
    endBarrierDone = 0
    numDone = 0
    while not endBarrierDone:
        if holdingJobgoLoop1 or clientExited:
            selectTime = 0.05
        else:
            selectTime = 4
        try:
            (inReadySockets,unused1,unused2) = select(socketsToSelect.keys(),[],[],selectTime)
        except error, data:
            if data[0] == EINTR:        # will come here if receive SIGCHLD, for example
                continue
            else:
                mpd_raise('select error: %s' % strerror(data[0]))
        except Exception, data:
            mpd_raise('other error after select %s :%s:' % ( data.__class__, data) )
        if holdingJobgoLoop1 and numConndWithIO >= numWithIO:
            holdingJobgoLoop1 = 0
            msgToSend = { 'cmd' : 'jobgo_loop_1' }
            mpd_send_one_msg(rhsSocket,msgToSend)
        if clientExited:
            if jobStarted  and  not clientExitStatusSent:
                msgToSend = { 'cmd' : 'client_exit_status', 'man_id' : myId,
                              'cli_status' : clientExitStatus, 'cli_host' : gethostname(),
                              'cli_pid' : clientPid, 'cli_rank' : myRank }
                if myRank == 0:
                    if conSocket:
                        mpd_send_one_msg_noprint(conSocket,msgToSend)
                else:
                    if rhsSocket:
                        mpd_send_one_msg(rhsSocket,msgToSend)
                clientExitStatusSent = 1
            if holdingEndBarrierLoop1 and (myRank == 0 or numDone >= numWithIO):
                holdingEndBarrierLoop1 = 0
                msgToSend = {'cmd' : 'end_barrier_loop_1'}
                mpd_send_one_msg(rhsSocket,msgToSend)
        for readySocket in inReadySockets:
            if readySocket not in socketsToSelect.keys():
                continue
            if readySocket == listenSocket:
                (tempSocket,tempConnAddr) = listenSocket.accept()
                msg = mpd_recv_one_msg(tempSocket)
                if msg  and  msg.has_key('cmd'):
                    if msg['cmd'] == 'child_in_stdout_tree':
                        socketsToSelect[tempSocket] = 1
                        childrenStdoutTreeSockets.append(tempSocket)
                        numConndWithIO += 1
                    elif msg['cmd'] == 'child_in_stderr_tree':
                        socketsToSelect[tempSocket] = 1
                        childrenStderrTreeSockets.append(tempSocket)
                        numConndWithIO += 1
                    elif msg['cmd'] == 'spawned_child_is_up':
                        socketsToSelect[tempSocket] = 1
                        spawnedChildSockets.append(tempSocket)
                        tempID = msg['spawned_id']
                        spawnedKVSname = 'mpdman_kvs_for_spawned_' + tempID
                        msgToSend = { 'cmd' : 'preput_info_for_child',
                                      'kvs' : KVSs[spawnedKVSname] }
                        mpd_send_one_msg(tempSocket,msgToSend)
                        msgToSend = { 'cmd' : 'ringsize', 'ringsize' : universeSize }
                        mpd_send_one_msg(tempSocket,msgToSend)
                        if pmiSocket:  # may have disappeared in early shutdown
                            pmiMsgToSend = 'cmd=spawn_result status=spawn_done\n'
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        mpd_print(1, 'unknown msg recvd on listenSocket :%s:' % (msg) )
            elif readySocket == lhsSocket:
                msg = mpd_recv_one_msg(lhsSocket)
                if not msg:
                    mpd_print(0000, 'lhs died' )
                    del socketsToSelect[lhsSocket]
                    lhsSocket.close()
                elif msg['cmd'] == 'jobgo_loop_1':
                    if myRank == 0:
			# let console pgm proceed
                        msgToSend = { 'cmd' : 'job_started', 'jobid' : jobid }
                        mpd_send_one_msg_noprint(conSocket,msgToSend)
                        msgToSend = { 'cmd' : 'jobgo_loop_2' }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                    else:
                        if numConndWithIO >= numWithIO:
                            mpd_send_one_msg(rhsSocket,msg)  # forward it on
                        else:
                            holdingJobgoLoop1 = 1
                elif msg['cmd'] == 'jobgo_loop_2':
                    if myRank != 0:
                       mpd_send_one_msg(rhsSocket,msg)  # forward it on
                    write(pipe_man_end,'go')
                    close(pipe_man_end)
                    jobStarted = 1
                elif msg['cmd'] == 'info_for_parent_in_tree':
                    if int(msg['to_rank']) == myRank:
                        parentHost = msg['parent_host']
                        parentPort = msg['parent_port']
                        parentStdoutSocket = \
                            mpd_get_inet_socket_and_connect(parentHost,parentPort)
                        msgToSend = { 'cmd' : 'child_in_stdout_tree', 'from_rank' : myRank }
                        mpd_send_one_msg(parentStdoutSocket,msgToSend)
                        parentStderrSocket = \
                            mpd_get_inet_socket_and_connect(parentHost,parentPort)
                        msgToSend = { 'cmd' : 'child_in_stderr_tree', 'from_rank' : myRank }
                        mpd_send_one_msg(parentStderrSocket,msgToSend)
                    else:
                        mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'end_barrier_loop_1':
                    if myRank == 0:
                        msgToSend = { 'cmd' : 'end_barrier_loop_2' }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                    else:
                        if numDone >= numWithIO:
			    if rhsSocket:
                                mpd_send_one_msg(rhsSocket,msg)
                        else:
                            holdingEndBarrierLoop1 = 1
                elif msg['cmd'] == 'end_barrier_loop_2':
                    endBarrierDone = 1
                    if myRank != 0:
                        mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'pmi_barrier_loop_1':
                    if myRank == 0:
                        msgToSend = { 'cmd' : 'pmi_barrier_loop_2' }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                        if doingBNR:    ## BNR
                            pmiMsgToSend = 'cmd=client_bnr_fence_out\n'
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                            select([],[],[],0.1)  # minor pause before intr
                            kill(clientPid,SIGUSR1)
                        else:
                            pmiMsgToSend = 'cmd=barrier_out\n'
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        holdingPMIBarrierLoop1 = 1
                        if pmiBarrierInRecvd:
                            mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'pmi_barrier_loop_2':
                    pmiBarrierInRecvd = 0
                    holdingPMIBarrierLoop1 = 0
                    if myRank != 0:
                        mpd_send_one_msg(rhsSocket,msg)
                        if doingBNR:    ## BNR
                            pmiMsgToSend = 'cmd=client_bnr_fence_out\n'
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                            select([],[],[],0.1)  # minor pause before intr
                            kill(clientPid,SIGUSR1)
                        else:
                            pmiMsgToSend = 'cmd=barrier_out\n'
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif msg['cmd'] == 'pmi_get':
                    if msg['from_rank'] == myRank:
                        if pmiSocket:  # may have disappeared in early shutdown
                            pmiMsgToSend = 'cmd=get_result rc=-1 key="%s"\n' % msg['key']
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        key = msg['key']
                        kvsname = msg['kvsname']
                        if KVSs.has_key(kvsname)  and  KVSs[kvsname].has_key(key):
                            value = KVSs[kvsname][key]
                            msgToSend = { 'cmd' : 'response_to_pmi_get', 'value' : value, 'to_rank' : msg['from_rank'] }
                            mpd_send_one_msg(rhsSocket,msgToSend)
                        else:
                            mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'pmi_getbyidx':
                    if msg['from_rank'] == myRank:
                        if pmiSocket:  # may have disappeared in early shutdown
                            KVSs[default_kvsname].update(msg['kvs'])
                            if KVSs[default_kvsname].keys():
                                key = KVSs[default_kvsname].keys()[0]
                                val = KVSs[default_kvsname][key]
                                pmiMsgToSend = 'cmd=getbyidx_results rc=0 nextidx=1 key=%s val=%s\n' % \
                                               (key,val)
                            else:
                                pmiMsgToSend = 'cmd=getbyidx_results rc=-2 reason=no_more_keyvals\n'
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        msg['kvs'].update(KVSs[default_kvsname])
                        mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'response_to_pmi_get':
                    if msg['to_rank'] == myRank:
                        if pmiSocket:  # may have disappeared in early shutdown
                            pmiMsgToSend = 'cmd=get_result rc=0 value=%s\n' % (msg['value'])
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'signal':
                    if msg['signo'] == 'SIGINT':
                        if not gdb:
                            jobEndingEarly = 1
                        for s in spawnedChildSockets:
                            mpd_send_one_msg(s,msg)
                        if myRank != 0:
                            if rhsSocket:  # still alive ?
                                mpd_send_one_msg(rhsSocket,msg)
                            if gdb:
                                kill(clientPid,SIGINT)
                            else:
                                try:
                                    pgrp = clientPid * (-1)   # neg Pid -> group
                                    kill(pgrp,SIGKILL)   # may be reaped by sighandler
                                except:
                                     pass
                    elif msg['signo'] == 'SIGKILL':
                        jobEndingEarly = 1
                        for s in spawnedChildSockets:
                            mpd_send_one_msg(s,msg)
                        if myRank != 0:
                            if rhsSocket:  # still alive ?
                                mpd_send_one_msg(rhsSocket,msg)
                            if gdb:
                                kill(clientPid,SIGUSR1)   # tell gdb driver to kill all
                            else:
                                try:
                                    pgrp = clientPid * (-1)   # neg Pid -> group
                                    kill(pgrp,SIGKILL)   # may be reaped by sighandler
                                except:
                                    pass
                    elif msg['signo'] == 'SIGTSTP':
                        if msg['dest'] != myId:
                            mpd_send_one_msg(rhsSocket,msg)
                            try:
                                pgrp = clientPid * (-1)   # neg Pid -> group
                                kill(pgrp,SIGTSTP)   # may be reaped by sighandler
                            except:
                                 pass
                    elif msg['signo'] == 'SIGCONT':
                        if msg['dest'] != myId:
                            mpd_send_one_msg(rhsSocket,msg)
                            try:
                                pgrp = clientPid * (-1)   # neg Pid -> group
                                kill(pgrp,SIGCONT)   # may be reaped by sighandler
                            except:
                                 pass
                elif msg['cmd'] == 'client_exit_status':
                    if myRank == 0:
                        if conSocket:
                            mpd_send_one_msg_noprint(conSocket,msg)
                    else:
                        if rhsSocket:
                            mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'collective_abort':
                    jobEndingEarly = 1
                    if msg['src'] != myId:
                        if rhsSocket:  # still alive ?
                            mpd_send_one_msg(rhsSocket,msg)
                    if conSocket:
                        msgToSend = { 'cmd' : 'job_aborted_early', 'jobid' : jobid,
                                      'rank' : msg['rank'], 
                                      'exit_status' : msg['exit_status'] }
                        mpd_send_one_msg_noprint(conSocket,msgToSend)
                    try:
                        pgrp = clientPid * (-1)   # neg Pid -> group
                        kill(pgrp,SIGKILL)   # may be reaped by sighandler
                    except:
                        pass
                elif msg['cmd'] == 'execution_problem':
                    jobEndingEarly = 1
                    if msg['src'] != myId:
                        if rhsSocket:  # still alive ?
                            mpd_send_one_msg(rhsSocket,msg)
                        if conSocket:
                            mpd_send_one_msg_noprint(conSocket,msg)
                    try:
                        pgrp = clientPid * (-1)   # neg Pid -> group
                        kill(pgrp,SIGKILL)   # may be reaped by sighandler
                    except:
                        pass
                elif msg['cmd'] == 'stdin_from_user':
                    if msg['src'] != myId:
                        mpd_send_one_msg(rhsSocket,msg)
                        if in_stdinRcvrs(myRank,stdinGoesToWho):
                            write(pipe_write_cli_stdin,msg['line'])
                elif msg['cmd'] == 'stdin_goes_to_who':
                    if msg['src'] != myId:
                        stdinGoesToWho = msg['stdin_procs']
                        mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'interrupt_peer_with_msg':    ## BNR
                    if int(msg['torank']) == myRank:
                        if pmiSocket:  # may have disappeared in early shutdown
                            pmiMsgToSend = '%s\n' % (msg['msg'])
                            mpd_send_one_line(pmiSocket,pmiMsgToSend)
                            select([],[],[],0.1)  # minor pause before intr
                            select([],[],[],0.1)
                            kill(clientPid,SIGUSR1)
                    else:
                        mpd_send_one_msg(rhsSocket,msg)
                else:
                    mpd_print(1, 'unexpected msg recvd on lhsSocket :%s:' % msg )
            elif readySocket == rhsSocket:
                msg = mpd_recv_one_msg(rhsSocket)
                mpd_print(0000, 'rhs died' )
                del socketsToSelect[rhsSocket]
                rhsSocket.close()
                rhsSocket = 0
            elif readySocket == clientStdoutFD:
                line = read(clientStdoutFD,1024)
                # line = clientStdoutFile.readline()
                if not line:
                    del socketsToSelect[clientStdoutFD]
                    close(clientStdoutFD)
                    numDone += 1
                    if numDone >= numWithIO:
                        if parentStdoutSocket:
                            parentStdoutSocket.close()
                            parentStdoutSocket = 0
                        if parentStderrSocket:
                            parentStderrSocket.close()
                            parentStderrSocket = 0
                else:
                    if parentStdoutSocket:
                        if lineLabels:
                            splitLine = line.split('\n',1024)
                            if startStdoutLineLabel:
                                line = myLineLabel
                            else:
                                line = ''
                            if splitLine[-1] == '':
                                startStdoutLineLabel = 1
                                del splitLine[-1]
                            else:
                                startStdoutLineLabel = 0
                            for s in splitLine[0:-1]:
                                line = line + s + '\n' + myLineLabel
                            line = line + splitLine[-1]
                            if startStdoutLineLabel:
                                line = line + '\n'
                        mpd_send_one_line_noprint(parentStdoutSocket,line)
                        # parentStdoutSocket.sendall('STDOUT by %d: |%s|' % (myRank,line) )
            elif readySocket == clientStderrFD:
                line = read(clientStderrFD,1024)
                # line = clientStderrFile.readline()
                if not line:
                    del socketsToSelect[clientStderrFD]
                    close(clientStderrFD)
                    numDone += 1
                    if numDone >= numWithIO:
                        if parentStdoutSocket:
                            parentStdoutSocket.close()
                            parentStdoutSocket = 0
                        if parentStderrSocket:
                            parentStderrSocket.close()
                            parentStderrSocket = 0
                else:
                    if parentStderrSocket:
                        if lineLabels:
                            splitLine = line.split('\n',1024)
                            if startStderrLineLabel:
                                line = myLineLabel
                            else:
                                line = ''
                            if splitLine[-1] == '':
                                startStderrLineLabel = 1
                                del splitLine[-1]
                            else:
                                startStderrLineLabel = 0
                            for s in splitLine[0:-1]:
                                line = line + s + '\n' + myLineLabel
                            line = line + splitLine[-1]
                            if startStderrLineLabel:
                                line = line + '\n'
                        mpd_send_one_line_noprint(parentStderrSocket,line)
            elif readySocket in childrenStdoutTreeSockets:
                line = readySocket.recv(1024)
                if not line:
                    del socketsToSelect[readySocket]
                    readySocket.close()
                    numDone += 1
                    if numDone >= numWithIO:
                        if parentStdoutSocket:
                            parentStdoutSocket.close()
                            parentStdoutSocket = 0
                        if parentStderrSocket:
                            parentStderrSocket.close()
                            parentStderrSocket = 0
                else:
                    if parentStdoutSocket:
                        mpd_send_one_line_noprint(parentStdoutSocket,line)
                        # parentStdoutSocket.sendall('FWD by %d: |%s|' % (myRank,line) )
            elif readySocket in childrenStderrTreeSockets:
                line = readySocket.recv(1024)
                if not line:
                    del socketsToSelect[readySocket]
                    readySocket.close()
                    numDone += 1
                    if numDone >= numWithIO:
                        if parentStdoutSocket:
                            parentStdoutSocket.close()
                            parentStdoutSocket = 0
                        if parentStderrSocket:
                            parentStderrSocket.close()
                            parentStderrSocket = 0
                else:
                    if parentStderrSocket:
                        mpd_send_one_line_noprint(parentStderrSocket,line)
                        # parentStdoutSocket.sendall('FWD by %d: |%s|' % (myRank,line) )
            elif readySocket in spawnedChildSockets:
                msg = mpd_recv_one_msg(readySocket)
                if not msg:
                    del socketsToSelect[readySocket]
                    readySocket.close()
                elif msg['cmd'] == 'job_started'  or  msg['cmd'] == 'job_terminated':
                    pass
                elif msg['cmd'] == 'client_exit_status':
                    if myRank == 0:
                        if conSocket:
                            mpd_send_one_msg_noprint(conSocket,msg)
                    else:
                        if rhsSocket:
                            mpd_send_one_msg(rhsSocket,msg)
                elif msg['cmd'] == 'job_aborted_early':
                    if conSocket:
                        msgToSend = { 'cmd' : 'job_aborted_early', 'jobid' : msg['jobid'],
                                      'rank' : msg['rank'], 
                                      'exit_status' : msg['exit_status'] }
                        mpd_send_one_msg_noprint(conSocket,msgToSend)
                else:
                    mpd_print(1, "unrecognized msg from spawned child :%s:" % msg )
            elif readySocket == pmiSocket:
                line = mpd_recv_one_line(pmiSocket)
                if not line:
                    del socketsToSelect[pmiSocket]
                    pmiSocket.close()
                    pmiSocket = 0
                    if pmiCollectiveJob:
                        if rhsSocket:  # still alive ?
                            if not jobEndingEarly:  # if I did not already know this
                                if not clientExited:
                                    clientExitStatus = 137  # assume kill -9 below
                                msgToSend = { 'cmd' : 'collective_abort',
                                              'src' : myId, 'rank' : myRank,
                                              'exit_status' : clientExitStatus }
                                mpd_send_one_msg(rhsSocket,msgToSend)
                        try:
                            pgrp = clientPid * (-1)   # neg Pid -> group
                            kill(pgrp,SIGKILL)   # may be reaped by sighandler
                        except:
                            pass
                    continue
                if line.startswith('mcmd='):
                    parsedMsg = {}
                    line = line.rstrip()
                    splitLine = line.split('=',1)
                    parsedMsg['cmd'] = splitLine[1]
                    line = ''
                    while not line.startswith('endcmd'):
                        line = mpd_recv_one_line(pmiSocket)
                        if not line.startswith('endcmd'):
                            line = line.rstrip()
                            splitLine = line.split('=',1)
                            parsedMsg[splitLine[0]] = splitLine[1]
                else:
                    parsedMsg = parse_pmi_msg(line)
                if not parsedMsg.has_key('cmd'):
                    mpd_print(1, "unrecognized pmi msg (no cmd) :%s:" % line )
                    continue
                # execution_problem is sent BEFORE client actually starts
                if parsedMsg['cmd'] == 'execution_problem':
                    msgToSend = { 'cmd' : 'execution_problem', 'src' : myId, 'jobid' : jobid,
                                  'rank' : myRank, 'exec' : clientPgm,
                                  'reason' : parsedMsg['reason']  }
                    mpd_send_one_msg(rhsSocket,msgToSend)
                    if conSocket:
                        mpd_send_one_msg_noprint(conSocket,msgToSend)
                elif parsedMsg['cmd'] == 'init':
                    pmiCollectiveJob = 1
                elif parsedMsg['cmd'] == 'get_my_kvsname':
                    pmiMsgToSend = 'cmd=my_kvsname kvsname=%s\n' % (default_kvsname)
                    mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'get_maxes':
                    pmiMsgToSend = 'cmd=maxes kvsname_max=4096 ' + \
                                   'keylen_max=4096 vallen_max=4096\n'
                    mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'get_universe_size':
                    pmiMsgToSend = 'cmd=universe_size size=%s\n' % (universeSize)
                    mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'create_kvs':
                    new_kvsname = kvsname_template + str(kvs_next_id)
                    KVSs[new_kvsname] = {}
                    kvs_next_id += 1
                    pmiMsgToSend = 'cmd=newkvs kvsname=%s\n' % (new_kvsname)
                    mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'destroy_kvs':
                    kvsname = parsedMsg['kvsname']
                    try:
                        del KVSs[kvsname]
                        pmiMsgToSend = 'cmd=kvs_destroyed rc=0\n'
                    except:
                        pmiMsgToSend = 'cmd=kvs_destroyed rc=-1\n'
                    mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'put':
                    kvsname = parsedMsg['kvsname']
                    key = parsedMsg['key']
                    value = parsedMsg['value']
                    try:
                        KVSs[kvsname][key] = value
                        pmiMsgToSend = 'cmd=put_result rc=0\n'
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    except Exception, errmsg:
                        pmiMsgToSend = 'cmd=put_result rc=-1 msg="%s"\n' % errmsg
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'barrier_in':
                    pmiBarrierInRecvd = 1
                    if myRank == 0  or  holdingPMIBarrierLoop1:
                        msgToSend = { 'cmd' : 'pmi_barrier_loop_1' }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                elif parsedMsg['cmd'] == 'get':
                    key = parsedMsg['key']
                    kvsname = parsedMsg['kvsname']
                    if KVSs.has_key(kvsname)  and  KVSs[kvsname].has_key(key):
                        value = KVSs[kvsname][key]
                        pmiMsgToSend = 'cmd=get_result rc=0 value=%s\n' % (value)
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        msgToSend = { 'cmd' : 'pmi_get', 'key' : key,
                                      'kvsname' : kvsname, 'from_rank' : myRank }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                elif parsedMsg['cmd'] == 'getbyidx':
                    kvsname = parsedMsg['kvsname']
                    idx = int(parsedMsg['idx'])
                    if idx == 0:
                        msgToSend = { 'cmd' : 'pmi_getbyidx', 'kvsname' : kvsname,
                                      'from_rank' : myRank, 'kvs' : KVSs[default_kvsname] }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                    else:
                        if len(KVSs[default_kvsname].keys()) > idx:
                            key = KVSs[default_kvsname].keys()[idx]
                            val = KVSs[default_kvsname][key]
                            nextidx = idx + 1
                            pmiMsgToSend = 'cmd=getbyidx_results rc=0 nextidx=%d key=%s val=%s\n' % \
                                           (nextidx,key,val)
                        else:
                            pmiMsgToSend = 'cmd=getbyidx_results rc=-2 reason=no_more_keyvals\n'
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'spawn':
                    ## This proc may produce stdout and stderr; do this early so I
                    ## won't exit before child sets up its conns with me.
                    ## NOTE: if you spawn a non-MPI job, it may not send these msgs
                    ## in which case adding 2 to numWithIO will cause the pgm to hang.
                    numWithIO += 2
                    nprocs  = int(parsedMsg['nprocs'])
                    pmiInfo = {}
                    for i in range(0,int(parsedMsg['info_num'])):
                        info_key = parsedMsg['info_key_%d' % i]
                        info_val = parsedMsg['info_val_%d' % i]
                        pmiInfo[info_key] = info_val
                    if pmiInfo.has_key('host'):
                        hosts = { (0,nprocs-1) : pmiInfo['host'] }
                    else:
                        hosts   = { (0,nprocs-1) : '_any_' }
                    execs   = { (0,nprocs-1) : parsedMsg['execname'] }
                    users   = { (0,nprocs-1) : mpd_get_my_username() }
                    cwds    = { (0,nprocs-1) : environ['MPDMAN_CWD'] }
                    paths   = { (0,nprocs-1) : '' }

		    spawnEnv = {}
		    spawnEnv.update(environ)
		    spawnEnv['MPI_APPNUM'] = '736'    # dummy for now
                    envvars = { (0,nprocs-1) : spawnEnv }

                    limits  = { (0,nprocs-1) : {} }
                    ##### args    = { (0,nprocs-1) : [ parsedMsg['args'] ] }
                    ##### args    = { (0,nprocs-1) : [ 'AA', 'BB', 'CC' ] }
                    cliArgs = []
                    cliArgcnt = int(parsedMsg['argcnt'])
                    for i in range(1,cliArgcnt+1):    # start at 1
                        cliArgs.append(parsedMsg['arg%d' % i])
                    args = { (0,nprocs-1) : cliArgs }
                    spawnedCnt += 1    # non-zero to use in msg below
                    msgToSend = { 'cmd' : 'spawn',
                                  'conhost'  : gethostname(),
                                  'conport'  : myPort,
                                  'spawned'  : spawnedCnt,
                                  'nstarted' : 0,
                                  'nprocs'   : nprocs,
                                  'hosts'    : hosts,
                                  'execs'    : execs,
                                  'users'    : users,
                                  'cwds'     : cwds,
                                  'paths'    : paths,
                                  'args'     : args,
                                  'envvars'  : envvars,
                                  'limits'   : limits
                                }
                    mpd_send_one_msg(mpdSocket,msgToSend)
                    # I could send the preput_info along but will keep it here
                    # and let the spawnee call me up and ask for it; he will
                    # call me anyway since I am his parent in the tree.  So, I
                    # will create a KVS to hold the info until he calls
                    spawnedKVSname = 'mpdman_kvs_for_spawned_' + str(spawnedCnt)
                    KVSs[spawnedKVSname] = {}
                    preput_num = int(parsedMsg['preput_num'])
                    for i in range(0,preput_num):
                        preput_key = parsedMsg['preput_key_%d' % i]
                        preput_val = parsedMsg['preput_val_%d' % i]
                        KVSs[spawnedKVSname][preput_key] = preput_val
                elif parsedMsg['cmd'] == 'finalize':
                    pmiCollectiveJob = 0
                    # the following lines are present to support a process that runs
                    # 2 MPI pgms in tandem (e.g. mpish at ANL)
                    KVSs = {}
                    KVSs[default_kvsname] = {}
                    kvs_next_id = 1
                    jobEndingEarly = 0
                    pmiCollectiveJob = 0
                    spawnedCnt = 0
                    pmiMsgToSend = 'cmd=finalize_ack\n'
                    mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'client_bnr_fence_in':    ## BNR
                    pmiBarrierInRecvd = 1
                    if myRank == 0  or  holdingPMIBarrierLoop1:
                        msgToSend = { 'cmd' : 'pmi_barrier_loop_1' }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                elif parsedMsg['cmd'] == 'client_bnr_put':         ## BNR
                    key = parsedMsg['attr']
                    value = parsedMsg['val']
                    try:
                        KVSs[default_kvsname][key] = value
                        pmiMsgToSend = 'cmd=put_result rc=0\n'
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    except Exception, errmsg:
                        pmiMsgToSend = 'cmd=put_result rc=-1 msg="%s"\n' % errmsg
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                elif parsedMsg['cmd'] == 'client_bnr_get':          ## BNR
                    key = parsedMsg['attr']
                    if KVSs[default_kvsname].has_key(key):
                        value = KVSs[default_kvsname][key]
                        pmiMsgToSend = 'cmd=client_bnr_get_output rc=0 val=%s\n' % (value)
                        mpd_send_one_line(pmiSocket,pmiMsgToSend)
                    else:
                        msgToSend = { 'cmd' : 'bnr_get', 'key' : key,
                                      'kvsname' : kvsname, 'from_rank' : myRank }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                elif parsedMsg['cmd'] == 'client_ready':               ## BNR
                    ## continue to wait for accepting_signals
                    pass
                elif parsedMsg['cmd'] == 'accepting_signals':          ## BNR
                    ## handle it like a barrier_in ??
                    pmiBarrierInRecvd = 1
                    doingBNR = 1    ## BNR
                elif parsedMsg['cmd'] == 'interrupt_peer_with_msg':    ## BNR
                    mpd_send_one_msg(rhsSocket,parsedMsg)
                else:
                    mpd_print(1, "unrecognized pmi msg :%s:" % line )
            elif readySocket == conSocket:
                msg = mpd_recv_one_msg(conSocket)
                if not msg:
                    if conSocket:
                        del socketsToSelect[conSocket]
                        conSocket.close()
                        conSocket = 0
                    if parentStdoutSocket:
                        parentStdoutSocket.close()
                        parentStdoutSocket = 0
                    if parentStderrSocket:
                        parentStderrSocket.close()
                        parentStderrSocket = 0
                    if rhsSocket:
                        msgToSend = { 'cmd' : 'signal', 'signo' : 'SIGKILL' }
                        mpd_send_one_msg(rhsSocket,msgToSend)
                    try:
                        pgrp = clientPid * (-1)   # neg Pid -> group
                        kill(pgrp,SIGKILL)   # may be reaped by sighandler
                    except:
                        pass
                elif msg['cmd'] == 'signal':
                    if msg['signo'] == 'SIGINT':
                        mpd_send_one_msg(rhsSocket,msg)
                        for s in spawnedChildSockets:
                            mpd_send_one_msg(s,msg)
                        if gdb:
                            kill(clientPid,SIGINT)
                        else:
                            try:
                                pgrp = clientPid * (-1)   # neg Pid -> group
                                kill(pgrp,SIGKILL)   # may be reaped by sighandler
                            except:
                                pass
                    elif msg['signo'] == 'SIGKILL':
                        mpd_send_one_msg(rhsSocket,msg)
                        for s in spawnedChildSockets:
                            mpd_send_one_msg(s,msg)
                        if gdb:
                            kill(clientPid,SIGUSR1)    # tell gdb driver to kill all
                        else:
                            try:
                                pgrp = clientPid * (-1)   # neg Pid -> group
                                kill(pgrp,SIGKILL)   # may be reaped by sighandler
                            except:
                                pass
                    elif msg['signo'] == 'SIGTSTP':
                        msg['dest'] = myId
                        mpd_send_one_msg(rhsSocket,msg)
                        try:
                            pgrp = clientPid * (-1)   # neg Pid -> group
                            kill(pgrp,SIGTSTP)   # may be reaped by sighandler
                        except:
                            pass
                    elif msg['signo'] == 'SIGCONT':
                        msg['dest'] = myId
                        mpd_send_one_msg(rhsSocket,msg)
                        try:
                            pgrp = clientPid * (-1)   # neg Pid -> group
                            kill(pgrp,SIGCONT)   # may be reaped by sighandler
                        except:
                            pass
                elif msg['cmd'] == 'stdin_from_user':
                    msg['src'] = myId
                    mpd_send_one_msg(rhsSocket,msg)
                    if in_stdinRcvrs(myRank,stdinGoesToWho):
                        try:
                            write(pipe_write_cli_stdin,msg['line'])
                        except:
                            mpd_print(1, 'cannot send stdin to client')
                elif msg['cmd'] == 'stdin_goes_to_who':
                    stdinGoesToWho = msg['stdin_procs']
                    msg['src'] = myId
                    mpd_send_one_msg(rhsSocket,msg)
                else:
                    mpd_print(1, 'unexpected msg recvd on conSocket :%s:' % msg )
            elif readySocket == mpdSocket:
                msg = mpd_recv_one_msg(mpdSocket)
                mpd_print(0000, 'msg recvd on mpdSocket :%s:' % msg )
                if not msg:
                    if conSocket:
                        msgToSend = { 'cmd' : 'job_aborted', 'reason' : 'mpd disappeared',
                                      'jobid' : jobid }
                        mpd_send_one_msg_noprint(conSocket,msgToSend)
                        del socketsToSelect[conSocket]
                        conSocket.close()
                        conSocket = 0
                    try:
                        kill(0,SIGKILL)  # pid 0 -> all in my process group
                    except:
                        pass
                    exit(0)
                if msg['cmd'] == 'signal_to_handle'  and  msg.has_key('sigtype'):
                    if msg['sigtype'].isdigit():
                        signum = int(msg['sigtype'])
                    else:
                        import signal as tmpimp  # just to get valid SIG's
                        exec('signum = %s' % 'tmpimp.SIG' + msg['sigtype'])
                    try:    
                        if msg['s_or_g'] == 's':    # single (not entire group)
                            pgrp = clientPid          # just client process
                        else:
                            pgrp = clientPid * (-1)   # neg Pid -> process group
                        kill(pgrp,signum)
                    except Exception, errmsg:
                        mpd_print(1, 'invalid signal (%d) from mpd' % (signum) )
                else:
                    mpd_print(1, 'invalid msg recvd on mpdSocket :%s:' % msg )
            elif readySocket == pmiListenSocket:
                (pmiSocket,tempConnAddr) = pmiListenSocket.accept()
                # the following lines are commented out so that we can support a process
                # that runs 2 MPI pgms in tandem  (e.g. mpish at ANL)
                ##### del socketsToSelect[pmiListenSocket]
                ##### pmiListenSocket.close()
                socketsToSelect[pmiSocket] = 1
            else:
                msg = mpd_recv_one_msg(readySocket)
                mpd_print(1, 'recvd msg :%s: on unknown socket :%s:' % (msg,readySocket) )
                del socketsToSelect[readySocket]
    mpd_print(0000, "out of loop")
    # may want to wait for waitPids here

def in_stdinRcvrs(myRank,stdinGoesToWho):
    s1 = stdinGoesToWho.split(',')
    for s in s1:
        s2 = s.split('-')
        if len(s2) == 1:
            if myRank == int(s2[0]):
                return 1
        else:
            if myRank >= int(s2[0])  and  myRank <= int(s2[1]):
                return 1
    return 0
        

def parse_pmi_msg(msg):
    parsed_msg = {}
    try:
        sm = findall(r'\S+',msg)
        for e in sm:
            se = e.split('=')
            parsed_msg[se[0]] = se[1]
    except:
        print 'unable to parse pmi msg :%s:' % msg
    return parsed_msg

def set_limits(limits):
    for type in limits.keys():
        limit = int(limits[type])
        try:
            if   type == 'core':
                from resource import RLIMIT_CORE
                setrlimit(RLIMIT_CORE,(limit,limit))
            elif type == 'cpu':
                from resource import RLIMIT_CPU
                setrlimit(RLIMIT_CPU,(limit,limit))
            elif type == 'fsize':
                from resource import RLIMIT_FSIZE
                setrlimit(RLIMIT_FSIZE,(limit,limit))
            elif type == 'data':
                from resource import RLIMIT_DATA
                setrlimit(RLIMIT_DATA,(limit,limit))
            elif type == 'stack':
                from resource import RLIMIT_STACK
                setrlimit(RLIMIT_STACK,(limit,limit))
            elif type == 'rss':
                from resource import RLIMIT_RSS
                setrlimit(RLIMIT_RSS,(limit,limit))
            elif type == 'nproc':
                from resource import RLIMIT_NPROC
                setrlimit(RLIMIT_NPROC,(limit,limit))
            elif type == 'nofile':
                from resource import RLIMIT_NOFILE
                setrlimit(RLIMIT_NOFILE,(limit,limit))
            elif type == 'ofile':
                from resource import RLIMIT_OFILE
                setrlimit(RLIMIT_OFILE,(limit,limit))
            elif type == 'memloc':
                from resource import RLIMIT_MEMLOCK
                setrlimit(RLIMIT_MEMLOCK,(limit,limit))
            elif  type == 'as':
                from resource import RLIMIT_AS
                setrlimit(RLIMIT_AS,(limit,limit))
            elif  type == 'vmem':
                from resource import RLIMIT_VMEM
                setrlimit(RLIMIT_VMEM,(limit,limit))
            else:
                raise NameError, 'invalid resource name: %s' % type  # validated at mpdrun
        except (NameError,ImportError), errmsg:
            return errmsg
    return 0

def sigchld_handler(signum,frame):
    global clientPid, clientExited, clientExitStatus, clientExitStatusSent
    done = 0
    while not done:
        try:
            (pid,status) = waitpid(-1,WNOHANG)
            if pid == 0:    # no existing child process is finished
                done = 1
            if pid == clientPid:
                clientExited = 1
                clientExitStatus = status
        except:
            done = 1


if __name__ == '__main__':
    if not environ.has_key('MPDMAN_CLI_PGM'):    # assume invoked from keyboard
        print 'mpdman for mpd version: %s' % str(mpd_version)
        print 'mpdman does NOT run as a console program; should be execd by mpd'
        exit(-1)
    try:
        mpdman()
    except mpdError, errmsg:
        print 'mpdman failed; cause: %s' % (errmsg)  ##
        pass
