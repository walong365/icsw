/*
  Copyright (C) 2012-2015 Andreas Lang-Nevyjel, init.at

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

#define STATE_OK 0
#define STATE_WARNING 1
#define STATE_CRITICAL 2
#define SERVICE_NAME "cczmq"

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define SENDBUFF_SIZE 16384
#define RECVBUFF_SIZE 65536
#define IOBUFF_SIZE 16384

char *send_buffer;
int verbose;

int err_message(char *str)
{
    char *errstr;

    errstr = (char *)malloc(ERRSTR_SIZE);
    if (!errstr)
        return -ENOMEM;
    if (errno) {
        sprintf(errstr, "An error occured (%d) : %s (%d) %s for %s\n",
                getpid(), str, errno, strerror(errno), send_buffer);
    } else {
        sprintf(errstr, "An error occured (%d): %s for %s\n", getpid(), str,
                send_buffer);
    }
    if (verbose) {
        syslog(LOG_DAEMON | LOG_ERR, errstr);
    };
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

void try_second_socket(int dummy)
{
    printf("first timeout\n");
}

int main(int argc, char **argv)
{
    int ret, num, inlen, file, i /*, time */ , port, rchar, quiet,
        retcode, timeout, host_written, only_send, raw, delay;
    struct in_addr sia;

    struct hostent *h;

    char *iobuff, *recv_buffer, *host_b, *act_pos, *act_source, *act_bp;

    struct itimerval mytimer;

    struct sigaction *alrmsigact;

    struct utsname myuts;

    retcode = STATE_CRITICAL;

    timeout = 15;
    port = 2001;
    verbose = 0;
    quiet = 0;
    raw = 0;
    delay = 0;
    host_written = 0;
    h = NULL;
    // get uts struct
    uname(&myuts);
    send_buffer = (char *)malloc(SENDBUFF_SIZE);
    host_b = (char *)malloc(SENDBUFF_SIZE);
    send_buffer[0] = 0;
    host_b[0] = 0;
    only_send = 0;
    sprintf(host_b, "localhost");
    while (1) {
        rchar = getopt(argc, argv, "+vm:p:ht:qsrd");
        //printf("%d %c\n", rchar, rchar);
        switch (rchar) {
        case 'p':
            port = strtol(optarg, NULL, 10);
            break;
        case 'm':
            sprintf(host_b, "%s", optarg);
            break;
        case 't':
            timeout = strtol(optarg, NULL, 10);
            break;
        case 'd':
            delay = 1;
            break;
        case 'v':
            verbose = 1;
            break;
        case 's':
            only_send = 1;
            break;
        case 'q':
            quiet = 1;
            break;
        case 'r':
            raw = 1;
            break;
        case 'h':
        case '?':
            printf
                ("Usage: %s [-t TIMEOUT] [-m HOST] [-p PORT] [-h] [-v] [-q] [-r] [-s] [-d(delay)] command\n",
                 basename(argv[0]));
            printf("  defaults: port=%d, timeout=%d\n", port, timeout);
            free(host_b);
            exit(STATE_CRITICAL);
            break;
        }
        if (rchar < 0)
            break;
    }
    //printf("%s\n", host_b);
    /*  errno = 0; */
    //if (!h) err_exit("Wrong host or no host given!\n");
    char identity_str[64];

    sprintf(identity_str, "%s:%s:%d", myuts.nodename, SERVICE_NAME, getpid());
    sprintf(send_buffer, ";2;%s;%s;%d;%d;%d;", identity_str, host_b, port,
            timeout, raw);
    act_pos = send_buffer;
    if (verbose) {
        printf("argument info (%d found)\n", argc);
    };
    for (i = optind; i < argc; i++) {
        if (verbose) {
            printf("[%2d] %s\n", i, argv[i]);
        };
        sprintf(send_buffer, "%s%d;%s;", send_buffer, strlen(argv[i]), argv[i]);
//        if (act_pos != send_buffer) *act_pos++=' ';
//        act_source = argv[i];
//        while (*act_source) *act_pos++=*act_source++;
//        *act_pos = 0;
    }
    send_buffer[SENDBUFF_SIZE] = '\0';  /* terminate optarg for secure use of strlen() */
    if (!strlen(send_buffer))
        err_exit("Nothing to send!\n");
    //printf("Send: %s %d\n", send_buffer, strlen(send_buffer));
    int linger = 100, n_bytes;

    recv_buffer = (char *)malloc(RECVBUFF_SIZE);
    //printf("%d -> 0x%x\n", RECVBUFF_SIZE, recv_buffer);
    alrmsigact = (struct sigaction *)malloc(sizeof(struct sigaction));
    if (!alrmsigact) {
        free(host_b);
        free(send_buffer);
        exit(ENOMEM);
    }
    alrmsigact->sa_handler = &mysigh;
    if ((ret = sigaction(SIGALRM, (struct sigaction *)alrmsigact, NULL)) < 0) {
        retcode = err_exit("sigaction");
    } else {
        getitimer(ITIMER_REAL, &mytimer);
        mytimer.it_value.tv_sec = timeout;
        mytimer.it_value.tv_usec = 0;
        setitimer(ITIMER_REAL, &mytimer, NULL);
        /* init 0MQ context */
        void *context = zmq_init(1);

        /* PUSH sender socket */
        void *requester = zmq_socket(context, ZMQ_PUSH);

        /* SUB receiver socket */
        void *receiver = zmq_socket(context, ZMQ_SUB);
        if (!only_send) {
            // receive, init receiver before sender to let ZMQ settle
            zmq_connect(receiver,
                        "ipc:///var/run/icsw/sockets/collrelay/sender");

            /* set filter */
            zmq_setsockopt(receiver, ZMQ_SUBSCRIBE, identity_str,
                           strlen(identity_str));
        };
        // send
        zmq_connect(requester,
                    "ipc:///var/run/icsw/sockets/collrelay/receiver");
        zmq_msg_t request;

        if (verbose) {
            printf
                ("send buffer has %d bytes, identity is '%s', nodename is '%s', servicename is '%s', only_send is %d, delay is %d, pid is %d\n",
                 strlen(send_buffer), identity_str, myuts.nodename,
                 SERVICE_NAME, only_send, delay, getpid());
            printf("%s\n", send_buffer);
        };
        zmq_msg_init_size(&request, strlen(send_buffer));
        memcpy(zmq_msg_data(&request), send_buffer, strlen(send_buffer));
        if (!only_send && delay) {
            usleep(10000);
        }
        zmq_sendmsg(requester, &request, 0);
        if (verbose) {
            printf("send(), waiting for result\n");
        }
        if (!only_send) {
            // receive header
            int64_t more = 0;
            size_t more_size = sizeof(more);

            // receive header
            n_bytes = zmq_recv(receiver, recv_buffer, RECVBUFF_SIZE, 0);
            if (verbose) {
                printf("header size: %d\nheader content: %s\n", n_bytes,
                       recv_buffer);
            }
            zmq_getsockopt(receiver, ZMQ_RCVMORE, &more, &more_size);
            zmq_msg_close(&request);
            if (verbose) {
                printf("rcv(): more_flag is %d\n", more);
            };
            if (more) {
                // receive body
                n_bytes = zmq_recv(receiver, recv_buffer, RECVBUFF_SIZE, 0);
                if (verbose) {
                    printf("body has %d bytes\n", n_bytes);
                };
                if (n_bytes > RECVBUFF_SIZE) {
                    printf("message was truncated (%d > %d)\n", n_bytes,
                           RECVBUFF_SIZE);
                    retcode = 2;
                } else {
                    recv_buffer[n_bytes] = 0;
                    retcode = strtol(recv_buffer, NULL, 10);
                }
                if (verbose) {
                    printf("rcv(): '%s'\n", recv_buffer + 2);
                };
                printf("%s\n", recv_buffer + 2);
            } else {
                retcode = 2;
                printf("short message\n");
            }
        } else {
            retcode = 0;
            printf("sent\n");
        }
        zmq_close(receiver);
        zmq_close(requester);
        zmq_term(context);
    }
    free(recv_buffer);
    free(send_buffer);
    free(host_b);
    exit(retcode);
}
