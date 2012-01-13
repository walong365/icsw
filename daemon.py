#!/usr/bin/env python2.2
def daemonize():
	"""Become a Linux/UNIX daemon"""
	import os,sys
	os.chdir('/')
	if os.fork(): os._exit(0)
	os.setsid()
	sys.stdin  = sys.__stdin__  = open('/dev/null','r')
	sys.stdout = sys.__stdout__ = open('/dev/null','w')
	sys.stdout = sys.__stderr__ = os.dup(sys.stdout.fileno())
	if os.fork(): os._exit(0)

def daemonize_log_demo():
	"""Demonstrate deamonize() with trivial syslog output""" 
	import time,syslog,os
	log = syslog.openlog("JimDaemon[%d]" % os.getpid())
	t=0
	while 1:
		t+=1
		syslog.syslog(syslog.LOG_INFO,"Interval %d  reached" % (t) )
		time.sleep(5)

if __name__=='__main__':
	daemonize()
	daemonize_log_demo()

