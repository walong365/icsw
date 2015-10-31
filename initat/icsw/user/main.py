#!/usr/bin/python-init -Ot
#
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2001-2004,2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
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

import sys

from . import logging
from initat.tools import mail_tools, logging_tools


def user_main(cur_opts):
    log_com = logging.get_logger(cur_opts.logger, all=True)

    if cur_opts.to_all:
        from initat.cluster.backbone.models import user
        from django.db.models import Q
        all_users = [
            entry for entry in list(
                user.objects.exclude(
                    Q(email='')
                ).filter(
                    Q(active=True) &
                    Q(group__active=True)
                ).values_list("email", flat=True)
            ) if entry.count("@")
        ]
        cur_opts.to = all_users
        log_com(
            "sending to {}: {}".format(
                logging_tools.get_plural("address", len(all_users)),
                ", ".join(sorted(all_users))
            )
        )
    message = (" ".join(cur_opts.message)).replace("\\n", "\n").strip()
    my_mail = mail_tools.mail(cur_opts.subject, getattr(cur_opts, "from"), cur_opts.to, message)
    my_mail.set_server(cur_opts.server)
    m_stat, m_ret_f = my_mail.send_mail()
    if m_stat:
        log_com(
            "Some error occured sending to {} ({}, {:d}): {}".format(
                ",".join(cur_opts.to),
                cur_opts.subject,
                m_stat,
                "\n".join(m_ret_f)
            ),
            logging_tools.LOG_LEVEL_ERROR
        )
    else:
        log_com(
            "Mail successfully sent to {} ({})".format(
                ",".join(cur_opts.to),
                cur_opts.subject,
            )
        )
    sys.exit(m_stat)
