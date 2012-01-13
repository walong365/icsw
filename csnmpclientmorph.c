/*
  Copyright (C) 2009 Andreas Lang, init.at
  
  Send feedback to: <lang@init.at>
  
  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License Version 2 as
  published by the Free Software Foundation.
  
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/

#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <syslog.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/ipc.h>
#include <sys/msg.h>
#include <getopt.h>

#define STATE_OK 0
#define STATE_WARNING 1
#define STATE_CRITICAL 2
#define STR_LEN 256

#define ERRSTR_SIZE 512

struct my_msg {
    long type;
    int pid, snmp_version, host_len, command_len, snmp_community_len;
    char strings[0];
};

struct msg_return {
    long type;
    int ret_state, cont_flag, return_len;
    char strings[0];
};


char ebuff[ERRSTR_SIZE];
int err_exit(const int errnum, int verbose, char* str, int how) {
    char* errstr;
    errstr = (char*)malloc(ERRSTR_SIZE);
    if (how) {
	sprintf (errstr, "An error occured for %s: %s\n", str, strerror(errnum));
    } else {
	sprintf (errstr, "An error occured: %s\n", str);
    }
    //if (verbose)
    //syslog (LOG_DAEMON | LOG_ERR, ebuff);
    //syslog (LOG_DAEMON | LOG_ERR, errstr);
    fprintf (stdout, errstr);
    free(errstr);
    return STATE_CRITICAL;
    
}

int timeout;
char *act_hostname, *act_command, *snmp_community;

void my_alarm_handler(int si) {
    //syslog(LOG_DAEMON | LOG_ERR, "on host %s : Timeout after %d secs while waiting for answer for '%s'", act_hostname, timeout, act_command);
    fprintf (stdout, "Timeout after %d secs while waiting for answer for '%s' (host %s)\n", timeout, act_command, act_hostname);
    exit(STATE_CRITICAL);
}

void my_term_handler(int si) {
    //syslog(LOG_DAEMON | LOG_ERR, "on host %s : terminated while waiting for answer for '%s'", act_hostname, act_command);
    fprintf (stdout, "terminated\n");
    exit(STATE_CRITICAL);
}

void my_int_handler(int si) {
    //syslog(LOG_DAEMON | LOG_ERR, "on host %s : interrupted while waiting for answer for '%s'", act_hostname, act_command);
    fprintf (stdout, "interrupted\n");
    exit(STATE_CRITICAL);
}

int main (int argc, char** argv) {
    int retcode, ret, idx, msgid, rchar, ipcnum, relay_id, ret_len, num_cont;
    int verbose = 0, first;
    struct my_msg *mbuf;
    struct msg_return *mret;
    char outbuff[65536];
    struct itimerval mytimer;
    struct sigaction *alrmsigact, *termsigact, *intsigact;
    
    retcode = STATE_OK;
    
    mbuf = (struct my_msg*)malloc(20000);
    mret = (struct msg_return*)malloc(20000);
    alrmsigact = (struct sigaction*)malloc(sizeof(struct sigaction));
    termsigact = (struct sigaction*)malloc(sizeof(struct sigaction));
    intsigact = (struct sigaction*)malloc(sizeof(struct sigaction));
    act_hostname = (char*)malloc(2000);
    act_command = (char*)malloc(2000);
    snmp_community = (char*)malloc(2000);
    strcpy(act_hostname  , "localhost");
    strcpy(act_command   , argv[0]);
    strcpy(snmp_community, "public"   );
    //sprintf((char*)mbuff->strings, "localhostversion")
    mbuf->snmp_version = 2;
    ipcnum = 0;
    timeout = 30;
    while (1) {
	rchar = getopt(argc, argv, "+vH:n:ht:P:C:k:z:");
	//printf("%d %c\n", rchar, rchar);
	switch (rchar) {
	    case 'H':
		strcpy(act_hostname, optarg);
		break;
	    case 'C':
		strcpy(snmp_community, optarg);
		break;
	    case 't':
		timeout = strtol(optarg, NULL, 10);
		break;
	    case 'V':
		mbuf->snmp_version = strtol(optarg, NULL, 10);
		break;
	    case 'v':
		verbose = 1;
		break;
	    case 'n':
		ipcnum = strtol(optarg, NULL, 10);
		break;
	    case 'k':
		sprintf((char*)act_command, "%s -k %s", (char*)act_command, optarg);
		break;
	    case 'z':
		sprintf((char*)act_command, "%s -z %s", (char*)act_command, optarg);
		break;
	    case 'h':
	    case '?':
		printf("Usage: csnmpclient2 [-t TIMEOUT] [-H HOST] [-C COMMUNITY] [-P version] [-n IPC_key] [-h] [-v] [-k|-z PASSTHROUGH] command\n");
		exit(-1);
		break;
	}
	if (rchar == -1) break;
    }
    if (ipcnum == 0) {
	if ((relay_id = open("/var/run/snmp_relay_key.ipc", O_RDONLY)) == -1) {
	    retcode = err_exit(errno, 1, "open /var/run/snmp_relay_key.ipc", 1);
	} else {
	    ret = read(relay_id, (char*)outbuff, 10);
	    ipcnum = strtol(outbuff, NULL, 10);
	    close(relay_id);
	}
    }
    if (retcode == STATE_OK) {
	for (idx = optind; idx < argc; idx++) {
	    if (idx == optind) {
		sprintf((char*)act_command, "%s", argv[idx]);
	    } else {
		sprintf((char*)act_command, "%s %s", (char*)act_command, argv[idx]);
	    }
	}
	//sprintf(ebuff, "Timeout %s ", (char*)mbuf->host.string);
	//sprintf(ebuff, "%s%s ", ebuff, (char*)mbuf->command.string);
	mbuf->pid = getpid();
	msgid = msgget((key_t) ipcnum, 0);
	if (verbose) {
	    printf("timeout: %d,  host: '%s',  community '%s', version %d, arguments: '%s'\n", 
		   (int)timeout, (char*)act_hostname, (char*)snmp_community, mbuf->snmp_version, act_command);
	    printf("pid: %d,  MessageID: %d\n", mbuf->pid, msgid);
	}
	//syslog (LOG_DAEMON | LOG_ERR, "%d %s %d %s", getpid(), (char*)mbuf->host.string, mbuf->port, (char*)mbuf->command.string);
	if (msgid < 0) {
	    if (verbose) {
		retcode = err_exit(errno, 1, "No IPC-Messagequeue found", 0);
	    }
	} else {
	    // fill ipc-buffer
	    mbuf->type = 1;
	    mbuf->host_len           = (int)strlen((char*)act_hostname  );
	    mbuf->command_len        = (int)strlen((char*)act_command   );
	    mbuf->snmp_community_len = (int)strlen((char*)snmp_community);
	    sprintf((char*)mbuf->strings, "%s%s%s", act_hostname, act_command, snmp_community);
	    // send buffer
	    ret = msgsnd(msgid, mbuf, sizeof(struct my_msg) + strlen((char*)mbuf->strings), IPC_NOWAIT);
	    if (ret) {
		retcode = err_exit(errno, 1, "sending message", 1);
	    } else {
		/* syslog(LOG_DAEMON | LOG_INFO, "put 1 message"); */
		alrmsigact->sa_handler = &my_alarm_handler;
		termsigact->sa_handler = &my_term_handler;
		intsigact->sa_handler  = &my_int_handler;
		if ((ret = sigaction(SIGALRM, (struct sigaction*)alrmsigact, NULL)) == -1) {
		    retcode = err_exit(errno, 1, "sig_alarm_action", 1);
		} else if ((ret = sigaction(SIGTERM, (struct sigaction*)termsigact, NULL)) == -1) {
		    retcode = err_exit(errno, 1, "sig_term_action", 1);
		} else if ((ret = sigaction(SIGINT, (struct sigaction*)intsigact, NULL)) == -1) {
		    retcode = err_exit(errno, 1, "sig_term_action", 1);
		} else {
		    getitimer(ITIMER_REAL, &mytimer);
		    mytimer.it_value.tv_sec  = timeout;
		    mytimer.it_value.tv_usec = 0;
		    setitimer(ITIMER_REAL, &mytimer, NULL);
		    ret = msgrcv(msgid, mret, sizeof(struct msg_return) + STR_LEN, getpid(), 0);
		    if (ret == -1) {
			retcode = STATE_CRITICAL;
		    } else {
			ret_len = ret;
			num_cont = 0;
			mret->strings[mret->return_len] = 0;
			//printf("%d %d %s\n", msgid, mret->command_len, outbuff);
			strcpy((char*)outbuff, (char*)mret->strings);
			retcode = mret->ret_state;
			while (mret->cont_flag) {
			    num_cont++;
			    ret = msgrcv(msgid, mret, sizeof(struct msg_return) + STR_LEN, getpid(), 0);
			    mret->strings[mret->return_len] = 0;
			    ret_len += ret;
			    if (strlen(outbuff) > 60000) {
				printf("%s", outbuff);
				outbuff[0] = 0;
			    }
			    sprintf((char*)outbuff, "%s%s", (char*)outbuff, (char*)mret->strings);
			}
			printf ("%s\n", outbuff);
			if (verbose) {
			    printf("Got %d bytes (%d continuations), return code is %d\n", ret_len, num_cont, retcode);
			}
		    }
		}
	    }
	}
    }
    exit(retcode);
}
