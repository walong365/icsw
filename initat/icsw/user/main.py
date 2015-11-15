#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
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
""" user commands for icsw """

from __future__ import print_function

import base64
import bz2
import json
import os
import re
import subprocess
import sys
import termios
import time

from initat.tools import mail_tools, logging_tools, process_tools, server_command, net_tools
from . import logging


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
    if cur_opts.with_email:
        all_users = [entry for entry in all_users if entry.email.strip() and entry.email.count("@")]
    print("{} in list".format(logging_tools.get_plural("User", len(all_users))))
    return all_users


def do_mail(cur_opts, log_com):
    # attention: we call this from send_email.py (located in /opt/cluster/bin), important
    if cur_opts.server_mode and cur_opts.use_db:
        _send_mail = cur_opts.sendit
        all_users = get_users(cur_opts, log_com)
        all_users = [entry.email for entry in all_users if entry.email.strip() and entry.email.count("@")]
    else:
        all_users = cur_opts.to
        _send_mail = True
    if not all_users:
        log_com("no valid target addresses", logging_tools.LOG_LEVEL_ERROR)
        sys.exit(0)
    if not _send_mail:
        print("")
        print("Will not send the email because --sendit is missing !")
        print("")
        print(
            "target list has {:d} entries: {}".format(
                len(all_users),
                ", ".join(sorted(all_users)),
            )
        )
        sys.exit(0)
    else:
        log_com(
            "sending to {}: {}".format(
                logging_tools.get_plural("address", len(all_users)),
                ", ".join(sorted(all_users))
            )
        )
    if not cur_opts.message:
        print("No message given")
        sys.exit(-1)
    message = (" ".join(cur_opts.message)).replace("\\n", "\n").strip()
    my_mail = mail_tools.mail(cur_opts.subject, getattr(cur_opts, "from"), all_users, message)
    my_mail.set_server(cur_opts.server)
    m_stat, m_ret_f = my_mail.send_mail()
    if m_stat:
        log_com(
            "Some error occured sending to {} ({}, {:d}): {}".format(
                ",".join(all_users),
                cur_opts.subject,
                m_stat,
                "\n".join(m_ret_f)
            ),
            logging_tools.LOG_LEVEL_ERROR
        )
    else:
        log_com(
            "Mail successfully sent to {} ({})".format(
                ",".join(all_users),
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
                logging_tools.form_entry(_user.login_fail_count, header="failedcount"),
                logging_tools.form_entry(_user.comment, header="comment"),
            ]
        )
    print(unicode(out_list))


def do_export(cur_opts, log_com):
    from initat.cluster.backbone.serializers import user_flat_serializer, group_flat_serializer
    from rest_framework.renderers import JSONRenderer
    users = get_users(cur_opts, log_com)
    groups = {}
    for _user in users:
        if _user.group_id not in groups:
            groups[_user.group.pk] = _user.group
    _group_exp = JSONRenderer().render(group_flat_serializer(groups.values(), many=True).data)
    _user_exp = JSONRenderer().render(user_flat_serializer(users, many=True).data)
    _exp = json.dumps(
        {
            "version": 1,
            "groups": json.loads(_group_exp),
            "users": json.loads(_user_exp),
        },
        indent=4,
    )
    if cur_opts.export:
        file(cur_opts.export, "wb").write(_exp)
        print("exported dump to {}".format(cur_opts.export))
    else:
        print(_exp)


