#!/usr/bin/python -Ot
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
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
""" wrapper for openssl_tools """

from initat.cluster_server.config import global_config
from initat.cluster.backbone.models import device
from django.db.models import Q
import cs_base_class
from initat.tools import logging_tools
from initat.tools import openssl_tools
from initat.tools import server_command


def _build_obj(cur_inst, **kwargs):
    obj_dict = {
        "CN": kwargs.get("cn", ""),
        "C": "AT",
        "ST": "Vienna",
        "O": "init.at",  # Informationstechnologie GmbH",
        "emailAddress": "cluster@init.at",
        "days": str(kwargs.get("days", 3650)),
    }
    for key, _value in obj_dict.iteritems():
        _key = "server_key:{}".format(key)
        if _key in cur_inst.srv_com:
            obj_dict[key] = cur_inst.srv_com[_key].text
    return obj_dict


class ca_new(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["ca_name"]

    def _call(self, cur_inst):
        _name = cur_inst.srv_com["server_key:ca_name"].text
        _obj_dict = _build_obj(cur_inst, cn="{}_ca".format(global_config["SERVER_FULL_NAME"]))
        cur_ca = openssl_tools.ca(_name, cur_inst.log)
        if cur_ca.ca_ok:
            cur_inst.srv_com.set_result(
                "CA '{}' already present".format(_name),
                server_command.SRV_REPLY_STATE_WARN,
            )
        else:
            if cur_ca.create(_obj_dict):
                cur_inst.srv_com.set_result(
                    "CA '{}' successfully created in {}".format(_name, cur_ca.ca_dir)
                )
            else:
                cur_inst.srv_com.set_result(
                    "creation of CA went wrong, please check the logs",
                    server_command.SRV_REPLY_STATE_ERROR,
                )


class ca_new_cert(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["ca_name", "cert_file", "ca_mode"]

    def _call(self, cur_inst):
        _name = cur_inst.srv_com["server_key:ca_name"].text
        _file_name = cur_inst.srv_com["server_key:cert_file"].text
        _ca_mode = cur_inst.srv_com["server_key:ca_mode"].text
        if "server_key:cn" in cur_inst.srv_com:
            _cn = cur_inst.srv_com["server_key:cn"].text
        else:
            _cn = global_config["SERVER_FULL_NAME"]
        if "server_key:add_device" in cur_inst.srv_com:
            _dev_name = cur_inst.srv_com["server_key:add_device"].text
            if _dev_name.count("."):
                _dev = device.objects.get(Q(name=_dev_name.split(".")[0]) & Q(domain_tree_node__full_name=_dev_name.split(".", 1)[1]))
            else:
                _dev = device.objects.get(Q(name=_dev_name))
        else:
            _dev = None
        _obj_dict = _build_obj(cur_inst, cn=_cn)
        cur_ca = openssl_tools.ca(_name, cur_inst.log)
        if not cur_ca.ca_ok:
            cur_inst.srv_com.set_result(
                "CA '{}' is not valid".format(_name),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            additional_args = {}
            if _dev is not None:
                additional_args['device'] = _dev
            if cur_ca.new_cert(_obj_dict, _ca_mode, _file_name, **additional_args):
                cur_inst.srv_com.set_result(
                    "certificate successfully created in {}".format(_file_name)
                )
            else:
                cur_inst.srv_com.set_result(
                    "cannot create new cert, please check logs",
                    server_command.SRV_REPLY_STATE_ERROR,
                )


class ca_revoke_cert(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["ca_name", "cert_serial", "revoke_cause"]

    def _call(self, cur_inst):
        _name = cur_inst.srv_com["server_key:ca_name"].text
        _cert_serial = cur_inst.srv_com["server_key:cert_serial"].text
        _revoke_cause = cur_inst.srv_com["server_key:revoke_cause"].text
        cur_ca = openssl_tools.ca(_name, cur_inst.log)
        if not cur_ca.ca_ok:
            cur_inst.srv_com.set_result(
                "CA '{}' is not valid".format(_name),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            if cur_ca.revoke_cert(_cert_serial, _revoke_cause):
                cur_inst.srv_com.set_result(
                    "certificate {} successfully revoked".format(_cert_serial),
                )
            else:
                cur_inst.srv_com.set_result(
                    "cannot revoke certificate, please check logs",
                    server_command.SRV_REPLY_STATE_ERROR,
                )


class ca_list_certs(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["ca_name"]

    def _call(self, cur_inst):
        _name = cur_inst.srv_com["server_key:ca_name"].text
        cur_ca = openssl_tools.ca(_name, cur_inst.log)
        if cur_ca.ca_ok:
            _certs = cur_ca.db
            cur_inst.srv_com.set_result(
                "found {}: {}".format(
                    logging_tools.get_plural("certificate", len(_certs)),
                    ", ".join(sorted(cur_ca.db.keys())),
                )
            )
            _bldr = cur_inst.srv_com.builder()
            certs = _bldr.certificates()
            for _serial in cur_ca.db:
                _cert = cur_ca.db[_serial]
                certs.append(
                    _bldr.certificate(
                        type=_cert["type"],
                        name=_cert["name"],
                        serial=_cert["serial"],
                        exp_date=cur_ca.db.format_date(_cert["exp_date"]),
                        rev_date=cur_ca.db.format_date(_cert["rev_date"]),
                        rev_cause=_cert["rev_cause"],
                    )
                )
            cur_inst.srv_com[""] = certs
        else:
            cur_inst.srv_com.set_result(
                "CA '{}' is not valid".format(_name),
                server_command.SRV_REPLY_STATE_ERROR,
            )
