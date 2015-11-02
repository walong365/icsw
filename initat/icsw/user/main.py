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
import re

from . import logging
from initat.tools import mail_tools, logging_tools


def get_users(cur_opts, log_com):
    from initat.cluster.backbone.models import user
    from django.db.models import Q
    all_users = user.objects.all().select_related("group").order_by("group__groupname", "login")
    if cur_opts.only_active:
        all_users = all_users.filter(
            Q(active=True) &
            Q(group__active=True)
        )
    if cur_opts.user_filter != ".*":
        log_f = re.compile(cur_opts.user_filter)
        all_users = [entry for entry in all_users if log_f.match(entry.login)]
    if cur_opts.group_filter != ".*":
        log_f = re.compile(cur_opts.group_filter)
        all_users = [entry for entry in all_users if log_f.match(entry.group.groupname)]
    print("{} in list".format(logging_tools.get_plural("User", len(all_users))))
    return all_users


def do_mail(cur_opts, log_com):
    if cur_opts.use_db:
        all_users = get_users(cur_opts, log_com)
        all_users = [entry.email for entry in all_users if not entry.email.strip() and entry.email.count("@")]
        cur_opts.to = all_users
        log_com(
            "sending to {}: {}".format(
                logging_tools.get_plural("address", len(all_users)),
                ", ".join(sorted(all_users))
            )
        )
    if not cur_opts.to:
        log_com("no valid target addresses", logging_tools.LOG_LEVEL_ERROR)
        sys.exit(0)
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


def do_list(cur_opts, log_com):
    users = get_users(cur_opts, log_com)
    out_list = logging_tools.new_form_list()
    for _user in users:
        out_list.append(
            [
                logging_tools.form_entry(_user.login, header="login"),
                logging_tools.form_entry(_user.uid, header="uid"),
                logging_tools.form_entry(_user.active, header="active"),
                logging_tools.form_entry(_user.group.groupname, header="group"),
                logging_tools.form_entry(_user.group.gid, header="gid"),
                logging_tools.form_entry(_user.group.active, header="gactive"),
                logging_tools.form_entry(_user.first_name, header="first name"),
                logging_tools.form_entry(_user.last_name, header="last name"),
                logging_tools.form_entry(_user.email, header="email"),
                logging_tools.form_entry(_user.login_count, header="logincount"),
                logging_tools.form_entry(_user.comment, header="comment"),
            ]
        )
    print unicode(out_list)


def do_export(cur_opts, log_com):
    from initat.cluster.backbone.serializers import user_flat_serializer
    from rest_framework.renderers import JSONRenderer
    users = get_users(cur_opts, log_com)
    _exp = JSONRenderer().render(user_flat_serializer(users, many=True).data)
    if cur_opts.export:
        file(cur_opts.export, "wb").write(_exp)
        print("exported dump to {}".format(cur_opts.export))
    else:
        print(_exp)


def user_main(cur_opts):
    log_com = logging.get_logger(cur_opts.logger, all=True)
    if cur_opts.mode == "mail":
        do_mail(cur_opts, log_com)
    elif cur_opts.mode == "list":
        do_list(cur_opts, log_com)
    elif cur_opts.mode == "export":
        do_export(cur_opts, log_com)
    else:
        print("Unknown mode '{}'".format(cur_opts.mode))
