/*
    Copyright (C) 2001,2002,2003,2004,2009 Andreas Lang-Nevyjel, init.at
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

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define SENDBUFF_SIZE 16384
#define IOBUFF_SIZE 16384

int err_message(char *str)
{
    char *errstr;
    errstr = (char *)malloc(ERRSTR_SIZE);
    if (!errstr)
        return -ENOMEM;
    if (errno) {
        sprintf(errstr, "An error occured : %s (%d) %s\n", str, errno,
                strerror(errno));
    } else {
        sprintf(errstr, "An error occured : %s\n", str);
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
    int mysock, ret, num, inlen, file, i /*, time */ , port, rchar, verbose,
        quiet, retcode, write_file, timeout;
    struct sockaddr_in *sockaddr;
    struct in_addr sia;
    struct hostent *h;
    char *iobuff, *sendbuff, *host_b, *act_pos, *act_source, *act_bp;
    struct itimerval mytimer;
    struct sigaction *alrmsigact;

    retcode = STATE_CRITICAL;

    timeout = 10;
    port = 8000;
    verbose = 0;
    quiet = 0;
    write_file = 1;
    h = NULL;
    host_b = (char *)malloc(HOSTB_SIZE);
    if (!host_b)
        exit(ENOMEM);
    host_b[0] = 0;
    while (1) {
        rchar = getopt(argc, argv, "+vm:p:ht:wq");
        //printf("%d %c\n", rchar, rchar);
        switch (rchar) {
        case 'p':
            port = strtol(optarg, NULL, 10);
            break;
        case 'm':
            if ((HOSTB_SIZE - 1) < strlen(optarg)) {
                free(host_b);
                exit(EINVAL);
            }
            strcpy((char *)host_b, (char *)optarg);
            h = gethostbyname(optarg);
            if (!h)
                err_exit("Can't resolve hostname");
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
            printf
                ("Usage: %s [-t TIMEOUT] [-m HOST] [-p PORT] [-h] [-v] [-w] [-q] command\n",
                 basename(argv[0]));
            printf("  defaults: port=%d, timeout=%d\n", port, timeout);
            free(host_b);
            exit(STATE_CRITICAL);
            break;
        }
        if (rchar < 0)
            break;
    }
/*  errno = 0;*/
    if (!h)
        err_exit("Wrong host or no host given!\n");
    sendbuff = (char *)malloc(SENDBUFF_SIZE);
    if (!sendbuff) {
        free(host_b);
        exit(ENOMEM);
    }

    act_pos = sendbuff;
    for (i = optind; i < argc; i++) {
        if (act_pos != sendbuff)
            *act_pos++ = ' ';
        act_source = argv[i];
        while (*act_source)
            *act_pos++ = *act_source++;
        *act_pos = 0;
    }
    sendbuff[SENDBUFF_SIZE] = '\0';     /* terminate optarg for secure use of strlen() */
    if (!strlen(sendbuff))
        err_exit("Nothing to send!\n");
    //printf("Send: %s %d\n", sendbuff, strlen(sendbuff));
    // check if we have to write to FNAME
    if (write_file) {
        file =
            open(FNAME, O_NOFOLLOW | O_WRONLY | O_CREAT | O_TRUNC,
                 S_IREAD | S_IWRITE | S_IRGRP | S_IROTH);
        if (file < 0)
            err_exit("Can't open statusfile " FNAME " for writing");
        ret = write(file, sendbuff, strlen(sendbuff));
        if (ret < 0)
            err_message("Failed to write to " FNAME);
        ret = close(file);
        if (ret < 0)
            err_message("Failed to close " FNAME);
    }
    sockaddr = (struct sockaddr_in *)malloc(sizeof(struct sockaddr_in));
    if (!sockaddr) {
        free(host_b);
        free(sendbuff);
        exit(ENOMEM);
    }
    sockaddr->sin_family = h->h_addrtype;
    memcpy((char *)&sia.s_addr, h->h_addr_list[0], h->h_length);
    sockaddr->sin_port = htons(port);
    sockaddr->sin_addr = sia;
    mysock = socket(AF_INET, SOCK_STREAM, 0);
    if (mysock < 0) {
        err_message("socket()");
    } else {
        alrmsigact = (struct sigaction *)malloc(sizeof(struct sigaction));
        if (!alrmsigact) {
            free(host_b);
            free(sendbuff);
            free(sockaddr);
            exit(ENOMEM);
        }
        alrmsigact->sa_handler = &mysigh;
        if ((ret =
             sigaction(SIGALRM, (struct sigaction *)alrmsigact, NULL)) < 0) {
            retcode = err_exit("sigaction");
        } else {
            getitimer(ITIMER_REAL, &mytimer);
            mytimer.it_value.tv_sec = timeout;
            mytimer.it_value.tv_usec = 0;
            setitimer(ITIMER_REAL, &mytimer, NULL);
            ret =
                connect(mysock, (struct sockaddr *)sockaddr,
                        sizeof(struct sockaddr));
            if (ret < 0) {
                err_message("connect() to ");
            } else {
                iobuff = (char *)malloc(IOBUFF_SIZE);
                if (!iobuff) {
                    free(host_b);
                    free(sendbuff);
                    free(sockaddr);
                    free(alrmsigact);
                    exit(ENOMEM);
                }
                sprintf(iobuff, "%08d%s", (size_t) strlen(sendbuff), sendbuff);
                iobuff[IOBUFF_SIZE] = '\0';
                ret = send(mysock, iobuff, (size_t) strlen(iobuff), 0);
                num = recv(mysock, (char *)iobuff, (size_t) 8, 0);
                iobuff[8] = 0;
                inlen = atoi(iobuff);
                if (num != 8) {
                    syslog(LOG_DAEMON | LOG_ERR,
                           "short read while receiving response header for '%s' to %s (got only %d instead of 8 bytes), skipping further reads\n",
                           sendbuff, (char *)host_b, num);
                    /* ret = recv(mysock, (char*)iobuff, (size_t)256, 0); */
                } else {
                    act_bp = iobuff;
                    while (num) {
                        num = recv(mysock, (char *)act_bp, (size_t) inlen, 0);
                        if (!num) {
                            syslog(LOG_DAEMON | LOG_ERR,
                                   "empty read while receiving response body for '%s' to %s\n",
                                   sendbuff, (char *)host_b);
                        } else if (num != inlen) {
                            syslog(LOG_DAEMON | LOG_INFO,
                                   "short read while receiving response body for '%s' to %s (got only %d instead of %d bytes)\n",
                                   sendbuff, (char *)host_b, num, inlen);
                            inlen -= num;
                        } else {
                            act_bp[num] = 0;
                            syslog(LOG_DAEMON | LOG_INFO,
                                   "successfully sent '%s' to host %s, port %d, received %d bytes\n",
                                   sendbuff, host_b, port, num);
                            retcode = STATE_OK;
                            if (!quiet) {
                                printf("%s\n", iobuff);
                            }
                            num = 0;
                        }
                        act_bp += num;
                    }
                }
                free(iobuff);
            }
            shutdown(mysock, 2);
        }
        close(mysock);
    }
    free(sendbuff);
    free(sockaddr);
    free(host_b);
    exit(retcode);
}
