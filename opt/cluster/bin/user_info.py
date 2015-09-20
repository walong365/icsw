#!/usr/bin/python-init -Ot
#
# Copyright (C) 2005-2008,2015 Andreas Lang-Nevyjel, init.at
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

from __future__ import print_function
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

django.setup()

from django.db.models import Q
from initat.cluster.backbone.models import user, user_quota_setting
import argparse
from initat.tools import logging_tools, net_tools, server_command
import pwd
import bz2
import base64
import subprocess
import sys
import termios
import time


def list_mode(options):
    all_users = user.objects.all().select_related("group").order_by("login")  # @UndefinedVariable
    out_list = logging_tools.new_form_list()
    for _user in all_users:
        out_list.append(
            [
                logging_tools.form_entry(_user.login, header="login"),
                logging_tools.form_entry(_user.uid, header="uid"),
                logging_tools.form_entry(_user.group.gid, header="gid"),
                logging_tools.form_entry(_user.group.groupname, header="group"),
            ]
        )
    print(unicode(out_list))
    return 0


def _get_user(user_name):
    _uo = user.objects  # @UndefinedVariable
    try:
        _user = _uo.select_related(
            "group"
        ).prefetch_related(
            "user_quota_setting_set__quota_capable_blockdevice__device"
        ).get(
            Q(login=user_name)
        )
    except user.DoesNotExist:  # @UndefinedVariable
        print("Unknown user '{}'".format(user_name))
        _user = None
    return _user


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


def info_mode(options, user_name):
    _user = _get_user(user_name)
    _ret_state = 0
    if _user is None:
        _ret_state = 1
    else:
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
        if num_qs and options.system_wide_quota:
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


def modify_password(options):
    srv_com = server_command.srv_command(command="modify_password")
    srv_com["server_key:user_name"] = options.username
    print("changing password for user '{}'".format(options.username))
    srv_com["server_key:old_password"] = base64.b64encode(bz2.compress(get_pass("please enter current password:")))
    srv_com["server_key:new_password_1"] = base64.b64encode(bz2.compress(get_pass("please enter the new password:")))
    srv_com["server_key:new_password_2"] = base64.b64encode(bz2.compress(get_pass("please reenter the new password:")))
    _conn = net_tools.zmq_connection(
        "pwd_change_request",
        timeout=options.timeout,
    )
    _conn.add_connection("tcp://localhost:8004", srv_com, immediate=True)
    _result = _conn.loop()[0]
    _res_str, _res_state = _result.get_log_tuple()
    # _res_str, _res_state = ("ok", logging_tools.LOG_LEVEL_OK)
    print("change gave [{}]: {}".format(logging_tools.get_log_level_str(_res_state), _res_str))
    if _res_state == logging_tools.LOG_LEVEL_OK:
        _conn = net_tools.zmq_connection(
            "ldap_update_request",
            timeout=options.timeout,
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


def main():
    _user_name = pwd.getpwuid(os.getuid())[0]
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--mode", dest="mode", choices=["info", "list", "change"], default="info", help="set mode [%(default)s]")
    my_parser.add_argument("-Q", "--system-wide-quota", default=False, action="store_true", help="show system-wide quota [%(default)s]")
    my_parser.add_argument(
        "--username",
        default=_user_name,
        choices=user.objects.filter(Q(active=True) & Q(group__active=True)).values_list("login", flat=True),
        help="set username [%(default)s]"
    )
    my_parser.add_argument("--timeout", default=10, type=int, help="timeout for server connections [%(default)d]")
    options = my_parser.parse_args()
    if options.mode in ["info", "change"] and not options.username:
        print("Need username for {} mode".format(options.mode))
        sys.exit(-1)
    if options.mode == "list":
        ret_code = list_mode(options)
    elif options.mode == "info":
        ret_code = 0
        _user = options.username
        ret_code = max(ret_code, info_mode(options, _user))
    elif options.mode == "change":
        ret_code = modify_password(options)
    else:
        ret_code = 1
    sys.exit(ret_code)


if __name__ == "__main__":
    main()
