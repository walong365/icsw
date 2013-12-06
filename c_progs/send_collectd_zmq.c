/*
    Copyright (C) 2013 Andreas Lang-Nevyjel, init.at

    Send feedback to: <lang-nevyjel@init.at>

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
#define SERVICE_NAME "send_collectd"

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define IOBUFF_SIZE 16384

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
        retcode, timeout, file_size, keep_file;
    struct in_addr sia;
    struct hostent *h;
    struct stat st;
    char *iobuff, *sendbuff, *filebuff, *host_b, *act_pos, *act_source, *act_bp,
        *dest_host, *uuid_buffer;
    struct itimerval mytimer;
    struct sigaction *alrmsigact;
    struct utsname myuts;
    int colons_passed = 0;
    int sendbuff_size = 1024;

    retcode = STATE_CRITICAL;

    timeout = 10;
    keep_file = 0;
    port = 8002;
    verbose = 0;
    quiet = 0;
    h = NULL;
    host_b = (char *)malloc(HOSTB_SIZE);
    dest_host = (char *)malloc(HOSTB_SIZE);
    dest_host[0] = 0;
    // get uts struct
    uname(&myuts);
    sprintf(dest_host, "localhost");
    while (1) {
        rchar = getopt(argc, argv, "+vm:p:ht:qk");
        //printf("%d %c\n", rchar, rchar);
        switch (rchar) {
        case 'p':
            port = strtol(optarg, NULL, 10);
            break;
        case 'm':
            sprintf(dest_host, optarg);
            //h = gethostbyname(optarg);
            //if (!h) err_exit("Can't resolve hostname");
            break;
        case 't':
            timeout = strtol(optarg, NULL, 10);
            break;
        case 'v':
            verbose = 1;
            break;
        case 'k':
            keep_file = 1;
            break;
        case 'q':
            quiet = 1;
            break;
        case 'h':
        case '?':
            printf
                ("Usage: %s [-t TIMEOUT] [-m HOST] [-p PORT] [-h] [-v] [-q] [-k (keep file)] filename\n",
                 basename(argv[0]));
            printf("  defaults: port=%d, timeout=%d, dest_host=%s\n", port,
                   timeout, dest_host);
            free(host_b);
            exit(STATE_CRITICAL);
            break;
        }
        if (rchar < 0)
            break;
    }
    // generate connection string
    sprintf(host_b, "tcp://%s:%d", dest_host, port);
/*  errno = 0;*/
    //if (!h) err_exit("Wrong host or no host given!\n");
    // get file size
    stat(argv[optind], &st);
    file_size = st.st_size;
    sendbuff_size = file_size + 1024;
    sendbuff = (char *)malloc(sendbuff_size);
    filebuff = (char *)malloc(sendbuff_size);
    if (!sendbuff) {
        free(host_b);
        exit(ENOMEM);
    }
    // read data from file
    file = open(argv[optind], 0);
    read(file, filebuff, file_size);
    close(file);
    if (!keep_file) {
        // now empty it
        open(argv[optind], O_NOFOLLOW | O_WRONLY | O_CREAT | O_TRUNC,
             S_IREAD | S_IWRITE | S_IRGRP | S_IROTH);
        close(file);
    }
    // mimic XML
    sprintf(sendbuff, "<?xml version='1.0'?><perf_data>%s</perf_data>",
            filebuff);
    sendbuff[sendbuff_size] = '\0';     /* terminate optarg for secure use of strlen() */
    if (!strlen(sendbuff))
        err_exit("Nothing to send!\n");
    //printf("Send: %s %d\n", sendbuff, strlen(sendbuff));
    void *context = zmq_init(1);
    void *requester = zmq_socket(context, ZMQ_PUSH);
    char *identity_str = parse_uuid();
    int64_t tcp_keepalive, tcp_keepalive_idle;
    tcp_keepalive = 1;
    tcp_keepalive_idle = 300;
    zmq_setsockopt(requester, ZMQ_IDENTITY, identity_str, strlen(identity_str));
    zmq_setsockopt(requester, ZMQ_TCP_KEEPALIVE, &tcp_keepalive,
                   sizeof(tcp_keepalive));
    zmq_setsockopt(requester, ZMQ_TCP_KEEPALIVE_IDLE, &tcp_keepalive_idle,
                   sizeof(tcp_keepalive_idle));
    alrmsigact = (struct sigaction *)malloc(sizeof(struct sigaction));
    if (!alrmsigact) {
        free(host_b);
        free(sendbuff);
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
                 strlen(sendbuff), myuts.nodename, SERVICE_NAME, identity_str,
                 getpid());
            printf("target is '%s'\n", host_b);
            // printf("send_str: '%s'\n", sendbuff);
        };
        getitimer(ITIMER_REAL, &mytimer);
        mytimer.it_value.tv_sec = timeout;
        mytimer.it_value.tv_usec = 0;
        setitimer(ITIMER_REAL, &mytimer, NULL);
        // send
        zmq_connect(requester, host_b);
        zmq_msg_t request;
        zmq_msg_init_size(&request, strlen(sendbuff));
        memcpy(zmq_msg_data(&request), sendbuff, strlen(sendbuff));
        zmq_sendmsg(requester, &request, 0);
        zmq_msg_close(&request);
        printf("sent\n");
        retcode = STATE_OK;
    }
    zmq_close(requester);
    zmq_term(context);
    free(sendbuff);
    free(filebuff);
    free(host_b);
    free(dest_host);
    exit(retcode);
}
