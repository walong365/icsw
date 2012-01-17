#!/usr/bin/python-init -Ot
#
# Copyright (c) 2001,2002,2003,2004,2007,2009 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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

import sys
import getopt
import process_tools
import mail_tools
import logging_tools

def main():
    try:
        args, opts = getopt.getopt(sys.argv[1:], "hf:t:s:m:G", ["help"])
    except:
        print "Error parsing options %s: %s" % (" ".join(sys.argv[1:]), process_tools.get_except_info())
        sys.exit(2)
    from_addr, subject, mailserver, to_addrs, group_mail = ("root@localhost", "unknown", "localhost", [], [])
    for arg, opt in args:
        if arg in ["-h", "--help"]:
            print "Usage: %s [ -h|--help] [ -f FROMADDR ] [ -s SUBJECT ] [ -m MAILSERVER ] [ -t TOADDR|-G ] MESSAGE" % (sys.argv[0])
            print "  default for FROMADDR is %s" % (from_addr)
            print "  default for SUBJECT is %s" % (subject)
            print "  default for MAILSERVER is %s" % (mailserver)
            print "  -G sends mail to all valid users found in Database"
            sys.exit(0)
        if arg == "-f":
            from_addr = opt
        if arg == "-t":
            to_addrs = [x.strip() for x in opt.split(",")]
        if arg == "-s":
            subject = opt
        if arg == "-m":
            mailserver = opt
        if arg == "-G":
            try:
                import mysql_tools
                import MySQLdb
            except ImportError:
                print "No mysql_tools found, exiting ..."
                sys.exit(1)
            else:
                db_con = mysql_tools.dbcon_container(with_logging=False)
                try:
                    dc = db_con.get_connection("cluster_full_access")
                except:
                    print "Cannot connect to SQL-Server (%s)" % (process_tools.get_except_info())
                    sys.exit(1)
                dc.execute("SELECT u.login,u.useremail FROM user u WHERE u.useremail LIKE('%@%')")
                user_dict = dict([(x["login"], x["useremail"]) for x in dc.fetchall()])
                dc.release()
                if user_dict:
                    user_list = sorted(user_dict.keys())
                    print "Sending mail to %s: %s" % (logging_tools.get_plural("user", len(user_list)),
                                                      ", ".join(user_list))
                    to_addrs = user_dict.values()
                else:
                    print "No users found, exiting ..."
                    sys.exit(0)
    if not opts:
        try:
            stdin_str = sys.stdin.read()
        except:
            stdin_str = ""
    else:
        stdin_str = ""
    message = ("%s %s" % ((" ".join(opts)).replace("\\n", "\n"), stdin_str)).strip()
    if not to_addrs:
        print "To-address(es) missing, exiting..."
        sys.exit(2)
    if not len(message):
        print "Need message text, exiting..."
        sys.exit(2)
    my_mail = mail_tools.mail(subject, from_addr, to_addrs, message)
    my_mail.set_server(mailserver)
    m_stat, m_ret_f = my_mail.send_mail()
    if m_stat:
        print "Some error occured (%d): %s" % (m_stat,
                                               "\n".join(m_ret_f))
    else:
        print "Mail successfully sent"
    sys.exit(m_stat)

if __name__ == "__main__":
    main()
    
