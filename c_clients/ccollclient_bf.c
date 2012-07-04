#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <syslog.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/ipc.h>
#include <sys/msg.h>
#include <getopt.h>

#define STATE_OK 0
#define STATE_WARNING 1
#define STATE_CRITICAL 2
#define STR_LEN 64
#define EBUFF_LEN 256
#define OUTBUFF_LEN 65536

struct py_str {
  long int len;
  char string[STR_LEN];
};

struct my_msg {
  long int type,pid,port,cont;
  struct py_str host,command;
};

struct my_cnt {
  long int type,cont;
  struct py_str command;
};

char ebuff[EBUFF_LEN];
int err_exit(int verbose,char* str,int how) {
  char errstr[EBUFF_LEN];
  if (how) {
    sprintf (errstr,"An error occured for %s: %s\n",str,strerror(errno));
  } else {
    sprintf (errstr,"An error occured: %s\n",str);
  }

  if (verbose)
    printf(errstr);
  //syslog (LOG_DAEMON|LOG_ERR,ebuff);
  syslog (LOG_DAEMON|LOG_ERR,errstr);

  return STATE_CRITICAL;
}

struct my_msg *mbuf;
int timeout;

void mysigh(int dummy) {
  syslog(LOG_DAEMON|LOG_ERR,"on host %s : Timeout after %d secs while waiting for answer for '%s'",(char*)mbuf->host.string,timeout,(char*)mbuf->command.string);
  fprintf (stdout,"Timeout after %d secs while waiting for answer for '%s'\n",timeout,(char*)mbuf->command.string);
  return;// STATE_CRITICAL;
  //err_exit(0,ebuff,0);
}

int main (int argc,char** argv) {
  int retcode,ret,idx,msgid,rchar,ipcnum,relay_id,ret_len,num_cont;
  int verbose=0;/*first;*/
  char outbuff[OUTBUFF_LEN];
  struct my_cnt *cbuf;
  struct itimerval mytimer;
  struct sigaction *alrmsigact;

  retcode=STATE_OK;
  
  
  mbuf=(struct my_msg*)malloc(sizeof(struct my_msg));
  if (!mbuf) exit(ENOMEM);
  cbuf=(struct my_cnt*)malloc(sizeof(struct my_cnt));
  if (!cbuf) exit(ENOMEM);
  alrmsigact=(struct sigaction*)malloc(sizeof(struct sigaction));
  if (!alrmsigact) exit(ENOMEM);
  sprintf((char*)mbuf->host.string,"localhost");
//huh?  sprintf((char*)mbuf->command.string,"");
  memset(mbuf->command.string,0,STR_LEN);
  mbuf->port=2001;
  ipcnum=0;
  timeout=6;
  while (1) {
    rchar=getopt(argc,argv,"+vm:p:n:ht:");
    //printf("%d %c\n",rchar,rchar);
    switch (rchar) {
    case 'p':
      mbuf->port=(int)strtol(optarg,NULL,10);
      break;
    case 'm':
      strncpy((char*)mbuf->host.string,optarg,STR_LEN-1);
      mbuf->host.string[STR_LEN]='\0';
      break;
    case 't':
      timeout=strtol(optarg,NULL,10);
      break;
    case 'v':
      verbose=1;
      break;
    case 'n':
      ipcnum=strtol(optarg,NULL,10);
      break;
    case 'h':
    case '?':
      printf("Usage: ccollclient [-t TIMEOUT] [-m HOST] [-p PORT] [-n IPC_key] [-h] [-v] command\n");
      exit(-1);
      break;
    }
    if (rchar < 0) break;
  }

  if (mbuf->port < 0) { errno=EINVAL; err_exit(1,"port",1); }
  if (timeout < 0) { errno=EINVAL; err_exit(1,"timeout",1); timeout=0;}
  if (ipcnum == 0) {
    if ((relay_id=open("/var/run/relay_key.ipc",O_RDONLY)) < 0) {
      retcode=err_exit(1,"open /var/run/relay_key.ipc",1);
    } else {
      ret=read(relay_id,(char*)outbuff,10);
      ipcnum=strtol(outbuff,NULL,10);
      close(relay_id);
    }
  }
  if (retcode == STATE_OK) {
    for (idx=optind;idx<argc;idx++) {
      sprintf((char*)mbuf->command.string,"%s%s ",(char*)mbuf->command.string,argv[idx]);
      mbuf->command.string[STR_LEN]='\0';
    }
    sprintf(ebuff,"Timeout %s ",(char*)mbuf->host.string);
    sprintf(ebuff,"%s%s ",ebuff,(char*)mbuf->command.string);
    mbuf->pid=getpid();
    msgid=msgget((key_t) ipcnum,0);
    if (verbose) {
      printf("timeout: %d, DestinationHost: '%s', Port: %d, Arguments: '%s'\n",
	     (int)timeout,(char*)mbuf->host.string,(int)mbuf->port,(char*)mbuf->command.string);
      printf("pid: %d, MessageID: %d\n",(int)mbuf->pid,msgid);
    }
    //syslog (LOG_DAEMON|LOG_ERR,"%d %s %d %s",getpid(),(char*)mbuf->host.string,mbuf->port,(char*)mbuf->command.string);
    if (msgid < 0) {
      if (verbose) {
	retcode=err_exit(1,"No IPC-Messagequeue found",0);
      }
    } else {
      // fill ipc-buffer
      mbuf->type=1;
      mbuf->host.len=(long int)strlen((char*)mbuf->host.string);
      mbuf->command.len=(long int)strlen((char*)mbuf->command.string);
      mbuf->cont=0;
      // send buffer
      ret=msgsnd(msgid,mbuf,sizeof(struct my_msg)-sizeof(long int),IPC_NOWAIT);
      if (ret) {
	retcode=err_exit(1,"msgsnd()",1);
      } else {
	/* syslog(LOG_DAEMON|LOG_INFO,"put 1 message"); */
	alrmsigact->sa_handler=&mysigh;
	if ((ret=sigaction(SIGALRM,(struct sigaction*)alrmsigact,NULL))==-1) {
	  retcode=err_exit(1,"sigaction",1);
	} else {
	  getitimer(ITIMER_REAL,&mytimer);
	  mytimer.it_value.tv_sec=timeout;
	  mytimer.it_value.tv_usec=0;
	  setitimer(ITIMER_REAL,&mytimer,NULL);
	  ret=msgrcv(msgid,mbuf,sizeof(struct my_msg)-sizeof(long int),getpid(),0);
	  if (ret < 0) {
	    retcode=STATE_CRITICAL;
	  } else {
	    ret_len=ret;
	    num_cont=0;
	    strncpy((char*)outbuff,(char*)mbuf->command.string,STR_LEN);
	    retcode=mbuf->host.len;
	    while (mbuf->cont) {
	      num_cont++;
	      ret=msgrcv(msgid,mbuf,sizeof(struct my_msg)-sizeof(long int),getpid(),0);
	      ret_len+=ret;
	      sprintf((char*)outbuff,"%s%s",(char*)outbuff,(char*)mbuf->command.string);
	    }
	    if (verbose) {
	      printf("Got %d bytes (%d continuations)\n",ret_len,num_cont);
	    }
	    printf ("%s\n",outbuff);
	  }
	}
      }
    }
  }
  exit(retcode);
}
