/*
    Copyright (C) 2001,2002,2003,2004,2009,2011 Andreas Lang-Nevyjel, init.at

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
#define FNAME "/var/run/.hoststat"
#define UUID_NAME "/etc/sysconfig/cluster/.cluster_device_uuid"
#define SERVICE_NAME "tell_mother"

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define SENDBUFF_SIZE 16384
#define IOBUFF_SIZE 16384

int err_message(char* str) {
    char* errstr;
    errstr = (char*)malloc(ERRSTR_SIZE);
    if (!errstr) return -ENOMEM;
    if (errno) {
        sprintf (errstr, "An error occured : %s (%d) %s\n", str, errno, strerror(errno));
    } else {
        sprintf (errstr, "An error occured : %s\n", str);
    }
    syslog (LOG_DAEMON|LOG_ERR, errstr);
    fprintf (stderr, errstr);
    free(errstr);
    return 0;
}

int err_exit(char* str) {
    if ( (err_message(str)) <0 ) exit(ENOMEM);
    exit(STATE_CRITICAL);
}

void mysigh(int dummy) {
    err_exit("Timeout while waiting for answer");
    //err_exit(0, ebuff, 0);
}

int main (int argc, char** argv) {
    int ret, num, uuid_file, inlen, file, i/*, time*/, port, rchar, verbose, quiet, retcode, write_file, timeout;
    struct in_addr sia;
    struct hostent *h;
    char *iobuff, *sendbuff, *host_b, *act_pos, *act_source, *act_bp, *dest_host, *uuid_buffer;
    struct itimerval mytimer;
    struct sigaction *alrmsigact;
    struct utsname myuts;
    int colons_passed = 0;

    retcode = STATE_CRITICAL;

    timeout = 10;
    port = 8000;
    verbose = 0;
    quiet = 0;
    write_file = 1;
    h = NULL;
    host_b = (char*)malloc(HOSTB_SIZE);
    dest_host = (char*)malloc(HOSTB_SIZE);
    if (!host_b) exit(ENOMEM);
    host_b[0] = 0;
    // get uts struct
    uname(&myuts);
    sprintf(dest_host, "localhost");
    while (1) {
        rchar = getopt(argc, argv, "+vm:p:ht:wq");
        //printf("%d %c\n", rchar, rchar);
        switch (rchar) {
            case 'p':
                port = strtol(optarg, NULL, 10);
                break;
            case 'm':
                sprintf(host_b, "%s%s", host_b, optarg);
                //h = gethostbyname(optarg);
                //if (!h) err_exit("Can't resolve hostname");
                break;
            case 't':
                timeout = strtol(optarg, NULL, 10);
                break;
            case 'v':
                verbose = 1;
                break;
            case 'q':
                quiet = 1;
                break;
            case 'w':
                write_file = 0;
                break;
            case 'h':
            case '?':
                printf("Usage: %s [-t TIMEOUT] [-m HOST] [-p PORT] [-h] [-v] [-w] [-q] command\n", basename(argv[0]));
                printf("  defaults: port=%d, timeout=%d\n", port, timeout);
                free(host_b);
                exit(STATE_CRITICAL);
                break;
        }
        if (rchar < 0) break;
    }
    // generate connection string
    sprintf(host_b, "tcp://%s:%d", dest_host, port);
/*  errno = 0;*/
    //if (!h) err_exit("Wrong host or no host given!\n");
    sendbuff = (char*)malloc(SENDBUFF_SIZE);
    if (!sendbuff) {
        free(host_b);
        exit(ENOMEM);
    }
    for (i = optind; i < argc; i++) {
        // skip first space
        if (i > optind) sprintf(sendbuff, "%s ", sendbuff);
        sprintf(sendbuff, "%s%s", sendbuff, argv[i]);
//        if (act_pos != sendbuff) *act_pos++=' ';
//        act_source = argv[i];
//        while (*act_source) *act_pos++=*act_source++;
//        *act_pos = 0;
    }
    sendbuff[SENDBUFF_SIZE] = '\0';/* terminate optarg for secure use of strlen() */
    if (!strlen(sendbuff)) err_exit("Nothing to send!\n");
    //printf("Send: %s %d\n", sendbuff, strlen(sendbuff));
    // check if we have to write to FNAME
    if (write_file) {
        file = open(FNAME, O_NOFOLLOW|O_WRONLY|O_CREAT|O_TRUNC, S_IREAD|S_IWRITE|S_IRGRP|S_IROTH);
        if (file < 0) err_exit("Can't open statusfile "FNAME" for writing");
        if (write(file, sendbuff, strlen(sendbuff)) < 0) err_message("Failed to write to "FNAME);
        if (close(file) < 0) err_message("Failed to close "FNAME);
    }
    void *context = zmq_init(1);
    void *requester = zmq_socket(context, ZMQ_XREQ);
    char* identity_str;
    identity_str = (char*)malloc(1000);
    identity_str[0] = 0;
    uuid_buffer = (char*)malloc(1000);
    uuid_file = open(UUID_NAME, O_RDONLY);
    if (uuid_file > 0) {
        read(uuid_file, uuid_buffer, 46);
        for (i=0; i < strlen(uuid_buffer); i++) {
            if ((colons_passed > 1 || i > 17) && (uuid_buffer[i] != '\n')) sprintf(identity_str, "%s%c", identity_str, uuid_buffer[i]);
            if (uuid_buffer[i] == ':') colons_passed++;
        };
        sprintf(identity_str, "%s:%s", identity_str, SERVICE_NAME);
    } else {
        sprintf(identity_str, "%s:%s:%d", myuts.nodename, SERVICE_NAME, getpid());
    };
    zmq_setsockopt(requester, ZMQ_IDENTITY, identity_str, strlen(identity_str));
    alrmsigact = (struct sigaction*)malloc(sizeof(struct sigaction));
    if (!alrmsigact) {
        free(host_b);
        free(sendbuff);
        exit(ENOMEM);
    }
    alrmsigact -> sa_handler = &mysigh;
    if ((ret = sigaction(SIGALRM, (struct sigaction*)alrmsigact, NULL))<0) {
        retcode = err_exit("sigaction");
    } else {
        getitimer(ITIMER_REAL, &mytimer);
        mytimer.it_value.tv_sec = timeout;
        mytimer.it_value.tv_usec = 0;
        setitimer(ITIMER_REAL, &mytimer, NULL);
        // send
        zmq_connect(requester, host_b);
        zmq_msg_t request;
        if (verbose) {
            printf("send buffer has %d bytes, nodename is '%s', servicename is '%s', identity_string is '%s', pid is %d\n", strlen(sendbuff), myuts.nodename, SERVICE_NAME, identity_str, getpid());
        };
        zmq_msg_init_size (&request, strlen(sendbuff));
        memcpy(zmq_msg_data(&request), sendbuff, strlen(sendbuff));
        zmq_send(requester, &request, 0);
        zmq_msg_close(&request);
        // receive
        zmq_msg_t reply;
        zmq_msg_init(&reply);
        zmq_recv(requester, &reply, 0);
        int reply_size = zmq_msg_size(&reply);
        char *recv_buffer = malloc(reply_size + 1);
        memcpy (recv_buffer, zmq_msg_data(&reply), reply_size);
        recv_buffer[reply_size] = 0;
        zmq_msg_close(&reply);
        printf("%s\n", recv_buffer);
    }
    free(sendbuff);
    free(host_b);
    free(dest_host);
    exit(retcode);
}
