# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" device views """

from __future__ import unicode_literals, print_function

import datetime
import json
import logging
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Max
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework import viewsets, status
from rest_framework.response import Response

from initat.cluster.backbone.models import device_group, device, \
    cd_connection, domain_tree_node, netdevice, ComCapability, \
    partition_table, monitoring_hint, DeviceSNMPInfo, snmp_scheme, \
    domain_name_tree, net_ip, peer_information, mon_ext_host, device_variable, \
    SensorThreshold, package_device_connection, DeviceDispatcherLink, AssetRun, \
    DeviceScanLock, device_variable_scope, StaticAsset, DeviceClass, \
    dvs_allowed_name
from initat.cluster.backbone.models import get_change_reset_list, DeviceLogEntry
from initat.cluster.backbone.models.functions import can_delete_obj
from initat.cluster.backbone.render import permission_required_mixin
from initat.cluster.backbone.serializers import netdevice_serializer, ComCapabilitySerializer, \
    partition_table_serializer, monitoring_hint_serializer, DeviceSNMPInfoSerializer, \
    snmp_scheme_serializer, device_variable_serializer, cd_connection_serializer, \
    SensorThresholdSerializer, package_device_connection_serializer, DeviceDispatcherLinkSerializer, \
    AssetRunSimpleSerializer, ShallowPastAssetBatchSerializer, DeviceScanLockSerializer, \
    device_variable_scope_serializer, StaticAssetSerializer, DeviceClassSerializer, \
    dvs_allowed_name_serializer, DeviceLogEntrySerializer
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server

logger = logging.getLogger("cluster.device")


