#!/usr/bin/python -Ot

import sys, os ,signal,pty

def main():
    """ A demo daemon main routine, write a datestamp to 
        /tmp/daemon-log every 10 seconds.
    """
    import time

    while 1: 
        print('%s\n' % time.ctime(time.time())) 
        time.sleep(10) 


if __name__ == "__main__":
    # do the UNIX double-fork magic, see Stevens' "Advanced 
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    new_f=open("/tmp/handle","a",0)
    # Ignore a terminal output signal
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    # Ignore a terminal input signal
    signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    # Ignore a terminal stop signal
    signal.signal(signal.SIGTSTP, signal.SIG_IGN)
    pid = os.fork() 
    if pid > 0:
      # exit first parent
      sys.exit(0) 
    # decouple from parent environment
    os.setpgrp()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    #os.setsid() 

    # do second fork
    pid,fd = pty.fork() 
    if pid > 0:
      # exit from second parent, print eventual PID before
      print "Daemon PID %d" % pid 
      sys.exit(0) 

    sys.__stdin__.close()
    sys.stdin.close()
    sys.stdout.close()
    sys.stdout=new_f
    sys.stderr.close()
    sys.stderr=new_f
    os.umask(000)
    print sys.stdin,sys.stdout,sys.stderr
    # Ignore a dead of child signal
    signal.signal(signal.SIGCLD, signal.SIG_IGN)
    # Install a hander for ther terminate signal
    #signal.signal(signal.SIGTERM, terminate)
    # Install a handler for the interrupt signal
    #signal.signal(signal.SIGINT, terminate)
    # Install a handler for the quit signal
    #signal.signal(signal.SIGQUIT, terminate)
    
    os.chdir("/") 
    os.umask(0) 
    # start the daemon main loop
    main() 