def do_import(cur_opts, log_com):
    from initat.cluster.backbone.serializers import user_flat_serializer  # , group_flat_serializer
    from initat.cluster.backbone.models import group, home_export_list
    from django.db.models import Q
    if not os.path.exists(cur_opts.export):
        print("import file '{}' not found".format(cur_opts.export))
    _imp = json.loads(file(cur_opts.export, "r").read())
    if "version" in _imp:
        pass
    else:
        _imp = {
            "version": 0,
            "groups": [],
            "users": _imp
        }
    if cur_opts.default_group:
        default_group = group.objects.get(Q(groupname=cur_opts.default_group))
    else:
        default_group = None
    hel = home_export_list()
    exp_dict = hel.exp_dict
    # todo, import groups
    for _user in _imp["users"]:
        data = user_flat_serializer(data=_user)
        if not data.is_valid():
            if "group" in data.errors and default_group:
                _user["group"] = default_group.pk
                data = user_flat_serializer(data=_user)
        if not data.is_valid():
            if "export" in data.errors and len(exp_dict.keys()) == 1:
                _user["export"] = exp_dict.keys()[0]
                data = user_flat_serializer(data=_user)
        if not data.is_valid():
            log_com("")
            log_com("-" * 50)
            log_com("Cannot import user")
            log_com(str(_user))
            log_com("errors:")
            log_com(str(data.errors))
            log_com("-" * 50)
            log_com("")
        else:
            try:
                data.object.save()
            except:
                log_com(
                    u"Cannot create user '{}': {}".format(
                        unicode(data.object),
                        process_tools.get_except_info(),
                    )
                )
            else:
                log_com(
                    "created user '{}'".format(unicode(data.object))
                )


def do_modify(cur_opts, log_com):
    from initat.cluster.backbone.models import device_config
    from django.db.models import Q
    users = get_users(cur_opts, log_com)
    for _user in users:
        if cur_opts.new_export and _user.export_id and _user.export_id != cur_opts.new_export:
            log_com(
                "changing export_id of user '{}' from {:d} to {:d}".format(
                    unicode(_user),
                    _user.export_id,
                    cur_opts.new_export,
                )
            )
            _user.export = device_config.objects.get(Q(pk=cur_opts.new_export))
            _user.save()


def get_quota_str(uqs):
    _info_f = []
    if uqs.bytes_used > uqs.bytes_hard:
        _info_f.append("hard quota violated")
    elif uqs.bytes_used > uqs.bytes_soft:
        _info_f.append("soft quota violated")
    if uqs.bytes_gracetime:
        # seconds
        grace_time = uqs.bytes_gracetime
        cur_time = int(time.time())
        _info_f.append("grace time left is {}".format(logging_tools.get_diff_time_str(grace_time - cur_time)))
    else:
        pass
    return "    {}{} used ({} soft, {} hard)".format(
        "{}; ".format(", ".join(_info_f)) if _info_f else "",
        logging_tools.get_size_str(uqs.bytes_used, True, 1024, True),
        logging_tools.get_size_str(uqs.bytes_soft, True, 1024, True),
        logging_tools.get_size_str(uqs.bytes_hard, True, 1024, True),
    )


def _get_user(user_name):
    from initat.cluster.backbone.models import user
    from django.db.models import Q
    _uo = user.objects
    try:
        _user = _uo.select_related(
            "group"
        ).prefetch_related(
            "user_quota_setting_set__quota_capable_blockdevice__device"
        ).get(
            Q(login=user_name)
        )
    except user.DoesNotExist:
        print("Unknown user '{}'".format(user_name))
        _user = None
    return _user


def do_info(cur_opts, log_com):
    if not cur_opts.username:
        print("No user name given")
        return 1
    _user = _get_user(cur_opts.username)
    _ret_state = 0
    if _user is None:
        _ret_state = 1
    else:
        from initat.cluster.backbone.models import user_quota_setting
        print("")
        print(
            u"User with loginname '{}' (user {}), uid={:d}, group={} (gid={:d})".format(
                _user.login,
                unicode(_user),
                _user.uid,
                unicode(_user.group),
                _user.group.gid,
            )
        )
        num_qs = _user.user_quota_setting_set.all().count()
        if num_qs and cur_opts.system_wide_quota:
            print("")
            print("{} found:".format(logging_tools.get_plural("system-wide quota setting", num_qs)))
            for _qs in _user.user_quota_setting_set.all():
                _bd = _qs.quota_capable_blockdevice
                print(
                    "    device {} ({} on {}): {}".format(
                        unicode(_bd.device.full_name),
                        _bd.block_device_path,
                        _bd.mount_path,
                        get_quota_str(_qs),
                    )
                )
        try:
            _cmd = "quota --show-mntpoint -wp -u {}".format(
                _user.login,
                # os.path.expanduser("~{}".format(_user.login)),
            )
            _res = subprocess.check_output(
                _cmd.split(),
            )
        except subprocess.CalledProcessError as sb_exc:
            _res = sb_exc.output
            # print("error calling '{}': {}".format(_cmd, process_tools.get_except_info()))
            _ret_state = 1
        else:
            _ret_state = 0
        if _res.lower().count("denied"):
            print("    error getting local quotas for {}: {}".format(_user.login, _res))
        else:
            # print _res
            _lines = [_line.strip().split() for _line in _res.split("\n") if _line.strip()]
            _lines = [_line for _line in _lines if len(_line) == 10]
            if _lines:
                print("", "local quota:", sep="\n")
                _line = _lines[-1]
                _bytes_violate = _line[2].count("*") > 0
                _local = user_quota_setting(
                    bytes_used=int(_line[2].replace("*", "")) * 1024,
                    bytes_soft=int(_line[3]) * 1024,
                    bytes_hard=int(_line[4]) * 1024,
                    bytes_gracetime=int(_line[5]),
                )
                print(
                    "    local mountpoint: {}".format(
                        get_quota_str(_local),
                    )
                )
        return _ret_state