class change_devices(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        c_dict = json.loads(_post.get("change_dict", ""))
        pk_list = json.loads(_post.get("device_list"))
        if c_dict.get("delete", False):
            num_deleted = 0
            error_msgs = []
            for pk in pk_list:
                obj = device.objects.get(Q(pk=pk))
                can_delete_answer = can_delete_obj(obj, logger)
                if can_delete_answer:
                    obj.delete()
                    num_deleted += 1
                else:
                    error_msgs.append((obj.name, can_delete_answer.msg))
            if num_deleted > 0:
                request.xml_response.info("delete {}".format(logging_tools.get_plural("device", num_deleted)))
            for pk, msg in error_msgs:
                request.xml_response.error("Failed to delete {}: {}".format(pk, msg))
        else:
            def_dict = {
                "bootserver": None,
                "monitor_server": None,
                "enabled": False,
                "store_rrd_data": False,
                "enable_perfdata": False,
            }
            # build change_dict
            c_dict = {
                key[7:]: c_dict.get(key[7:], def_dict.get(key[7:], None)) for key in c_dict.iterkeys() if key.startswith("change_") and c_dict[key]
            }
            # resolve foreign keys
            res_c_dict = {
                key: {
                    "device_group": device_group,
                    "device_class": DeviceClass,
                    "domain_tree_node": domain_tree_node,
                    "bootserver": device,
                    "monitor_server": device,
                }[key].objects.get(
                    Q(pk=value)
                ) if type(value) == int else value for key, value in c_dict.iteritems()
            }
            logger.info("change_dict has {}".format(logging_tools.get_plural("key", len(res_c_dict))))
            for key in sorted(res_c_dict):
                if key == "root_passwd":
                    logger.info(" {}: {}".format(key, "****"))
                else:
                    logger.info(" {}: {}".format(key, unicode(res_c_dict.get(key))))
            dev_changes = 0
            changes_json = []
            for cur_dev in device.objects.filter(Q(pk__in=pk_list)):
                changed = False
                for c_key, c_value in res_c_dict.iteritems():
                    if getattr(cur_dev, c_key) != c_value:
                        if c_key == "root_passwd":
                            c_value = cur_dev.crypt(c_value)
                            if c_value:
                                setattr(cur_dev, c_key, c_value)
                                changed = True
                        else:
                            setattr(cur_dev, c_key, c_value)
                            changes_json.append(
                                {
                                    "device": cur_dev.pk,
                                    "attribute": c_key,
                                    "value": c_dict[c_key],
                                }
                            )
                            changed = True

                if changed:
                    cur_dev.save()
                    dev_changes += 1
            request.xml_response["changed"] = dev_changes
            request.xml_response["json_changes"] = json.dumps(changes_json)
            request.xml_response.info("changed settings of {}".format(logging_tools.get_plural("device", dev_changes)))


class select_parents(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        cur_sel = json.loads(_post["angular_sel"])
        devs = device.all_real_enabled.filter(Q(pk__in=cur_sel))
        cd_pks = list(
            device.all_real_enabled.filter(
                (
                    Q(com_capability_list__matchcode="ipmi") |
                    Q(snmp_schemes__power_control=True)
                ) & Q(master_connections__in=devs)
            ).values_list("pk", flat=True)
        )
        _res = {
            "cd_pks": cd_pks,
            "new_selection": list(set(cur_sel) | set(cd_pks))
        }
        return HttpResponse(json.dumps(_res), content_type="application/json")


class manual_connection(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        re_dict = {
            "source": _post["source"],
            "target": _post["target"],
        }
        t_type = _post["mode"]
        logger.info("mode is '%s', source_str is '%s', target_str is '%s'" % (
            t_type,
            re_dict["source"],
            re_dict["target"]))
        # # (hash) is our magic sign for \d
        for key in re_dict.keys():
            val = re_dict[key]
            if val.count("#"):
                parts = val.split("#")
                val = ("(%s)(%s)(%s)" % (parts[0], "#" * (len(parts) - 1), parts[-1])).replace("()", "").replace("#", "\d")
            re_dict[key] = re.compile("^%s$" % (val))
        # all cd / non-cd devices
        # FIXME
        cd_devices = device.all_real_enabled.filter(
            Q(com_capability_list__matchcode="ipmi") |
            Q(snmp_schemes__power_control=True)
        )
        # print cd_devices
        non_cd_devices = device.all_real_enabled.all()
        logger.info("cd / non-cd devices: {:d} / {:d}".format(cd_devices.count(), non_cd_devices.count()))
        # iterate over non-cd-device
        # pprint.pprint(re_dict)
        match_dict = {}
        for key, dev_list in [
            ("source", cd_devices),
            ("target", non_cd_devices)
        ]:
            match_dict[key] = {}
            for cur_dev in dev_list:
                cur_m = re_dict[key].match(cur_dev.name)
                if cur_m and cur_m.groups():
                    d_key = cur_m.groups()[1]
                    if d_key.isdigit():
                        d_key = int(d_key)
                    match_dict[key][d_key] = (cur_m.groups(), cur_dev)
        # matching keys
        m_keys = set(match_dict["source"].keys()) & set(match_dict["target"].keys())
        logger.info(
            "{}: {}".format(
                logging_tools.get_plural("matching key", len(m_keys)),
                ", ".join(sorted([str(key) for key in m_keys]))
            )
        )
        created_cons = []
        for m_key in m_keys:
            new_cd = cd_connection(
                parent=match_dict["target" if t_type == "slave" else "source"][m_key][1],
                child=match_dict["source" if t_type == "slave" else "target"][m_key][1],
                created_by=request.user,
                connection_info="manual"
            )
            try:
                new_cd.save()
            except ValidationError:
                request.xml_response.error("error creating: {}".format(process_tools.get_except_info()), logger)
                for del_cd in created_cons:
                    del_cd.delete()
            else:
                created_cons.append(new_cd)
        if m_keys:
            if created_cons:
                request.xml_response.info("created {}".format(logging_tools.get_plural("connection", len(m_keys))), logger)
        else:
            request.xml_response.warn("found no matching devices", logger)


class scan_device_network(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _json_dev = json.loads(request.POST["settings"])
        # copy address
        _json_dev["scan_address"] = _json_dev["manual_address"]
        _dev = device.objects.get(Q(pk=_json_dev["device"]))
        _sm = _json_dev["scan_mode"]
        logger.info("scanning network settings of device {} via {}".format(unicode(_dev.full_name), _sm))
        if _sm == "hm":
            srv_com = server_command.srv_command(command="scan_network_info")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                    "scan_address": _json_dev["scan_address"],
                    "strict_mode": "1" if _json_dev["strict_mode"] else "0",
                    "modify_peering": "1" if _json_dev["modify_peering"] else "0",
                }
            )
            srv_com["devices"] = _dev_node
        elif _sm == "snmp":
            srv_com = server_command.srv_command(command="snmp_basic_scan")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                    "scan_address": _json_dev["scan_address"],
                    "snmp_version": "{}".format(_json_dev["snmp_version"]),
                    "snmp_community": _json_dev["snmp_community"],
                    "strict": "1" if _json_dev["remove_not_found"] else "0",
                    "modify_peering": "1" if _json_dev["modify_peering"] else "0",
                }
            )
            srv_com["devices"] = _dev_node
        elif _sm == "base":
            srv_com = server_command.srv_command(command="base_scan")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                }
            )
            if _json_dev["scan_address"] != "":
                _dev_node.attrib.update(
                    {
                        "scan_address": _json_dev["scan_address"],
                    }
                )
            srv_com["devices"] = _dev_node
        elif _sm == "wmi":
            srv_com = server_command.srv_command(command="wmi_scan")
            _dev_node = srv_com.builder("device")
            _dev_node.attrib.update(
                {
                    "pk": "{:d}".format(_dev.pk),
                    "scan_address": _json_dev["scan_address"],
                    "username": _json_dev["wmi_username"],
                    "password": _json_dev["wmi_password"],
                    "discard_disabled_interfaces": "1" if _json_dev["wmi_discard_disabled_interfaces"] else "0",
                }
            )
            srv_com["devices"] = _dev_node
        else:
            srv_com = None
            request.xml_response.error("invalid scan type {}".format(_sm))
        if srv_com is not None:
            _result = contact_server(request, icswServiceEnum.discovery_server, srv_com, timeout=30)


