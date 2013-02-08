#!/usr/bin/python-init -Ot
#
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2001,2002,2003,2004,2007,2009 Andreas,2013 Lang-Nevyjel, init.at
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
""" small tool for sending mails via commandline """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import argparse
import mail_tools
import logging_tools

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-f", "--from", type=str, help="from address [%(default)s]", default="root@localhost")
    my_parser.add_argument("-s", "--subject", type=str, help="subject [%(default)s]", default="mailsubject")
    my_parser.add_argument("-m", "--server", type=str, help="mailserver to connect [%(default)s]", default="localhost")
    my_parser.add_argument("-t", "--to", type=str, nargs="*", help="to address [%(default)s]", default="root@localhost")
    my_parser.add_argument("-G", dest="to_all", action="store_true", default=False, help="send mail to all active users [%(default)s]")
    my_parser.add_argument("message", nargs="+", help="message to send")
    cur_opts = my_parser.parse_args()
    if cur_opts.to_all:
        from initat.cluster.backbone.models import user
        from django.db.models import Q
        all_users = [entry for entry in list(user.objects.exclude(Q(email='')).filter(Q(active=True) & Q(group__active=True)).values_list("email", flat=True)) if entry.count("@")]
        cur_opts.to = all_users
        print "sending to %s: %s" % (
            logging_tools.get_plural("address", len(all_users)),
            ", ".join(sorted(all_users)))
    message = (" ".join(cur_opts.message)).replace("\\n", "\n").strip()
    my_mail = mail_tools.mail(cur_opts.subject, getattr(cur_opts, "from"), cur_opts.to, message)
    my_mail.set_server(cur_opts.server)
    m_stat, m_ret_f = my_mail.send_mail()
    if m_stat:
        print "Some error occured (%d): %s" % (
            m_stat,
            "\n".join(m_ret_f))
    else:
        print "Mail successfully sent"
    sys.exit(m_stat)

if __name__ == "__main__":
    main()
    