def get_pass(prompt=">"):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    passwd = None
    while True:
        try:
            passwd = raw_input(prompt)
        except KeyboardInterrupt:
            print("press <CTRL-d> to exit")
            passwd = ""
        except EOFError:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            print("\nterminating")
            sys.exit(-1)
        else:
            if passwd:
                break
            else:
                print("password is empty")
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print()
    return passwd


def do_chpasswd(cur_opts, log_com):
    srv_com = server_command.srv_command(command="modify_password")
    srv_com["server_key:user_name"] = cur_opts.username
    print("changing password for user '{}'".format(cur_opts.username))
    srv_com["server_key:old_password"] = base64.b64encode(bz2.compress(get_pass("please enter current password:")))
    srv_com["server_key:new_password_1"] = base64.b64encode(bz2.compress(get_pass("please enter the new password:")))
    srv_com["server_key:new_password_2"] = base64.b64encode(bz2.compress(get_pass("please reenter the new password:")))
    _conn = net_tools.zmq_connection(
        "pwd_change_request",
        timeout=cur_opts.timeout,
    )
    _conn.add_connection("tcp://localhost:8004", srv_com, immediate=True)
    _result = _conn.loop()[0]
    _res_str, _res_state = _result.get_log_tuple()
    # _res_str, _res_state = ("ok", logging_tools.LOG_LEVEL_OK)
    print("change gave [{}]: {}".format(logging_tools.get_log_level_str(_res_state), _res_str))
    if _res_state == logging_tools.LOG_LEVEL_OK:
        _conn = net_tools.zmq_connection(
            "ldap_update_request",
            timeout=cur_opts.timeout,
        )
        upd_com = server_command.srv_command(command="sync_ldap_config")
        _conn.add_connection("tcp://localhost:8004", upd_com, immediate=True)
        _res_str, _res_state = _conn.loop()[0].get_log_tuple()
        print(
            "syncing the LDAP tree returned ({}) {}".format(
                logging_tools.get_log_level_str(_res_state),
                _res_str,
            )
        )
    # print(_result.pretty_print())
    return 0


def user_main(cur_opts):
    log_com = logging.get_logger(cur_opts.logger, all=True)
    ret_code = 0
    if cur_opts.mode == "mail":
        do_mail(cur_opts, log_com)
    elif cur_opts.mode == "list":
        do_list(cur_opts, log_com)
    elif cur_opts.mode == "export":
        do_export(cur_opts, log_com)
    elif cur_opts.mode == "import":
        do_import(cur_opts, log_com)
    elif cur_opts.mode == "modify":
        do_modify(cur_opts, log_com)
    elif cur_opts.mode == "info":
        ret_code = max(ret_code, do_info(cur_opts, log_com))
        sys.exit(ret_code)
    elif cur_opts.mode == "chpasswd":
        ret_code = max(ret_code, do_chpasswd(cur_opts, log_com))
        sys.exit(ret_code)
    else:
        log_com("Unknown mode '{}'".format(cur_opts.mode))
