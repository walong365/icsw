# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

""" config views """

import StringIO
import copy
import datetime
import json
import logging
import re
import time

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from lxml import etree
from lxml.builder import E
from rest_framework.parsers import XMLParser
from rest_framework.renderers import XMLRenderer

from initat.cluster.backbone import serializers
from initat.cluster.backbone.models import config, device, device_config, ConfigTreeNode, \
    get_related_models, mon_check_command, category, config_str, \
    config_script, config_bool, config_blob, config_int, config_catalog
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.backbone.serializers import config_dump_serializer, mon_check_command_serializer
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.tools import logging_tools, process_tools, server_command

logger = logging.getLogger("cluster.config")


class show_configs(permission_required_mixin, View):
    all_required_permissions = ["backbone.config.modify_config"]

    def get(self, request):
        return render_me(
            request,
            "config_overview.html", {
            }
        )()


def delete_object(request, del_obj, **kwargs):
    num_ref = get_related_models(del_obj)
    if num_ref:
        request.xml_response.error("cannot delete {} '{}': {}".format(
            del_obj._meta.object_name,
            unicode(del_obj),
            logging_tools.get_plural("reference", num_ref)), logger)
    else:
        del_obj.delete()
        if kwargs.get("xml_log", True):
            request.xml_response.info("deleted {}".format(del_obj._meta.object_name), logger)
        else:
            logger.info("deleted {}".format(del_obj._meta.object_name))


def _get_device_configs(sel_list, **kwargs):
    dev_list = [key.split("__")[1] for key in sel_list if key.startswith("dev__")]
    devg_list = [key.split("__")[1] for key in sel_list if key.startswith("devg__")]
    all_devs = device.all_real_enabled.filter(Q(pk__in=dev_list))
    # all meta devices
    meta_devs = device.all_meta_enabled.filter(
        Q(device_group__in=devg_list) | Q(device_group__device_group__in=dev_list)
    ).distinct()
    meta_confs = device_config.objects.filter(
        Q(device__enabled=True) & Q(device__device_group__enabled=True) & Q(device__in=meta_devs)
    ).select_related("device")
    # print len(meta_confs), len(meta_devs)
    if "conf" in kwargs:
        all_confs = device_config.objects.filter(
            Q(device__enabled=True) &
            Q(device__device_group__enabled=True) &
            Q(config=kwargs["conf"]) &
            Q(device__in=dev_list)
        )
        meta_confs = meta_confs.filter(config=kwargs["conf"])
    else:
        all_confs = device_config.objects.filter(
            Q(device__enabled=True) &
            Q(device__device_group__enabled=True) & (
                Q(device__in=dev_list) | (
                    Q(device__device_group__in=devg_list) & Q(device__is_meta_device=True)
                )
            )
        )
    xml_resp = E.device_configs()
    # build dict device_group -> conf_list
    dg_dict = {}
    for meta_conf in meta_confs:
        dg_dict.setdefault(meta_conf.device.device_group_id, []).append(meta_conf.config_id)
    for cur_conf in all_confs:
        xml_resp.append(
            E.device_config(
                device="{:d}".format(cur_conf.device_id),
                config="{:d}".format(cur_conf.config_id),
            )
        )
    # add meta device configs
    # print "***", all_devs, dev_list, device.objects.get(Q(pk=284))
    for sbm_dev in all_devs:
        # print unicode(all_devs)
        # print sbm_dev.device_group_id, dg_dict.keys()
        for conf_id in dg_dict.get(sbm_dev.device_group_id, []):
            # print unicode(sbm_dev)
            xml_resp.append(E.device_config(
                device="{:d}".format(sbm_dev.pk),
                config="{:d}".format(conf_id),
                meta="1"))
    return xml_resp


