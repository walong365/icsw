/*
  Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
  
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

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <sys/resource.h>
#include <syslog.h>
#include <unistd.h>
#include <fcntl.h>
#include <netdb.h>
#include <signal.h>
#include <string.h>

#define PORT 2002
#define FNAME "/var/run/.hoststat"
#define NUMWAIT 15

#ifndef O_NOFOLLOW
#define O_NOFOLLOW	0400000
#endif

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define SENDBUFF_SIZE 16384
#define IOBUFF_SIZE 256

err_exit(char *str)
{
    char *errstr;
    errstr = (char *)malloc(512);
    sprintf(errstr, "An error occured for %s: %s\n", str, strerror(errno));
    syslog(LOG_DAEMON | LOG_ERR, errstr);
    fprintf(stderr, errstr);
    free(errstr);
    exit(-1);
}

int err_message(char *str)
{
    char *errstr;
    errstr = malloc(ERRSTR_SIZE);
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

int main(int argc, char **argv)
{
    struct rlimit resourceLimit = { 0 };
    int mysock, ret, num, inlen, loop, file, fread, idx, npid, verbose, postcom,
        n_retries, i;
    char retc;
    struct sockaddr_in sockaddr;
    struct in_addr sia;
    struct hostent *h;
    size_t hn_len;
    char *fbuff, *inbuff, *outbuff, *filebuff, *cp, *retbuff;

    chdir("/");
    npid = fork();
    if (npid)
        exit(0);
    resourceLimit.rlim_max = 0;
    getrlimit(RLIMIT_NOFILE, &resourceLimit);
    for (i = 0; i < resourceLimit.rlim_max; i++) {
        (void)close(i);
    }
    setsid();
    npid = fork();
    if (npid)
        exit(0);
    chdir("/");
    umask(0);
    int file_desc = open("/dev/null", O_RDWR);
    (void)dup(file_desc);
    (void)dup(file_desc);
    verbose = 0;
    n_retries = 0;
    while (1) {
        ret = getopt(argc, argv, "vhn:");
        if (ret < 0)
            break;
        switch (ret) {
        case 'h':
            printf("Usage: %s [ -h ] [ -v ] [ -n NUM ]\n", basename(argv[0]));
            printf
                ("  where NUM sets the number of retries to bind to the given port (%d second gap)\n",
                 NUMWAIT);
            exit(-1);
            break;
        case 'v':
            verbose = 1;
            break;
        case 'n':
            n_retries = atoi(optarg);
            break;
        }
    }
    if (optind + 1 < argc) {
        fprintf(stderr, "Too many arguments !\n");
        exit(-1);
    } else if (optind + 1 == argc) {
        umask(0);
        /* Sets the default hoststatus */
        file = open(FNAME, O_NOFOLLOW | O_WRONLY | O_CREAT | O_TRUNC, S_IREAD | S_IWRITE | S_IRGRP | S_IROTH);  /* S_IWGRP|S_IWOTH */
        if (file < 0)
            err_exit("Can't open statusfile " FNAME " for writing");
        ret = write(file, argv[optind], strlen(argv[optind]));
        if (ret < 0)
            err_message("Failed to write to " FNAME);
        ret = close(file);
        if (ret < 0)
            err_message("Failed to close " FNAME);
        syslog(LOG_DAEMON | LOG_INFO, "wrote " FNAME);
    }
    syslog(LOG_DAEMON | LOG_INFO, "hoststatus starting");
    filebuff = (char *)malloc(SENDBUFF_SIZE);
    if (!filebuff)
        exit(ENOMEM);
    fbuff = (char *)malloc(10);
    if (!fbuff)
        exit(ENOMEM);
    h = gethostbyname((char *)"localhost");
    if (h) {
        sockaddr.sin_family = h->h_addrtype;
    } else {
        sockaddr.sin_family = AF_INET;
    }
    sockaddr.sin_port = htons((int)PORT);
    sockaddr.sin_addr.s_addr = INADDR_ANY;
    mysock = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(mysock, SOL_SOCKET, SO_REUSEADDR, (int *)1, (socklen_t) 1);
    if (mysock < 0)
        err_exit("socket()");
    ret = -1;
    while (ret < 0) {
        ret =
            bind(mysock, (struct sockaddr *)&sockaddr, sizeof(struct sockaddr));
        if (ret < 0) {
            if (n_retries) {
                n_retries--;
                sprintf(filebuff,
                        "bind failed,  sleeping for %d seconds (%d remaining)",
                        NUMWAIT, n_retries);
                syslog(LOG_DAEMON | LOG_ERR, filebuff);
                sleep(NUMWAIT);
            } else {
                err_exit("bind");
            }
        }
    }
    ret = listen(mysock, 5);
    if (ret < 0)
        err_exit("listen");
    syslog(LOG_DAEMON | LOG_INFO, "hoststatus (pid %d) listening on port %d\n",
           getpid(), ntohs(sockaddr.sin_port));
    postcom = 0;
    loop = 1;
    while (loop == 1) {
        ret = accept(mysock, NULL, 0);
        //(struct sockaddr*) sockaddr, sizeof(struct sockaddr));
        if (ret < 0)
            err_exit("accept");
        num = recv(ret, (char *)fbuff, (size_t) 8, 0);
        fbuff[8] = 0;
        inlen = atoi(fbuff);
        inbuff = (char *)malloc((size_t) (inlen + 1));
        if (!inbuff)
            exit(ENOMEM);
        inbuff[inlen] = 0;
        num = recv(ret, (char *)inbuff, (size_t) inlen, 0);
        if (num != inlen)
            syslog(LOG_DAEMON | LOG_ERR, "short read: %d -> %d\n", num, inlen);
        if (verbose)
            syslog(LOG_DAEMON | LOG_INFO, "got command %s\n", inbuff);
        outbuff = (char *)malloc((size_t) (SENDBUFF_SIZE));
        if (!outbuff)
            exit(ENOMEM);
        retbuff = (char *)malloc((size_t) (SENDBUFF_SIZE + 8));
        if (!retbuff)
            exit(ENOMEM);
        if (!strncmp(inbuff, "exit", 4)) {
            loop = 0;
            sprintf(outbuff, "exiting...");
        } else if (!strncmp(inbuff, "status", 6)) {
            //printf ("%d ,  %s %d\n", num, inbuff, sizeof(inbuff));
            file = open(FNAME, 0);
            if (file < 0) {
                fprintf(stderr, "File not found");
                sprintf(outbuff, "error: statfile not found");
            } else {
                fread = read(file, filebuff, (size_t) 255);
                filebuff[fread] = 0;
                //printf ("%d from %d (%d): %s\n", fread, file, strlen(filebuff), filebuff);
                for (cp = filebuff; *cp; cp++) {
                    if (*cp == '\n')
                        *cp = 0;
                }
                //printf("%d\n", strlen(filebuff));
                close(file);
                sprintf(outbuff, "%s", filebuff);
            }
            syslog(LOG_DAEMON | LOG_INFO, "got status-request,  answering %s",
                   outbuff);
        } else if (!strncmp(inbuff, "reboot", 6)) {
            sprintf(outbuff, "rebooting");
            postcom = 1;
            loop = 0;
            syslog(LOG_DAEMON | LOG_INFO, "got reboot-request,  answering %s",
                   outbuff);
        } else if (!strncmp(inbuff, "halt", 4)) {
            sprintf(outbuff, "halting");
            postcom = 2;
            loop = 0;
            syslog(LOG_DAEMON | LOG_INFO, "got halt-request,  answering %s",
                   outbuff);
        } else if (!strncmp(inbuff, "poweroff", 8)) {
            sprintf(outbuff, "poweroff");
            postcom = 3;
            loop = 0;
            syslog(LOG_DAEMON | LOG_INFO, "got poweroff-request,  answering %s",
                   outbuff);
        } else {
            sprintf(outbuff, "unknown command");
        }
        outbuff[SENDBUFF_SIZE] = '\0';
        sprintf(retbuff, "%08d%s", strlen(outbuff), outbuff);
        //syslog (LOG_DAEMON|LOG_INFO, retbuff);
        //printf ("%s\n", outbuff);
        num = send(ret, (char *)retbuff, (size_t) strlen(retbuff), 0);
        //printf ("%d bytes send.\n", num);
        free(retbuff);
        free(outbuff);
        shutdown(ret, 2);
        close(ret);
        free(inbuff);
    }

    shutdown(mysock, 2);
    close(mysock);
    free(fbuff);
    if (postcom == 1) {
        syslog(LOG_DAEMON | LOG_INFO,
               "hoststatus calling /sbin/reboot (port %d)\n", PORT);
        execlp("reboot", "reboot", NULL);
        err_exit("rebooting");
    } else if (postcom == 2) {
        syslog(LOG_DAEMON | LOG_INFO,
               "hoststatus calling /sbin/halt (port %d)\n", PORT);
        execlp("halt", "halt", NULL);
        err_exit("halting");
    } else if (postcom == 3) {
        syslog(LOG_DAEMON | LOG_INFO,
               "hoststatus calling /sbin/poweroff (port %d)\n", PORT);
        execlp("poweroff", "poweroff", NULL);
        err_exit("poweroff");
    } else {
        syslog(LOG_DAEMON | LOG_INFO, "hoststatus exiting (port %d)\n", PORT);
    }
    return 0;
}
