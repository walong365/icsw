# Copyright (C) 2015 Andreas Lang-Nevyjel
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
""" modifies password for a given user """

from django.db.models import Q
from django.contrib.auth import authenticate
from initat.cluster.backbone.models import user
from initat.cluster_server.config import global_config
from initat.tools import config_tools
import base64
import bz2
import cs_base_class
import os
from initat.tools import process_tools
from initat.tools import server_command


class modify_password(cs_base_class.server_com):
    class Meta:
        needed_configs = []
        needed_option_keys = ["user_name", "old_password", "new_password_1", "new_password_2"]

    def _call(self, cur_inst):
        opt_dict = {
            _key: cur_inst.srv_com["*server_key:{}".format(_key)] for _key in self.Meta.needed_option_keys
        }
        _data_ok = True
        for _c_key in [_key for _key in self.Meta.needed_option_keys if _key.count("password")]:
            try:
                opt_dict[_c_key] = bz2.decompress(base64.b64decode(opt_dict[_c_key]))
            except:
                cur_inst.srv_com.set_result(
                    "invalid data received",
                    server_command.SRV_REPLY_STATE_CRITICAL,
                )
                _data_ok = False
        if _data_ok:
            if opt_dict["new_password_1"] != opt_dict["new_password_2"]:
                cur_inst.srv_com.set_result(
                    "the new passwords do not match",
                    server_command.SRV_REPLY_STATE_ERROR
                )
            elif opt_dict["old_password"] == opt_dict["new_password_1"]:
                cur_inst.srv_com.set_result(
                    "the new password is the same as the old one",
                    server_command.SRV_REPLY_STATE_ERROR
                )
            else:
                try:
                    cur_user = user.objects.get(Q(login=opt_dict["user_name"]))
                except user.DoesNotExist:
                    cur_inst.srv_com.set_result(
                        "user '{}' does not exist".format(opt_dict["user_name"]),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                else:
                    if authenticate(username=opt_dict["user_name"], password=opt_dict["old_password"]):
                        cur_user.password = opt_dict["new_password_1"]
                        # update password
                        cur_user.save()
                        cur_inst.srv_com.set_result(
                            "password sucessfully changed",
                        )
                    else:
                        cur_inst.srv_com.set_result(
                            "wrong old password given",
                            server_command.SRV_REPLY_STATE_ERROR
                        )