class alter_config_cb(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        checked = bool(int(_post["value"]))
        if "conf_pk" in _post:
            dev_id, conf_id = (
                int(_post["dev_pk"]),
                int(_post["conf_pk"]),
            )
        else:
            dev_id, conf_id = (
                int(_post["id"].split("__")[1]),
                int(_post["id"].split("__")[3])
            )
        cur_dev, cur_conf = (
            device.objects.get(Q(pk=dev_id)),
            getattr(config, "objects").get(Q(pk=conf_id))
        )
        # is metadevice ?
        is_meta = cur_dev.is_meta_device
        # all devices of device_group
        all_devs = cur_dev.device_group.device_group.all()
        logger.info(u"device {} [{}]/ config {}: {} ({} in device_group)".format(
            unicode(cur_dev),
            "MD" if is_meta else "-",
            unicode(cur_conf),
            "set" if checked else "unset",
            logging_tools.get_plural("device", len(all_devs))))
        if is_meta:
            # handling of actions for meta devices
            if checked:
                # remove all configs from devices in group
                to_remove = device_config.objects.exclude(Q(device=cur_dev)).filter(Q(config=cur_conf) & Q(device__in=all_devs))
                # check if we can safely set the meta device_config
                set_meta = True
                if len(to_remove):
                    if any([True for del_obj in to_remove if get_related_models(del_obj)]):
                        request.xml_response.error("device configs are in use (hence protected)", logger)
                        set_meta = False
                    else:
                        to_remove.delete()
                        request.xml_response.info("removed {} from devices".format(logging_tools.get_plural("config", len(to_remove))), logger)
                # unset all devices except meta_device
                if set_meta:
                    try:
                        device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
                    except device_config.DoesNotExist:
                        device_config(device=cur_dev,
                                      config=cur_conf).save()
                        request.xml_response.info("set meta config {}".format(unicode(cur_conf)), logger)
                    else:
                        request.xml_response.warn("meta config already set", logger)
            else:
                try:
                    del_obj = device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
                except device_config.DoesNotExist:
                    request.xml_response.warn("meta config already unset", logger)
                else:
                    delete_object(request, del_obj, xml_log=False)
                    request.xml_response.info("meta config '{}' removed".format(unicode(cur_conf)), logger)
        else:
            # get meta device
            try:
                meta_dev = cur_dev.device_group.device_group.get(Q(is_meta_device=True))
            except device.DoesNotExist:
                meta_dev = None
            # handling of actions for non-meta devices
            if checked:
                try:
                    device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
                except device_config.DoesNotExist:
                    device_config(device=cur_dev,
                                  config=cur_conf).save()
                    request.xml_response.info("set config {}".format(unicode(cur_conf)), logger)
                else:
                    request.xml_response.error("config {} already set".format(unicode(cur_conf)), logger)
            else:
                try:
                    del_obj = device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
                except device_config.DoesNotExist:
                    if meta_dev:
                        # check if meta_device has config_set
                        try:
                            meta_conf = device_config.objects.get(Q(device=meta_dev) & Q(config=cur_conf))
                        except device_config.DoesNotExist:
                            request.xml_response.error("config {} already unset and meta config also not set".format(unicode(cur_conf)), logger)
                        else:
                            # set config for all devices exclude the meta device and this device
                            if get_related_models(meta_conf):
                                request.xml_response.error("meta config {} is in use".format(unicode(cur_conf)), logger)
                            else:
                                meta_conf.delete()
                                add_devs = 0
                                for set_dev in all_devs.exclude(Q(pk=meta_dev.pk)).exclude(Q(pk=cur_dev.pk)):
                                    add_devs += 1
                                    device_config(device=set_dev,
                                                  config=cur_conf).save()
                                request.xml_response.warn("removed meta conf {} and set {}".format(
                                    unicode(cur_conf),
                                    logging_tools.get_plural("device", add_devs)), logger)

                    else:
                        request.xml_response.warn("config {} already unset".format(unicode(cur_conf)), logger)
                else:
                    delete_object(request, del_obj, xml_log=False)
                    request.xml_response.info("remove config {}".format(unicode(cur_conf)), logger)
        xml_resp = _get_device_configs(["dev__{:d}".format(sel_dev.pk) for sel_dev in all_devs], conf=cur_conf)
        xml_resp.extend(
            [
                E.config(pk="{:d}".format(cur_conf.pk)),
                E.devices(
                    *[
                        E.device(
                            pk="{:d}".format(sel_dev.pk),
                            key="dev__{:d}".format(sel_dev.pk)
                        ) for sel_dev in all_devs
                    ]
                )
            ]
        )
        request.xml_response["response"] = xml_resp


class ConfigTreeStruct(object):
    def __init__(self, cur_dev, node_list, node=None, depth=0, parent=None):
        self.dev_pk = cur_dev.pk
        self.depth = depth
        self.parent = parent
        if not node:
            if node_list:
                # root entry
                self.node = [entry for entry in node_list if not entry.parent_id][0]
            else:
                self.node = None
        else:
            self.node = node
        if self.node is not None:
            self.written_config_file = self.node.WrittenConfigFile
            self.childs = [
                ConfigTreeStruct(
                    cur_dev,
                    node_list,
                    node=cur_node,
                    depth=self.depth + 1,
                    parent=self,
                ) for cur_node in sorted(node_list) if cur_node.parent_id == self.node.pk
            ]
        else:
            self.wc_file = None
            self.childs = []

    def get_name(self):
        if self.node:
            return "{}{}".format(
                self.wc_file.dest,
                "/" if self.node.is_dir else ""
            )
        else:
            return "empty"

    def __unicode__(self):
        return "\n".join(
            [
                "{}{} ({:d}, {:d}), {}".format(
                    "  " * self.depth,
                    unicode(self.node),
                    self.depth,
                    len(self),
                    self.get_name()
                )
            ] + [
                u"{}".format(unicode(sub_entry)) for sub_entry in self.childs
            ]
        )

    def get_dict(self):
        return {
            "data": serializers.WrittenConfigFileSerializer(self.wc_file).data,
            "sub_nodes": [sub_node.get_dict() for sub_node in self.childs],
            "name": self.get_name(),
            "depth": "{:d}".format(self.depth),
            "is_dir": "1" if self.node.is_dir else "0",
            "is_link": "1" if self.node.is_link else "0",
            "node_id": "{:d}_{:d}".format(self.dev_pk, self.node.pk),
            # needed for linking in frontend angular code
            "parent_id": "{}".format("{:d}_{:d}".format(self.dev_pk, self.parent.node.pk) if self.parent else "0")
        }


class config_encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            # FIXME
            return obj.ctime()
        else:
            return super(config_encoder, self).default(obj)


class generate_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "pk_list" in _post:
            sel_list = json.loads(_post["pk_list"])
        else:
            sel_list = [key.split("__")[1] for key in _post.getlist("sel_list[]", []) if key.startswith("dev__")]
        dev_list = device.objects.prefetch_related("categories").filter(Q(pk__in=sel_list)).order_by("name")
        dev_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in dev_list])
        logger.info(
            "generating config for {}: {}".format(
                logging_tools.get_plural("device", len(dev_list)),
                ", ".join([unicode(dev) for dev in dev_list])))
        srv_com = server_command.srv_command(command="build_config")
        srv_com["devices"] = srv_com.builder(
            "devices",
            *[srv_com.builder("device", pk="{:d}".format(cur_dev.pk)) for cur_dev in dev_list])
        result = contact_server(request, "config", srv_com, timeout=30, log_result=False)
        if result:
            _json_result = {"devices": []}
            # request.xml_response["result"] = E.devices()
            for dev_node in result.xpath(".//ns:device", smart_strings=False):
                res_node = {key: dev_node.get(key) for key in dev_node.attrib.keys()}
                res_node["text"] = dev_node.text
                res_node["info_dict"] = []
                for sub_el in dev_node:
                    for _entry in sub_el.findall("entry"):
                        res_node["info_dict"].append(
                            {
                                "key": _entry.get("key"),
                                "text": _entry.text
                            }
                        )
                if "state_level" in dev_node.attrib:
                    if int(dev_node.attrib["state_level"]) < logging_tools.LOG_LEVEL_ERROR:
                        # if int(dev_node.attrib["state_level"]) == logging_tools.LOG_LEVEL_OK or True:
                        cur_dev = dev_dict[int(dev_node.attrib["pk"])]
                        # build tree
                        cur_tree = ConfigTreeStruct(cur_dev, ConfigTreeNode.objects.filter(Q(device=cur_dev)).select_related("WrittenConfigFile"))
                        res_node["config_tree"] = cur_tree.get_dict()
                else:
                    # config server not running, return dummy entry
                    dev_node.attrib["state_level"] = "{:d}".format(logging_tools.LOG_LEVEL_ERROR)
                    dev_node.attrib["result"] = "no result found"
                    res_node.update(
                        {
                            "state_level": logging_tools.LOG_LEVEL_ERROR
                        }
                    )
                _json_result["devices"].append(res_node)
            request.xml_response["result"] = config_encoder().encode(_json_result)
            request.xml_response.info("build done", logger)


