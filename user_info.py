#!/usr/bin/python-init -Ot
#
# Copyright (C) 2005-2008,2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" change password from the commandline """

import sys
import argparse
import logging_tools
import getopt
import os
import pwd
import termios
import crypt
import random
import server_command
import process_tools

def show_help(script):
    print "Usage : %s [OPTIONS] username" % (os.path.basename(script))
    print "  where OPTIONS is one or more of"
    print " -h, --help      this help"
    print " -p              change password"
    print " -i              show information"
    print " -l              show all users"

def list_mode(dc):
    dc.execute("SELECT u.*, g.* FROM user u, ggroup g WHERE u.ggroup=g.ggroup_idx ORDER BY u.login")
    out_list = logging_tools.form_list()
    out_list.set_header_string(0, ["login", "groupname", "uid", "gid", "title", "vname", "nname", "email", "phone"])
    for db_rec in dc.fetchall():
        out_list.add_line([db_rec["login"],
                           db_rec["ggroupname"],
                           db_rec["uid"],
                           db_rec["gid"],
                           db_rec["usertitan"],
                           db_rec["uservname"],
                           db_rec["usernname"],
                           db_rec["useremail"],
                           db_rec["usertel"]])
    print out_list
    return 0

def get_pass(prompt=">"):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    try:
        passwd = raw_input(prompt)
    except KeyboardInterrupt:
        passwd = ""
    except EOFError:
        passwd = ""
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print
    return passwd

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--mode", dest="mode", choices=["info", "list", "change"], default="info", help="set mode [%(default)s]")
    my_parser.add_argument("username", nargs="?", default=pwd.getpwuid(os.getuid())[0], help="set username [%(default)s]")
    options = my_parser.parse_args()
    if options.mode in ["info", "change"] and not options.username:
        print "Need username for %s mode" % (options.mode)
        sys.exit(-1)
    print options
    # get name of directory server
    ds_file_name = "/etc/sysconfig/cluster/directory_server"
    if not os.path.isfile(ds_file_name):
        print "No directory server specified in '%s', please contact your admin" % (ds_file_name)
        sys.exit(1)
    print "functionality not ready, please contact lang-nevyjel@init.at"
    sys.exit(0)
    if mode == "l":
        errnum = list_mode(dc)
    else:
        print "Operating on user '%s'" % (user_name)
        dc.execute("SELECT u.*, g.* FROM user u, ggroup g WHERE g.ggroup_idx=u.ggroup AND login='%s'" % (user_name))
        if dc.rowcount == 0:
            print "No user named '%s' found in database" % (user_name)
            sys.exit(1)
        elif dc.rowcount > 1:
            print "More than one user named '%s' found in database" % (user_name)
            sys.exit(1)
        user_stuff = dc.fetchone()
        if mode == "i":
            print "User information:"
            out_list = logging_tools.form_list()
            for what, key in [("Login"             , "login"),
                              ("User ID"           , "uid"),
                              ("Primary Group Name", "ggroupname"),
                              ("Group ID"          , "gid"),
                              ("first name"        , "uservname"),
                              ("second name"       , "usernname"),
                              ("title"             , "usertitan")]:
                out_list.add_line(("  %s" % (what), " : ", user_stuff[key] or "<not set>"))
            print out_list
            errnum = 0
        else:
            print "Change password"
            if os.getuid():
                # ask old password if not root
                old_passwd = get_pass("please enter old password>")
                if crypt.crypt(old_passwd, user_stuff["password"]) != user_stuff["password"]:
                    print "Wrong password, exiting ..."
                    sys.exit(1)
            ok = False
            while not ok:
                new_passwd = get_pass("please enter new password>")
                if len(new_passwd) < 6:
                    print "minimum 6 characters"
                else:
                    ok = True
            new_passwd_check = get_pass("please enter new password again>")
            if new_passwd != new_passwd_check:
                print "The passwords do not match, exiting ..."
                sys.exit(1)
            new_hash = crypt.crypt(new_passwd,
                                   "".join([chr(random.randint(97, 122)) for x in range(16)]))
            print "Updating database..."
            dc.execute("UPDATE user SET password=%s WHERE login=%s", (new_hash,
                                                                      user_name))
            print "Signaling server..."
            if ds_type == "yp":
                send_com = server_command.server_command(command="write_yp_config")
            elif ds_type == "ldap":
                send_com = server_command.server_command(command="sync_ldap_config")
            else:
                print "Unknown directory_server_type '%s'" % (ds_type)
                errnum = 1
                send_com = None
            if send_com:
                errnum, data = net_tools.single_connection(host=ds_name,
                                                           port=8004,
                                                           command=send_com).iterate()
                try:
                    server_reply = server_command.server_reply(data)
                except ValueError:
                    print "Error: got no valid server_reply (got: '%s')" % (data)
                else:
                    errnum, result = server_reply.get_state_and_result()
                    print "Got [%d]: %s" % (errnum, result)
    dc.release()
    del db_con
    sys.exit(errnum)

if __name__ == "__main__":
    main()

