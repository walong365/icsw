/*
    Copyright (C) 2001,2002,2003,2004,2005,2006,2012 Andreas Lang, init.at

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

#include <zmq.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <sys/resource.h>
#include <sys/utsname.h>
#include <syslog.h>
#include <unistd.h>
#include <fcntl.h>
#include <netdb.h>
#include <signal.h>
#include <string.h>

#define PORT 2002
#define FNAME "/var/run/.hoststat"

#ifndef O_NOFOLLOW
#define O_NOFOLLOW	0400000
#endif

/* internal buffer sizes */
#define ERRSTR_SIZE 512
#define HOSTB_SIZE 256
#define SENDBUFF_SIZE 16384
#define IOBUFF_SIZE 256
#define SERVICE_NAME "hoststatus"

#include "parse_uuid.c"

err_exit(char* str) {
    char* errstr;
    errstr = (char*)malloc(512);
    sprintf(errstr, "An error occured for %s: %s\n", str, strerror(errno));
    syslog(LOG_DAEMON|LOG_ERR, errstr);
    fprintf (stderr, errstr);
    free(errstr);
    exit(-1);
}

int err_message(char* str) {
    char* errstr;
    errstr = malloc(ERRSTR_SIZE);
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

int main (int argc, char** argv) {
    struct rlimit resourceLimit = { 0 };
    int mysock, ret, inlen, file, fread, idx, npid, postcom, i;
    char retc;
    struct in_addr sia;
    struct hostent *h;
    size_t hn_len;
    char *fbuff, *inbuff, *filebuff, *cp, *retbuff, *src_ip;

    int verbose = 0;
    int daemon = 1;
    src_ip = (char*)malloc(HOSTB_SIZE);
    src_ip[0] = 0;
    while (1) {
        ret = getopt(argc, argv, "vhd");
        if (ret < 0) break;
        switch (ret) {
            case 'h':
                printf("Usage: %s [ -h ] [ -v ] [-d] [-i SRC_IP]\n", argv[0]);
                printf("  where -d specifies non-daemon mode\n");
                exit(-1);
                break;
            case 'v':
                verbose = 1;
                break;
            case 'd':
                daemon = 0;
                break;
            case 'i':
                sprintf(src_ip, optarg);
                break;
        }
    }
    if (daemon) {
        chdir("/");
        npid = fork();
        if (npid) exit(0);
        resourceLimit.rlim_max = 0;
        getrlimit(RLIMIT_NOFILE, &resourceLimit);
        for (i = 0; i < resourceLimit.rlim_max; i++) {
            (void) close(i);
        }
        setsid();
        npid = fork();
        if (npid) exit(0);
        chdir("/");
        umask(0);
        int file_desc = open("/dev/null", O_RDWR);
        (void) dup(file_desc);
        (void) dup(file_desc);
    };
    if (optind + 1 < argc) {
        fprintf (stderr, "Too many arguments !\n");
        exit(-1);
    } else if(optind + 1 == argc) {
        umask(0);
        /* Sets the default hoststatus */
        file = open(FNAME, O_NOFOLLOW|O_WRONLY|O_CREAT|O_TRUNC, S_IREAD|S_IWRITE|S_IRGRP|S_IROTH); /* S_IWGRP|S_IWOTH */
        if (file < 0) err_exit("Can't open statusfile "FNAME" for writing");
        if (write(file, argv[optind], strlen(argv[optind])) < 0) err_message("Failed to write to "FNAME);
        if (close(file) < 0) err_message("Failed to close "FNAME);
        syslog (LOG_DAEMON|LOG_INFO, "wrote "FNAME);
    }
    syslog (LOG_DAEMON|LOG_INFO, "hoststatus starting");
    filebuff = (char*)malloc(SENDBUFF_SIZE);
    if (!filebuff) exit(ENOMEM);
    fbuff = (char*) malloc(10);
    if (!fbuff) exit(ENOMEM);
    void *context = zmq_init(1);
    void *responder = zmq_socket(context, ZMQ_ROUTER);
    char* identity_str = parse_uuid(src_ip);
    zmq_setsockopt(responder, ZMQ_IDENTITY, identity_str, strlen(identity_str));
    char bind_address[100];
    sprintf(bind_address, "tcp://*:%d", PORT);
    zmq_bind (responder, bind_address);
    syslog(LOG_DAEMON|LOG_INFO, "hoststatus (pid %d) listening on port %d (bind_string is %s), ZMQ_IDENTITY is '%s'\n", getpid(), PORT, bind_address, identity_str);
    char *msg_text, *client_uuid;
    char *outbuff = malloc(SENDBUFF_SIZE + 1);
    char *sendbuff = malloc(SENDBUFF_SIZE + 1);
    int loop=1;
    while (loop) {
        int msg_part = 0;
        while (1) {
            zmq_msg_t message;
            zmq_msg_init (&message);
            zmq_recvmsg (responder, &message, 0);
            //  Process the message part
            int size = zmq_msg_size (&message);
            if (msg_part == 0) {
                client_uuid = malloc (size + 1);
                memcpy (client_uuid, zmq_msg_data (&message), size);
                client_uuid[size] = 0;
            } else {
                msg_text = malloc (size + 1);
                memcpy (msg_text, zmq_msg_data (&message), size);
                msg_text[size] = 0;
            };
            msg_part++;
            zmq_msg_close (&message);
            int64_t more;
            size_t more_size = sizeof (more);
            zmq_getsockopt (responder, ZMQ_RCVMORE, &more, &more_size);
            if (!more) {
                break;      //  Last message part
            };
        }
        syslog(LOG_DAEMON|LOG_INFO, "got '%s' from '%s'", msg_text, client_uuid);
        // handle command
        if (!strncmp(msg_text, "status", 6) && strlen(msg_text) == 6) {
            //printf ("%d ,  %s %d\n", num, inbuff, sizeof(inbuff));
            // recreate FNAME according to current runlevel, not beautifull but working
            system("echo 'up to runlevel' $(/sbin/runlevel |cut -d ' ' -f 2) >"FNAME);
            file = open(FNAME, 0);
            if (file < 0) {
                fprintf(stderr, "File not found");
                sprintf(outbuff, "error: statfile not found");
            } else {
                fread = read(file, filebuff, (size_t)255);
                filebuff[fread] = 0;
                //printf ("%d from %d (%d): %s\n", fread, file, strlen(filebuff), filebuff);
                for (cp = filebuff; *cp; cp++) {
                    if (*cp == '\n') *cp = 0;
                }
                //printf("%d\n", strlen(filebuff));
                close(file);
                sprintf(outbuff, "%s", filebuff);
            }
            syslog(LOG_DAEMON|LOG_INFO, "got status-request, answering %s", outbuff);
        } else if (!strncmp(msg_text, "reboot", 6) && strlen(msg_text) == 6) {
            sprintf(outbuff, "rebooting");
            postcom = 1;
            loop = 0;
            syslog(LOG_DAEMON|LOG_INFO, "got reboot-request, answering %s", outbuff);
        } else if (!strncmp(msg_text, "halt", 4) && strlen(msg_text) == 4) {
            sprintf(outbuff, "halting");
            postcom = 2;
            loop = 0;
            syslog(LOG_DAEMON|LOG_INFO, "got halt-request, answering %s", outbuff);
        } else if (!strncmp(msg_text, "poweroff", 8) && strlen(msg_text) == 8) {
            sprintf(outbuff, "poweroff");
            postcom = 3;
            loop = 0;
            syslog(LOG_DAEMON|LOG_INFO, "got poweroff-request, answering %s", outbuff);
        } else if (!strncmp(msg_text, "exit", 4) && strlen(msg_text) == 4) {
            sprintf(outbuff, "exiting");
            loop = 0;
            syslog(LOG_DAEMON|LOG_INFO, "got exit-request, answering %s", outbuff);
        } else {
            sprintf(outbuff, "unknown command %s", msg_text);
            syslog(LOG_DAEMON|LOG_INFO, "unknown command, answering %s", outbuff);
        }
        syslog(LOG_DAEMON|LOG_INFO, "uuid / buffer : %d / %d", strlen(client_uuid), strlen(outbuff));
        sprintf(sendbuff, "<?xml version='1.0'?><ics_batch><nodestatus>%s</nodestatus></ics_batch>", outbuff);
        sendbuff[SENDBUFF_SIZE] = '\0';
        zmq_msg_t reply;
        zmq_msg_init_size (&reply, strlen(client_uuid));
        memcpy (zmq_msg_data (&reply), client_uuid, strlen(client_uuid));
        zmq_sendmsg (responder, &reply, ZMQ_SNDMORE);
        zmq_msg_init_size (&reply, strlen(sendbuff));
        memcpy (zmq_msg_data (&reply), sendbuff, strlen(sendbuff));
        zmq_sendmsg (responder, &reply, 0);
        zmq_msg_close (&reply);
    }
    zmq_close(responder);
    zmq_term(context);
    //syslog (LOG_DAEMON|LOG_INFO, retbuff);
    //printf ("%s\n", outbuff);
    free(retbuff);
    free(outbuff);
    free(sendbuff);
    free(inbuff);

    if (postcom == 1) {
        syslog(LOG_DAEMON|LOG_INFO, "hoststatus calling /sbin/reboot (port %d)", PORT);
        execlp("reboot", "reboot", NULL);
        err_exit("rebooting");
    } else if (postcom == 2) {
        syslog(LOG_DAEMON|LOG_INFO, "hoststatus calling /sbin/halt (port %d)", PORT);
        execlp("halt", "halt", NULL);
        err_exit("halting");
    } else if (postcom == 3) {
        syslog(LOG_DAEMON|LOG_INFO, "hoststatus calling /sbin/poweroff (port %d)", PORT);
        execlp("poweroff", "poweroff", NULL);
        err_exit("poweroff");
    } else {
        syslog(LOG_DAEMON|LOG_INFO, "hoststatus exiting (port %d)", PORT);
    }
    return 0;
}