class download_configs(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        conf_ids = json.loads(kwargs["hash"])
        logger.info("got download request for {}: {}".format(
            logging_tools.get_plural("config", len(conf_ids)),
            ", ".join(["{:d}".format(val) for val in sorted(conf_ids)])))
        configs = []
        # res_xml.append(configs)
        conf_list = getattr(config, "objects").filter(Q(pk__in=conf_ids)).prefetch_related(
            "config_str_set",
            "config_int_set",
            "config_bool_set",
            "config_blob_set",
            "mon_check_command_set",
            "config_script_set",
            "categories",
        )
        for cur_conf in conf_list:
            configs.append(config_dump_serializer(cur_conf).data)
        xml_tree = etree.fromstring(XMLRenderer().render(configs))  # @UndefinedVariable
        # remove all idxs and parent_configs
        for pk_el in xml_tree.xpath(".//idx|.//parent_config|.//categories|.//date", smart_strings=False):
            pk_el.getparent().remove(pk_el)
        act_resp = HttpResponse(
            etree.tostring(xml_tree, pretty_print=True),  # @UndefinedVariable
            content_type="application/xml"
        )
        act_resp["Content-disposition"] = "attachment; filename=config_{}.xml".format(
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        return act_resp

IGNORE_WHEN_EMPTY = ["categories"]
IGNORE_ATTRS = ["mon_service_templ"]
DEFAULT_MAP = {"description": "description"}


def interpret_xml(el_name, in_xml, mapping):
    new_el = getattr(E, el_name)()
    for key, value in in_xml.attrib.iteritems():
        if key in IGNORE_ATTRS:
            pass
        elif key in IGNORE_WHEN_EMPTY and not value.strip():
            pass
        else:
            if not value.strip() and key in DEFAULT_MAP:
                value = DEFAULT_MAP[key]
            new_el.append(getattr(E, key)(mapping.get(key, value)))
    return new_el


class upload_config(View):
    @method_decorator(login_required)
    def post(self, request):
        _data = StringIO.StringIO(request.FILES["config"].read())
        if _data.getvalue().startswith("<configuration>"):
            # old value
            _tree = etree.fromstring(_data.getvalue())  # @UndefinedVariable
            new_tree = E.root()
            for _config in _tree.findall(".//config"):
                c_el = interpret_xml("list-item", _config, {})
                mapping = {"config": c_el.findtext("name")}
                for targ_list in ["mon_check_command", "config_bool", "config_str", "config_int", "config_blob", "config_script"]:
                    c_el.append(getattr(E, "{}_set".format(targ_list))())
                new_tree.append(c_el)
                for sub_el in _config.xpath(
                    ".//config_str|.//config_int|.//config_bool|.//config_blob|.//config_script|.//mon_check_command",
                    smart_strings=False
                ):
                    if "type" in sub_el.attrib:
                        t_list = c_el.find("config_{}_set".format(sub_el.get("type")))
                    else:
                        t_list = c_el.find("{}_set".format(sub_el.tag))
                    if sub_el.tag == "config_script":
                        sub_el.attrib["description"] = "config script"
                    t_list.append(interpret_xml("list-item", sub_el, mapping))
            _data = StringIO.StringIO(etree.tostring(new_tree, pretty_print=False))  # @UndefinedVariable
            # print etree.tostring(new_tree, pretty_print=True)
            # sys.exit(-1)
            # print etree.tostring(_tree, pretty_print=True)
        try:
            conf_list = XMLParser().parse(_data)
        except:
            logger.error("cannot interpret upload file: {}".format(process_tools.get_except_info()))
        else:
            # store in local cache
            # get list of uploads
            _upload_list = cache.get("ICSW_UPLOAD_LIST", [])
            new_key = "ICSW_UPLOAD_{:d}".format(int(time.time()))
            store_cached_upload({"upload_key": new_key, "list": conf_list})
            _upload_list.append(new_key)
            cache.set("ICSW_UPLOAD_LIST", _upload_list, None)
        return HttpResponse(
            json.dumps("done"),
            content_type="application/json"
        )


def check_upload_config_cache(key):
    _res = None
    _up_list = cache.get("ICSW_UPLOAD_LIST", [])
    if key in _up_list:
        _res = cache.get(key, None)
    return _res


class get_cached_uploads(View):
    @method_decorator(login_required)
    def post(self, request):
        _cur_list = []
        _act_keys = []
        for _key in cache.get("ICSW_UPLOAD_LIST", []):
            _cur_val = cache.get(_key, None)
            if _cur_val and type(_cur_val) == dict:
                if all([_entry.get("_taken", False) for _entry in _cur_val["list"]]):
                    remove_cached_upload(_cur_val)
                else:
                    _cur_list.append(_cur_val)
                    _act_keys.append(_key)
        cache.set("ICSW_UPLOAD_LIST", _act_keys, None)
        return HttpResponse(json.dumps(_cur_list), content_type="application/json")


def store_cached_upload(struct):
    if all([_entry.get("_taken", False) for _entry in struct["list"]]):
        remove_cached_upload(struct)
    else:
        cache.set(struct["upload_key"], struct, 3600)


def remove_cached_upload(struct):
    cache.delete(struct["upload_key"])


class handle_cached_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        _struct = check_upload_config_cache(_post["upload_key"])
        if _struct:
            if _post["mode"] == "take":
                self._handle_take(request, _struct, _post)
            elif _post["mode"] == "delete":
                self._handle_ignore(request, _struct, _post)
            else:
                request.xml_response.error("unknown mode {}".format(_post["mode"]), logger=logger)

    def _handle_take(self, request, _struct, _post):
        for _entry in _struct["list"]:
            if _entry["name"] == _post["name"]:
                # make a copy because take_config alters entry
                _entry["_taken"] = self._take_config(request, copy.deepcopy(_entry), config_catalog.objects.get(Q(pk=_post["catalog"])))
                store_cached_upload(_struct)

    def _handle_ignore(self, request, _struct, _post):
        _struct["list"] = [_entry for _entry in _struct["list"] if _entry["name"] != _post["name"]]
        store_cached_upload(_struct)

    def _take_config(self, request, conf, ccat):
        _sets = {}
        for key in conf.iterkeys():
            # remove all subsets, needed because of limitations in DRF
            if key.endswith("_set") and conf[key]:
                _sets[key] = conf[key]
                conf[key] = []
        _ent = config_dump_serializer(data=conf)
        added = 0
        sub_added = 0
        try:
            _exists = config.objects.get(Q(name=conf["name"]) & Q(config_catalog=ccat))  # @UndefinedVariable
        except config.DoesNotExist:
            _take = True
        else:
            request.xml_response.error(
                "config {} already exists in config catalog {}".format(
                    conf["name"],
                    unicode(ccat)
                ),
                logger=logger
            )
            _take = False
        # we create the config with a dummy name to simplify matching of vars / scripts / monccs against configs with same name but different catalogs
        dummy_name = "_ul_config_{:d}".format(int(time.time()))
        taken = False
        if _take:
            if _ent.is_valid():
                _ent.object.create_default_entries = False
                try:
                    # store config catalog
                    _ent.object.config_catalog = ccat
                    _ent.object.name = dummy_name
                    _ent.object.save()
                    # pass
                except:
                    logger.error(
                        "error saving entry '{}': {}".format(
                            unicode(_ent),
                            process_tools.get_except_info()
                        )
                    )
                else:
                    taken = True
                    # add sub-sets
                    for key in _sets.iterkeys():
                        for entry in _sets[key]:
                            entry["config"] = dummy_name
                            if not entry.get("description", None):
                                # fix simple structure errors
                                entry["description"] = "dummy description"
                            _sub_ent = getattr(serializers, "{}_nat_serializer".format(key[:-4]))(data=entry)
                            if _sub_ent.is_valid():
                                try:
                                    _sub_ent.object.save()
                                except:
                                    request.xml_response.error(
                                        "error saving subentry '{}': {}".format(
                                            unicode(_sub_ent),
                                            process_tools.get_except_info()
                                        ),
                                        logger=logger
                                    )
                                else:
                                    sub_added += 1
                            else:
                                request.xml_response.error(
                                    "cannot create {} object: {}".format(
                                        key,
                                        unicode(_sub_ent.errors)
                                    ),
                                    logger=logger
                                )
                    added += 1
                    _ent.object.name = conf["name"]
                    _ent.object.save()
                    request.xml_response["new_pk"] = "{:d}".format(_ent.object.pk)
                    request.xml_response.info("create new config {} ({:d}) in config catalog {}".format(unicode(_ent.object), sub_added, unicode(ccat)))
            else:
                request.xml_response.error("cannot create config object: {}".format(unicode(_ent.errors)), logger=logger)
        return taken


class get_device_cvars(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "keys" in _post:
            pk_list = json.loads(_post["keys"])
        else:
            pk_list = [_post["key"]]
        srv_com = server_command.srv_command(command="get_config_vars")
        srv_com["devices"] = srv_com.builder(
            "devices",
            *[srv_com.builder("device", pk="{:d}".format(int(cur_pk))) for cur_pk in pk_list])
        result = contact_server(request, "config", srv_com, timeout=30, log_result=False)
        if result:
            request.xml_response["result"] = E.devices()
            for dev_node in result.xpath(".//ns:device", smart_strings=False):
                res_node = E.device(dev_node.text, **dev_node.attrib)
                for sub_el in dev_node:
                    res_node.append(sub_el)
                request.xml_response["result"].append(res_node)
                request.xml_response.log(int(dev_node.attrib["state_level"]), dev_node.attrib["info_str"], logger=logger)


class copy_mon(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        _config = config.objects.get(Q(pk=_post["config"]))  # @UndefinedVariable
        mon_source = mon_check_command.objects.get(Q(pk=_post["mon"]))
        name_re = re.compile("^(?P<pre>.*)_(?P<idx>\d+)$")
        if name_re.match(mon_source.name):
            new_name = mon_source.name
        else:
            new_name = "{}_1".format(mon_source.name)
        while True:
            if mon_check_command.objects.filter(Q(name=new_name)).count():
                name_s = name_re.match(new_name)
                new_name = u"{}_{:d}".format(name_s.group("pre"), int(name_s.group("idx")) + 1)
            else:
                break
        src_cats = mon_source.categories.all().values_list("pk", flat=True)
        mon_source.pk = None
        mon_source.name = new_name
        mon_source.save()
        mon_source.categories.add(*[_entry for _entry in category.objects.filter(Q(pk__in=src_cats))])
        logger.info("duplicate mon_check_command '{}' ({:d})".format(unicode(mon_source), mon_source.pk))
        _json = mon_check_command_serializer(mon_source).data
        _json["date"] = _json["date"].isoformat()
        request.xml_response.log(logging_tools.LOG_LEVEL_OK, "duplicated MonCheckCommand")
        request.xml_response["mon_cc"] = json.dumps(_json)


class delete_objects(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        del_list = json.loads(request.POST["obj_list"])
        del_dict = {}
        for obj_type, obj_idx in del_list:
            del_dict.setdefault(obj_type, []).append(obj_idx)
        for obj_type, pk_list in del_dict.iteritems():
            {
                "mon": mon_check_command,
                "script": config_script,
                "str": config_str,
                "int": config_int,
                "bool": config_bool,
                "blob": config_blob,
            }[obj_type].objects.filter(Q(pk__in=pk_list)).delete()
        request.xml_response.info("deleted {}".format(logging_tools.get_plural("object", len(del_list))))
