/*
  Copyright (C) 2012-2013,2015 Andreas Lang-Nevyjel, init.at
 
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
#define SERVICE_NAME "sczmq"

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define SENDBUFF_SIZE 65536
#define RECVBUFF_SIZE 65536
#define IOBUFF_SIZE 65536

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

int main(int argc, char **argv)
{
    int ret, num, inlen, file, i /*, time */ , rchar, quiet,
        retcode, timeout, host_written, snmp_version, delay;
    struct in_addr sia;

    struct hostent *h;

    char *iobuff, *host_b, *act_pos, *act_source, *act_bp, *snmp_community;
    struct itimerval mytimer;

    struct sigaction *alrmsigact;

    struct utsname myuts;

    retcode = STATE_CRITICAL;

    timeout = 10;
    verbose = 0;
    quiet = 0;
    delay = 0;
    host_written = 0;
    snmp_version = 1;
    h = NULL;
    // get uts struct
    uname(&myuts);
    send_buffer = (char *)malloc(SENDBUFF_SIZE);
    host_b = (char *)malloc(SENDBUFF_SIZE);
    snmp_community = (char *)malloc(2000);
    send_buffer[0] = 0;
    strcpy(host_b, "localhost");
    strcpy(snmp_community, "public");
    while (1) {
        rchar = getopt(argc, argv, "+vm:ht:qC:V:d");
        //printf("%d %c\n", rchar, rchar);
        switch (rchar) {
        case 'm':
            sprintf(host_b, "%s", optarg);
            //h = gethostbyname(optarg);
            //if (!h) err_exit("Can't resolve hostname");
            break;
        case 't':
            timeout = strtol(optarg, NULL, 10);
            break;
        case 'v':
            verbose = 1;
            break;
        case 'V':
            snmp_version = strtol(optarg, NULL, 10);
            break;
        case 'd':
            delay = 1;
            break;
        case 'C':
            strcpy(snmp_community, optarg);
            break;
        case 'q':
            quiet = 1;
            break;
        case 'h':
        case '?':
            printf
                ("Usage: %s [-t TIMEOUT] [-m HOST] [-C COMMUNITY] [-V VERSION] [-h] [-v] [-q] [-d(elay)] command\n",
                 basename(argv[0]));
            printf
                ("  defaults: community=%s, version=%d, timeout=%d\n",
                 snmp_community, snmp_version, timeout);
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
    sprintf(send_buffer, ";1;%s;%s;%d;%s;%d;", identity_str, host_b,
            snmp_version, snmp_community, timeout);
    act_pos = send_buffer;
    if (verbose) {
        printf("sendbuffer before arguments: '%s'\n", send_buffer);
        printf("argument info (%d length)\n", argc);
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

    int rcv_timeout = 200;

    int res_code = 0;

    int retry_iter = 0;
    char recv_buffer[RECVBUFF_SIZE];
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
        mytimer.it_value.tv_sec = timeout + 2;
        mytimer.it_value.tv_usec = 0;
        setitimer(ITIMER_REAL, &mytimer, NULL);
        /* init 0MQ context */
        void *context = zmq_init(1);

        /* PUSH sender socket */
        void *requester = zmq_socket(context, ZMQ_PUSH);

        /* SUB receiver socket */
        void *receiver = zmq_socket(context, ZMQ_SUB);

        // send
        zmq_connect(requester,
                    "ipc:///var/log/cluster/sockets/snmp-relay/receiver");
        zmq_connect(receiver,
                    "ipc:///var/log/cluster/sockets/snmp-relay/sender");
        zmq_setsockopt(receiver, ZMQ_SUBSCRIBE, identity_str,
                       strlen(identity_str));
        zmq_setsockopt(receiver, ZMQ_RCVTIMEO, &rcv_timeout, sizeof(int));
        zmq_msg_t request, reply;

        if (verbose) {
            printf
                ("send buffer has %d bytes, identity is '%s', nodename is '%s', servicename is '%s', pid is %d, delay is %d\n",
                 strlen(send_buffer), identity_str, myuts.nodename,
                 SERVICE_NAME, getpid(), delay);
        };
        zmq_msg_init_size(&request, strlen(send_buffer));
        memcpy(zmq_msg_data(&request), send_buffer, strlen(send_buffer));
        zmq_msg_init(&reply);
        if (delay) {
            usleep(10000);
        }
        zmq_sendmsg(requester, &request, 0);
        if (verbose) {
            printf("send(), waiting for result\n");
        }
        // receive header
        retry_iter = 0;
        while (1) {
            retry_iter++;
            res_code = zmq_recv(receiver, recv_buffer, RECVBUFF_SIZE, 0);
            if (res_code > 0)
                break;
            if (verbose) {
                printf("RCV_TIMEOUT, retry_iter is %d\n", retry_iter);
            }
        };
        int64_t more = 0;
        size_t more_size = sizeof(more);

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
        zmq_close(requester);
        zmq_close(receiver);
        zmq_term(context);
    }
    free(send_buffer);
    free(host_b);
    exit(retcode);
}
