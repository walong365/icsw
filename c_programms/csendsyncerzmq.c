/*
    Copyright (C) 2013-2014 Andreas Lang-Nevyjel, init.at

    Send feedback to: <lang-nevyjel@init.at>

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License Version 3 as
    published by the Free Software Foundation.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/

#include <zmq.h>
#include <stdio.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <signal.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <sys/utsname.h>
#include <linux/unistd.h>
#include <linux/kernel.h>
#include <syslog.h>
#include <unistd.h>
#include <stdlib.h>
#include <libgen.h>
#include <netdb.h>

#ifndef O_NOFOLLOW
#define O_NOFOLLOW	0400000
#endif

#define STATE_OK 0
#define STATE_WARNING 1
#define STATE_CRITICAL 2
#define SERVICE_NAME "md-sync-server"

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define IOBUFF_SIZE 16384
#define SENDBUFF_SIZE 16384

#include "parse_uuid.c"

int err_message(char *str)
{
    char *errstr;
    errstr = (char *)malloc(ERRSTR_SIZE);
    if (!errstr)
        return -ENOMEM;
    if (errno) {
        sprintf(errstr, "An error occured (%d) : %s (%d) %s\n", getpid(), str,
                errno, strerror(errno));
    } else {
        sprintf(errstr, "An error occured (%d) : %s\n", getpid(), str);
    }
    syslog(LOG_DAEMON | LOG_ERR, errstr);
    fprintf(stderr, errstr);
    free(errstr);
    return 0;
}

int err_exit(char *str)
{
    if ((err_message(str)) < 0)
        exit(ENOMEM);
    exit(STATE_CRITICAL);
}

void mysigh(int dummy)
{
    err_exit("Timeout while waiting for answer");
    //err_exit(0, ebuff, 0);
}

int main(int argc, char **argv)
{
    int ret, num, inlen, file, i /*, time */ , port, rchar, verbose, quiet,
        retcode, timeout, file_size;
    struct in_addr sia;
    struct hostent *h;
    struct stat st;
    char *iobuff, *filebuff, *act_pos, *act_source, *act_bp,
        *dest_host, *uuid_buffer, *send_buffer;
    struct itimerval mytimer;
    struct sigaction *alrmsigact;
    struct utsname myuts;
    int colons_passed = 0;
    int sendbuff_size = 1024;

    retcode = STATE_CRITICAL;

    timeout = 10;
    verbose = 0;
    quiet = 0;
    h = NULL;
    send_buffer = (char *)malloc(SENDBUFF_SIZE);
    send_buffer[0] = 0;
    dest_host = (char *)malloc(HOSTB_SIZE);
    dest_host[0] = 0;
    // get uts struct
    uname(&myuts);
    sprintf(dest_host, "localhost");
    while (1) {
        rchar = getopt(argc, argv, "+vht:q");
        //printf("%d %c\n", rchar, rchar);
        switch (rchar) {
        case 't':
            timeout = strtol(optarg, NULL, 10);
            break;
        case 'v':
            verbose = 1;
            break;
        case 'q':
            quiet = 1;
            break;
        case 'h':
        case '?':
            printf
                ("Usage: %s [-t TIMEOUT] [-p PORT] [-h] [-v] [-q] filename\n",
                 basename(argv[0]));
            printf("  defaults: port=%d, timeout=%d\n", port,
                   timeout, dest_host);
            exit(STATE_CRITICAL);
            break;
        }
        if (rchar < 0)
            break;
    }
    // generate connection string
/*  errno = 0;*/
    //if (!h) err_exit("Wrong host or no host given!\n");
    // get file size
    char *identity_str = malloc(1000);
    identity_str[0] = 0;
    sprintf(identity_str, "%s:%s:%d", myuts.nodename, "sender", getpid());
    sprintf(send_buffer, ";2;%s;%s;%d;%d;%d;", identity_str, "", 0,
            timeout, 0);
    for (i = optind; i < argc; i++) {
        if (verbose) {
            printf("[%2d] %s\n", i, argv[i]);
        };
        sprintf(send_buffer, "%s%d;%s;", send_buffer, strlen(argv[i]), argv[i]);
    }
    send_buffer[SENDBUFF_SIZE] = '\0';  /* terminate optarg for secure use of strlen() */
    void *context = zmq_init(1);
    void *requester = zmq_socket(context, ZMQ_PUSH);

    int tcp_keepalive, tcp_keepalive_idle;
    tcp_keepalive = 1;
    tcp_keepalive_idle = 300;
    zmq_setsockopt(requester, ZMQ_IDENTITY, identity_str, strlen(identity_str));
    zmq_setsockopt(requester, ZMQ_TCP_KEEPALIVE, &tcp_keepalive,
                   sizeof(tcp_keepalive));
    zmq_setsockopt(requester, ZMQ_TCP_KEEPALIVE_IDLE, &tcp_keepalive_idle,
                   sizeof(tcp_keepalive_idle));
    alrmsigact = (struct sigaction *)malloc(sizeof(struct sigaction));
    if (!alrmsigact) {
        free(send_buffer);
        free(filebuff);
        exit(ENOMEM);
    }
    alrmsigact->sa_handler = &mysigh;
    if ((ret = sigaction(SIGALRM, (struct sigaction *)alrmsigact, NULL)) < 0) {
        retcode = err_exit("sigaction");
    } else {
        if (verbose) {
            printf
                ("send buffer has %d bytes, nodename is '%s', servicename is '%s', identity_string is '%s', pid is %d\n",
                 strlen(send_buffer), myuts.nodename, SERVICE_NAME, identity_str,
                 getpid());
            printf("send_str: '%s'\n", send_buffer);
        };
        getitimer(ITIMER_REAL, &mytimer);
        mytimer.it_value.tv_sec = timeout;
        mytimer.it_value.tv_usec = 0;
        setitimer(ITIMER_REAL, &mytimer, NULL);
        // send
        zmq_connect(requester, "ipc:///var/run/icsw/sockets/md-sync-server/receiver");
        zmq_msg_t request;
        zmq_msg_init_size(&request, strlen(send_buffer));
        memcpy(zmq_msg_data(&request), send_buffer, strlen(send_buffer));
        zmq_sendmsg(requester, &request, 0);
        zmq_msg_close(&request);
        retcode = STATE_OK;
    }
    zmq_close(requester);
    zmq_term(context);
    free(send_buffer);
    free(filebuff);
    free(dest_host);
    exit(retcode);
}