class get_device_location(View):
    @method_decorator(login_required)
    def get(self, request):
        if "devices" in request.GET:
            _dev_pks = json.loads(request.GET["devices"])
            _mapping_list = list(category.objects.filter(Q(device__in=_dev_pks) & Q(full_name__startswith="/location/")).values_list("device__pk", "pk"))
        else:
            _mapping_list = list(category.objects.filter(Q(full_name__startswith="/location/")).values_list("device__pk", "pk"))
        return HttpResponse(json.dumps(_mapping_list), content_type="application/json")


class GetMatchingDevices(View):
    """ Search for device by ip or mac """
    @method_decorator(login_required)
    def post(self, request):
        search_str = request.POST['search_str']
        result = device.objects.filter(
            Q(netdevice__macaddr__startswith=search_str) | Q(netdevice__net_ip__ip__startswith=search_str)
        ).values_list('pk', flat=True)
        return HttpResponse(json.dumps(list(result)), content_type="application/json")


class EnrichmentObject(object):
    def __init__(self, base_object, serializer, related_name="device", prefetch_list=[], related_list=[]):
        self.base_object = base_object
        self.serializer = serializer
        self.related_name = related_name
        self.prefetch_list = prefetch_list
        self.related_list = related_list

    def fetch(self, pk_list):
        _result = self.base_object.objects.filter(
            Q(
                **{
                    "{}__in".format(self.related_name): pk_list
                }
            )
        ).prefetch_related(
            *self.prefetch_list
        ).select_related(
            *self.related_list
        )
        # create data
        _data = self.serializer(_result, many=True).data
        return _data


class ComCapabilityEnrichment(object):
    def fetch(self, pk_list):
        # get reference list
        _ref_list = ComCapability.objects.filter(
            Q(device__in=pk_list)
        ).values("pk", "device__pk")
        # simple result
        _result = {
            _el.pk: _el for _el in ComCapability.objects.filter(
                Q(device__in=pk_list)
            )
        }
        # manually unroll n2m relations
        _data = [
            ComCapabilitySerializer(
                _result[_ref["pk"]],
                context={"device": _ref["device__pk"]}
            ).data for _ref in _ref_list
        ]
        return _data


class SNMPSchemeEnrichment(object):
    def fetch(self, pk_list):
        # get reference list
        _ref_list = snmp_scheme.objects.filter(
            Q(device__in=pk_list)
        ).values("pk", "device__pk")
        # simple result
        _result = {
            _el.pk: _el for _el in snmp_scheme.objects.filter(
                Q(device__in=pk_list)
            ).prefetch_related(
                "snmp_scheme_tl_oid_set",
            ).select_related(
                "snmp_scheme_vendor",
            )
        }
        # manually unroll n2m relations
        _data = [
            snmp_scheme_serializer(
                _result[_ref["pk"]],
                context={"device": _ref["device__pk"]}
            ).data for _ref in _ref_list
        ]
        return _data


class DiskEnrichment(object):
    def fetch(self, pk_list):
        # get reference list
        _ref_list = partition_table.objects.filter(
            Q(act_partition_table__in=pk_list)
        ).values("pk", "act_partition_table__pk")
        # simple result
        _result = {
            _el.pk: _el for _el in partition_table.objects.filter(
                Q(act_partition_table__in=pk_list)
            ).prefetch_related(
                "partition_disc_set",
                "partition_disc_set__partition_set",
                "partition_disc_set__partition_set__partition_fs",
                "sys_partition_set",
            )
        }
        # manually unroll n2m relations
        _data = [
            partition_table_serializer(
                _result[_ref["pk"]],
                context={"device": _ref["act_partition_table__pk"]}
            ).data for _ref in _ref_list
        ]
        return _data


class StaticAssetEnrichment(object):
    def fetch(self, pk_list):
        # get reference list
        _ref_list = StaticAsset.objects.filter(
            Q(device__in=pk_list)
        ).prefetch_related(
            "staticassetfieldvalue_set"
        )
        _data = StaticAssetSerializer(_ref_list, many=True).data
        return _data


