#
# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" HardwareFingerPrintTools """

import netifaces

from django.db.models import Q

from initat.cluster.backbone.models import HardwareFingerPrint, device
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.backbone.models.functions import memoize_with_expiry


def create_db_entry(device_obj, hfp):
    _ser = HardwareFingerPrint.serialize(hfp)
    try:
        cur_hfp = HardwareFingerPrint.objects.get(
            Q(device=device_obj)
        )
    except HardwareFingerPrint.DoesNotExist:
        cur_hfp = HardwareFingerPrint.objects.create(
            device=device_obj,
            fingerprint=_ser,
        )
    else:
        if _ser != cur_hfp.fingerprint:
            cur_hfp.update(_ser)
    return cur_hfp


@memoize_with_expiry(expiry_time=10)
def get_server_fp(serialize=False):
    _devs_with_server = {
        _dev.pk: _dev for _dev in device.objects.filter(
            Q(
                device_config__config__config_service_enum__enum_name=icswServiceEnum.cluster_server.name
            )
        ).select_related(
            "domain_tree_node",
        ).prefetch_related(
            "hardwarefingerprint_set",
        ).all()
    }
    _s_dict = {}
    for _dev in _devs_with_server.values():
        _s_dict[_dev.pk] = {
            "name": _dev.full_name,
            "fingerprints": [
                _fp.fingerprint for _fp in _dev.hardwarefingerprint_set.all()
            ],
            "pk": _dev.pk
        }
    if serialize:
        # return an ascii-decoded string
        return HardwareFingerPrint.serialize(_s_dict).decode("ascii")
    else:
        return _s_dict


def server_dict_is_valid(s_dict):
    # returns state and log string
    _valid = False
    _logs = []
    if not len(s_dict):
        _logs.append("No servers found")
    else:
        _valid = True
        for _srv in s_dict.values():
            _num_fp = len(_srv["fingerprints"])
            if not _num_fp:
                _logs.append(
                    "server '{}' has no valid fingerprint".format(
                        _srv["name"]
                    )
                )
                _valid = False
            elif _num_fp > 1:
                _logs.append(
                    "server '{}' has {:d} fingerprints".format(
                        _srv["name"],
                        _num_fp
                    )
                )
                _valid = False
    if _valid:
        _logs.append("Server Fingerprint is valid")
    else:
        _logs.insert(0, "Server Fingerprint is invalid, license will not be permanent")
    return _valid, ", ".join(_logs)


def get_local_hfp(serialize=False):
    _rd = {
        "net": get_local_net_hfp()
    }
    if serialize:
        _rd = HardwareFingerPrint.serialize(_rd)
    return _rd


def get_local_net_hfp():
    _ifaces = netifaces.interfaces()
    _if_dict = {}
    for _if_name in _ifaces:
        if _if_name.startswith("lo"):
            continue
        _if = netifaces.ifaddresses(_if_name)
        if netifaces.AF_LINK in _if and netifaces.AF_INET in _if:
            _if_dict[_if_name] = _if
    _gw_info = netifaces.gateways()
    if "default" in _gw_info and netifaces.AF_INET in _gw_info["default"]:
        _inet_gw = _gw_info["default"][netifaces.AF_INET]
        _gw_dev = _inet_gw[1]
    else:
        _gw_dev = None
    if _gw_dev in _if_dict:
        # hfp is mac of gateway
        hw_fp_dev = _gw_dev
    else:
        hw_fp_dev = sorted(_if_dict.keys())[0]
    # print("*", _gw_dev, _if_dict)
    if hw_fp_dev:
        fp = {
            "name": hw_fp_dev,
            "value": _if_dict[hw_fp_dev][netifaces.AF_LINK][0]["addr"],
        }
    else:
        fp = {}
    return fp


if __name__ == "__main__":
    print(get_local_hfp())