class AssetEnrichment(object):
    def fetch(self, pk_list):
        # get reference list
        _ref_list = AssetRun.objects.filter(
            Q(device__in=pk_list)
        ).values("pk", "device__pk")
        _result = {
            _el.pk: _el for _el in AssetRun.objects.filter(
                Q(device__in=pk_list)
            )
        }
        # manually unroll n2m relations
        _data = [
            AssetRunSimpleSerializer(
                _result[_ref["pk"]],
                context={"device": _ref["device__pk"]}
            ).data for _ref in _ref_list
        ]
        return _data


class PastAssetrunEnrichment(object):
    def fetch(self, pk_list):
        _now = timezone.now()
        _result = AssetBatch.objects.filter(
            Q(device__in=pk_list) &
            Q(run_start_time__gt=_now - datetime.timedelta(days=1))
        )
        # manually unroll n2m relations
        _data = [
            ShallowPastAssetBatchSerializer(_ab).data for _ab in _result
        ]
        return _data


class DeviceConnectionEnrichment(object):
    def fetch(self, pk_list):
        _ref_list = cd_connection.objects.filter(
            Q(child__in=pk_list) | Q(parent__in=pk_list)
        )
        # result dict
        _data = [
            cd_connection_serializer(
                _cd,
            ).data for _cd in _ref_list
        ]
        return _data


class ScanLockEnrichment(object):
    def fetch(self, pk_list):
        _res = DeviceScanLock.objects.filter(
            Q(device__in=pk_list) & Q(active=True)
        )
        _data = [
            DeviceScanLockSerializer(
                _sl,
            ).data for _sl in _res
        ]
        return _data


class SensorThresholdEnrichment(object):
    def fetch(self, pk_list):
        _res = SensorThreshold.objects.filter(
            Q(mv_value_entry__mv_struct_entry__machine_vector__device__in=pk_list)
        ).annotate(
            device=Max("mv_value_entry__mv_struct_entry__machine_vector__device_id")
        )
        _data = [
            SensorThresholdSerializer(
                _cd,
                context={"device": _cd.device}
            ).data for _cd in _res
        ]
        return _data


class EnrichmentHelper(object):
    def __init__(self):
        self._all = {}
        self._all["network_info"] = EnrichmentObject(
            netdevice,
            netdevice_serializer,
            prefetch_list=["net_ip_set"]
        )
        self._all["disk_info"] = DiskEnrichment()
        self._all["com_info"] = ComCapabilityEnrichment()
        self._all["snmp_info"] = EnrichmentObject(DeviceSNMPInfo, DeviceSNMPInfoSerializer)
        self._all["snmp_schemes_info"] = SNMPSchemeEnrichment()
        self._all["monitoring_hint_info"] = EnrichmentObject(monitoring_hint, monitoring_hint_serializer)
        self._all["scan_lock_info"] = ScanLockEnrichment()
        self._all["variable_info"] = EnrichmentObject(device_variable, device_variable_serializer)
        self._all["device_connection_info"] = DeviceConnectionEnrichment()
        self._all["sensor_threshold_info"] = SensorThresholdEnrichment()
        self._all["package_info"] = EnrichmentObject(package_device_connection, package_device_connection_serializer)
        self._all["dispatcher_info"] = EnrichmentObject(DeviceDispatcherLink, DeviceDispatcherLinkSerializer)
        self._all["asset_info"] = AssetEnrichment()
        self._all["past_assetrun_info"] = PastAssetrunEnrichment()
        self._all["static_asset_info"] = StaticAssetEnrichment()

    def create(self, key, pk_list):
        if key not in self._all:
            _error = "Unknown Enrichment type {}".format(key)
            raise KeyError(_error)
        else:
            return self._all[key].fetch(pk_list)


_my_en_helper = EnrichmentHelper()


class EnrichDevices(View):
    """ Returns enrichment info for the webfrontend """

    @method_decorator(login_required)
    def post(self, request):
        _req = json.loads(request.POST["enrich_request"])
        # pprint.pprint(_req)
        result = {}
        for en_key, pk_list in _req.iteritems():
            # iterate over enrichment info
            result[en_key] = _my_en_helper.create(en_key, pk_list)
        # pprint.pprint(result)
        return HttpResponse(json.dumps(result), content_type="application/json")


class DeviceListInfo(View):
    @method_decorator(login_required)
    def post(self, request):
        _pk_list = json.loads(request.POST["pk_list"])
        # _pk_list = json.loads()
        if _pk_list:
            _dev_names = [
                _dev.full_name for _dev in device.objects.filter(Q(pk__in=_pk_list)).select_related("domain_tree_node")
            ]
            _response_str = "{}: {}".format(
                logging_tools.get_plural("device", len(_dev_names)),
                logging_tools.reduce_list(_dev_names)
            )
        else:
            _response_str = "no devices selected"
        return HttpResponse(
            json.dumps({"header": _response_str}),
            content_type="application/json"
        )


class create_device(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_tree"]

    @method_decorator(login_required)
    def get(self, request):
        pass

    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        # domain name tree
        dnt = domain_name_tree()
        device_data = json.loads(_post["device_data"])
        try:
            cur_dg = device_group.objects.get(Q(name=device_data["device_group"]))
        except device_group.DoesNotExist:
            try:
                cur_dg = device_group.objects.create(
                    name=device_data["device_group"],
                    domain_tree_node=dnt.get_domain_tree_node(""),
                    description="auto created device group {}".format(device_data["device_group"]),
                )
            except:
                request.xml_response.error(
                    u"cannot create new device group: {}".format(
                        process_tools.get_except_info()
                    ),
                    logger=logger
                )
                cur_dg = None
            else:
                request.xml_response.info(u"created new device group '{}'".format(unicode(cur_dg)), logger=logger)
        else:
            if cur_dg.cluster_device_group:
                request.xml_response.error(
                    u"no devices allowed in system (cluster) group",
                    logger=logger
                )
                cur_dg = None
        _create_ok = True
        if cur_dg is not None:
            if device_data["full_name"].count("."):
                short_name, domain_name = device_data["full_name"].split(".", 1)
                dnt_node = dnt.add_domain(domain_name)
            else:
                short_name = device_data["full_name"]
                # top level node
                dnt_node = dnt.get_domain_tree_node("")
            try:
                cur_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node=dnt_node))
            except device.DoesNotExist:
                # check image
                if device_data["icon_name"].strip():
                    try:
                        cur_img = mon_ext_host.objects.get(Q(name=device_data["icon_name"]))
                    except mon_ext_host.DoesNotExist:
                        cur_img = None
                    else:
                        pass
                try:
                    cur_dev = device.objects.create(
                        device_group=cur_dg,
                        is_meta_device=False,
                        domain_tree_node=dnt_node,
                        name=short_name,
                        mon_resolve_name=device_data["resolve_via_ip"],
                        comment=device_data["comment"],
                        mon_ext_host=cur_img,
                        creator=request.user,
                    )
                except:
                    request.xml_response.error(
                        u"cannot create new device: {}".format(
                            process_tools.get_except_info()
                        ),
                        logger=logger
                    )
                    cur_dev = None
                else:
                    request.xml_response["device_pk"] = cur_dev.idx
            else:
                request.xml_response.warn(u"device {} already exists".format(unicode(cur_dev)), logger=logger)
                cur_dev = None

            if cur_dev is not None:
                try:
                    cur_nd = netdevice.objects.get(Q(device=cur_dev) & Q(devname='eth0'))
                except netdevice.DoesNotExist:
                    try:
                        cur_nd = netdevice.objects.create(
                            devname="eth0",
                            device=cur_dev,
                            routing=device_data["routing_capable"],
                        )
                        if device_data["peer"]:
                            peer_information.objects.create(
                                s_netdevice=cur_nd,
                                d_netdevice=netdevice.objects.get(Q(pk=device_data["peer"])),
                                penalty=1,
                            )
                    except:
                        request.xml_response.error("cannot create netdevice")
                        _create_ok = False
                try:
                    net_ip.objects.get(Q(netdevice=cur_nd) & Q(ip=device_data["ip"]))
                except net_ip.DoesNotExist:
                    cur_ip = net_ip(
                        netdevice=cur_nd,
                        ip=device_data["ip"],
                        domain_tree_node=dnt_node,
                    )
                    try:
                        cur_ip.save()
                    except:
                        request.xml_response.error(u"cannot create IP: {}".format(process_tools.get_except_info()), logger=logger)
                        _create_ok = False
        if cur_dev is not None:
            if _create_ok:
                request.xml_response.info(u"created new device '{}'".format(unicode(cur_dev)), logger=logger)
            else:
                # creation not ok, deleting device
                cur_dev.delete()


class DeviceVariableViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def create(self, request):
        new_obj = device_variable_serializer(data=request.data)
        # print new_obj.device_variable_scope
        if new_obj.is_valid():
            new_obj.save()
        else:
            raise ValidationError(
                "New Variable not valid: {}".format(
                    ", ".join(
                        [
                            "{}: {}".format(
                                _key,
                                ", ".join(_value),
                            ) for _key, _value in new_obj.errors.iteritems()
                        ]
                    )
                )
            )
        return Response(new_obj.data)

    @method_decorator(login_required)
    def get(self, request):
        return Response(
            device_variable_serializer(
                device_variable.objects.get(Q(pk=request.query_params["pk"]))
            ).data
        )

    @method_decorator(login_required)
    def delete(self, request, *args, **kwargs):
        device_variable.objects.get(Q(pk=kwargs["pk"])).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @method_decorator(login_required)
    def store(self, request, *args, **kwargs):
        _prev_var = device_variable.objects.get(Q(pk=kwargs["pk"]))
        # print _prev_var
        _cur_ser = device_variable_serializer(
            device_variable.objects.get(Q(pk=kwargs["pk"])),
            data=request.data
        )
        # print "*" * 20
        # print _cur_ser.device_variable_type
        if _cur_ser.is_valid():
            _new_var = _cur_ser.save()
        resp = _cur_ser.data
        c_list, r_list = get_change_reset_list(_prev_var, _new_var, request.data)
        resp = Response(resp)
        # print c_list, r_list
        resp.data["_change_list"] = c_list
        resp.data["_reset_list"] = r_list
        return resp


class DeviceVariableScopeViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def create_var_scope(self, request):
        new_scope = device_variable_scope_serializer(data=request.data)
        if new_scope.is_valid():
            new_scope.save()
        else:
            raise ValidationError(
                "New Scope not valid: {}".format(
                    ", ".join(
                        [
                            "{}: {}".format(
                                _key,
                                ", ".join(_value),
                            ) for _key, _value in new_scope.errors.iteritems()
                            ]
                    )
                )
            )
        return Response(new_scope.data)

    @method_decorator(login_required)
    def update_var_scope(self, request, *args, **kwargs):
        _prev_scope = device_variable_scope.objects.get(Q(pk=kwargs["pk"]))
        # print _prev_var
        _cur_ser = device_variable_scope_serializer(
            device_variable_scope.objects.get(Q(pk=kwargs["pk"])),
            data=request.data
        )
        # print "*" * 20
        # print _cur_ser.device_variable_type
        if _cur_ser.is_valid():
            _new_scope = _cur_ser.save()
            resp = _cur_ser.data
            c_list, r_list = get_change_reset_list(_prev_scope, _new_scope, request.data)
            resp = Response(resp)
            # print c_list, r_list
            resp.data["_change_list"] = c_list
            resp.data["_reset_list"] = r_list
            return resp
        else:
            raise ValidationError(
                "New Scope not valid: {}".format(
                    ", ".join(
                        [
                            "{}: {}".format(
                                _key,
                                ", ".join(_value),
                            ) for _key, _value in _cur_ser.errors.iteritems()
                        ]
                    )
                )
            )

    @method_decorator(login_required)
    def list(self, request):
        return Response(
            device_variable_scope_serializer(
                device_variable_scope.objects.all().prefetch_related("dvs_allowed_name_set"),
                many=True,
            ).data
        )

    @method_decorator(login_required)
    def delete_entry(self, request, **kwargs):
        dvs_entry = dvs_allowed_name.objects.get(Q(pk=kwargs["pk"]))
        can_delete_answer = can_delete_obj(dvs_entry, logger)
        if can_delete_answer:
            dvs_entry.delete()
        else:
            raise ValidationError(
                "cannot delete: {}".format(
                    logging_tools.get_plural("reference", len(can_delete_answer.related_objects))
                )
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @method_decorator(login_required)
    def create_entry(self, request, **kwargs):
        new_obj = dvs_allowed_name_serializer(data=request.data)
        # print new_obj.device_variable_scope
        if new_obj.is_valid():
            new_obj.save()
        else:
            raise ValidationError(
                "New Variable not valid: {}".format(
                    ", ".join(
                        [
                            "{}: {}".format(
                                _key,
                                ", ".join(_value),
                            ) for _key, _value in new_obj.errors.iteritems()
                        ]
                    )
                )
            )
        return Response(new_obj.data)

    @method_decorator(login_required)
    def store_entry(self, request, *args, **kwargs):
        _prev_var = dvs_allowed_name.objects.get(Q(pk=kwargs["pk"]))
        # print _prev_var
        _cur_ser = dvs_allowed_name_serializer(
            dvs_allowed_name.objects.get(Q(pk=kwargs["pk"])),
            data=request.data
        )
        # print "*" * 20
        # print _cur_ser.device_variable_type
        if _cur_ser.is_valid():
            _new_var = _cur_ser.save()
        resp = _cur_ser.data
        c_list, r_list = get_change_reset_list(_prev_var, _new_var, request.data)
        resp = Response(resp)
        # print c_list, r_list
        resp.data["_change_list"] = c_list
        resp.data["_reset_list"] = r_list
        return resp


class DeviceClassViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def list(self, request):
        return Response(
            DeviceClassSerializer(
                DeviceClass.objects.all(),
                many=True,
            ).data
        )

from initat.tools import logging_tools, process_tools, server_command
from initat.cluster.backbone.models import DeviceFlagsAndSettings, mon_check_command, MachineVector, AssetBatch, user, \
    category
import pytz
import ast


class DeviceCompletion(View):
    @method_decorator(login_required)
    def post(self, request):
        device_pks = [int(obj) for obj in request.POST.getlist("device_pks[]")]

        srv_com = server_command.srv_command(command="check_rrd_graph_freshness")
        srv_com["device_pk"] = device_pks[0]
        srv_com["device_pks"] = device_pks

        (result, _) = contact_server(
            request,
            icswServiceEnum.grapher_server,
            srv_com
        )

        rrd_modification_dict = None
        if result:
            result_str, status = result.get_result()
            if status == 0:
                rrd_modification_dict = ast.literal_eval(result_str)

        devices = device.objects.prefetch_related(
            "assetbatch_set"
        ).select_related(
            "flags_and_settings"
        ).filter(
            Q(idx__in=device_pks)
        )

        # build monitoring check information
        device_checks_count = {}
        for check in mon_check_command.objects.all().prefetch_related("config__device_config_set"):
            for device_idx in check.get_configured_device_pks():
                if device_idx not in device_checks_count:
                    device_checks_count[device_idx] = 0
                device_checks_count[device_idx] += 1

        # build graphing information
        device_graph_count = {}
        machine_vectors = MachineVector.objects.prefetch_related("device").filter(device__idx__in=device_pks)
        for machine_vector in machine_vectors:
            if machine_vector.device.idx not in device_graph_count:
                device_graph_count[machine_vector.device.idx] = 0
            device_graph_count[machine_vector.device.idx] += 1

        # build location information map
        device_location_count = {}
        location_categories = category.objects.prefetch_related("device_set").filter(full_name__startswith="/location/")
        for location_category in location_categories:
            for _device in location_category.device_set.all():
                if _device.idx not in device_location_count:
                    device_location_count[_device.idx] = 0
                device_location_count[_device.idx] += 1

        info_dict = {}

        for _device in devices:
            info_dict[_device.idx] = {}

            info_dict[_device.idx]["graphing_data"] = 0
            if _device.idx in device_graph_count:
                info_dict[_device.idx]["graphing_data"] = device_graph_count[_device.idx]

            info_dict[_device.idx]["graphing_data_warning"] = False

            try:
                if _device.flags_and_settings.graph_enslavement_start:
                    seconds_since_graph_setup = \
                        (datetime.datetime.now(tz=pytz.utc) - _device.flags_and_settings.graph_enslavement_start).total_seconds()
                else:
                    seconds_since_graph_setup = 0

                info_dict[_device.idx]["graphing_data_warning"] = seconds_since_graph_setup < (60 * 2)
            except DeviceFlagsAndSettings.DoesNotExist:
                pass

            if rrd_modification_dict and _device.idx in rrd_modification_dict and rrd_modification_dict[_device.idx] > 0:
                _now = datetime.datetime.now()
                modification_time = datetime.datetime.fromtimestamp(rrd_modification_dict[_device.idx])

                rrd_age_in_seconds = int((_now - modification_time).total_seconds())

                info_dict[_device.idx]["graphing_data_age_in_seconds"] = rrd_age_in_seconds
                info_dict[_device.idx]["graphing_data_extended_text"] = "Last update {} second(s) ago".format(rrd_age_in_seconds)
                if rrd_age_in_seconds > 60:
                    age_in_minutes = round(rrd_age_in_seconds / 60.0, 1)
                    info_dict[_device.idx]["graphing_data_extended_text"] = "Last update {} minute(s) ago".format(
                        age_in_minutes)
                if rrd_age_in_seconds > (60 * 60):
                    age_in_hours = round(rrd_age_in_seconds / (60.0 * 60.0), 1)
                    info_dict[_device.idx]["graphing_data_extended_text"] = "Last update {} hour(s) ago".format(
                        age_in_hours)
                if rrd_age_in_seconds > (60 * 60 * 24):
                    age_in_days = round(rrd_age_in_seconds / (60.0 * 60.0 * 24), 1)
                    info_dict[_device.idx]["graphing_data_extended_text"] = "Last update {} day(s) ago".format(
                        age_in_days)
                if rrd_age_in_seconds > (60 * 60 * 24 * 7):
                    age_in_weeks = round(rrd_age_in_seconds / (60.0 * 60.0 * 24 * 7), 1)
                    info_dict[_device.idx]["graphing_data_extended_text"] = "Last update {} week(s) ago".format(
                        age_in_weeks)

            info_dict[_device.idx]["monitoring_checks"] = 0
            if _device.idx in device_checks_count:
                info_dict[_device.idx]["monitoring_checks"] = device_checks_count[_device.idx]
                info_dict[_device.idx]["monitoring_checks_extended_text"] = "{}".format(device_checks_count[_device.idx])

            info_dict[_device.idx]["location_data"] = 0
            if _device.idx in device_location_count:
                info_dict[_device.idx]["location_data"] = device_location_count[_device.idx]
                info_dict[_device.idx]["location_data_extended_text"] = "{}".format(device_location_count[_device.idx])

            asset_scan_count = _device.assetbatch_set.count()
            info_dict[_device.idx]["asset_data"] = asset_scan_count

            if asset_scan_count:
                info_dict[_device.idx]["asset_data_extended_text"] = "{}".format(asset_scan_count)

        return HttpResponse(
            json.dumps(info_dict)
        )


class SimpleGraphSetup(View):
    @method_decorator(login_required)
    def post(self, request):
        device_pk = int(request.POST.get("device_pk"))

        srv_com = server_command.srv_command(command="add_rrd_target")
        srv_com["device_pk"] = device_pk

        (result, _) = contact_server(
            request,
            icswServiceEnum.collectd_server,
            srv_com,
        )

        if result:
            _status = bool(result.get_result())
        else:
            _status = False

        return HttpResponse(
            json.dumps(_status)
        )

#todo move somwhere sane
class SystemCompletion(View):
    def post(self, request):
        info_dict = {}

        system_device = device.objects.get(idx=1)

        devices_count = device.objects.filter(is_meta_device=False).count()
        v = system_device.device_variable_set.filter(name="__ISSUES_IGNORE_{}__".format("devices"))

        info_dict['devices'] = devices_count
        info_dict['devices_text'] = "{} Device".format(devices_count)
        info_dict['devices_ignore'] = len(v) > 0

        mon_check_count = mon_check_command.objects.all().count()
        v = system_device.device_variable_set.filter(name="__ISSUES_IGNORE_{}__".format("monitoring_checks"))

        info_dict['monitoring_checks'] = mon_check_count
        info_dict['monitoring_checks_text'] = "{} Check".format(mon_check_count)
        info_dict['monitoring_checks_ignore'] = len(v) > 0

        user_count = user.objects.all().count() - 1
        v = system_device.device_variable_set.filter(name="__ISSUES_IGNORE_{}__".format("users"))

        info_dict["users"] = user_count
        info_dict["users_text"] = "{} (non-admin) User".format(user_count)
        info_dict["users_ignore"] = len(v) > 0

        locations_count = 0
        for _category in category.objects.all():
            if _category.full_name.startswith("/location/"):
                locations_count += 1

        v = system_device.device_variable_set.filter(name="__ISSUES_IGNORE_{}__".format("locations"))

        info_dict["locations"] = locations_count
        info_dict["locations_text"] = "{} Location".format(locations_count)
        info_dict["locations_ignore"] = len(v) > 0

        info_names = ["devices", "monitoring_checks", "users", "locations"]
        for info_name in info_names:
            if info_dict[info_name] > 1:
                info_dict[info_name + "_text"] += "s"

        return HttpResponse(
            json.dumps(info_dict)
        )

#todo move somwhere sane
class SystemCompletionIgnoreToggle(View):
    def post(self, request):
        system_component_name = request.POST.get("system_component_name")

        system_device = device.objects.get(idx=1)

        variable_name = "__ISSUES_IGNORE_{}__".format(system_component_name)

        v = system_device.device_variable_set.filter(name=variable_name)

        if v:
            v[0].delete()
        else:
            system_device.device_variable_set.create(
                device = system_device,
                is_public = False,
                name = variable_name,
                local_copy_ok = False,
                inherit = False,
                protected = True,
                var_type = "i",
                val_int = 1
            )

        return HttpResponse(
            json.dumps(1)
        )

class DeviceLogEntryViewSet(viewsets.ViewSet):
    def list(self, request):
        prefetch_list = [
            "source",
            "level"
        ]

        if "device_pks" in request.query_params:
            queryset = DeviceLogEntry.objects.prefetch_related(*prefetch_list).filter(
                device__in=json.loads(request.query_params.getlist("device_pks")[0]))
        else:
            queryset = DeviceLogEntry.objects.prefetch_related(*prefetch_list).all()

        serializer = DeviceLogEntrySerializer(queryset, many=True)

        return Response(serializer.data)