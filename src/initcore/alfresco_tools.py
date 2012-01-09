#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
""" toolkit for alfresco """

from pkg_resources import require
require("Suds")
import suds
from suds.client import Client
#from suds.wsse import Security, UsernameToken
from suds.sax.element import Element
import urllib2
import suds.wsse
import time
import base64
import datetime
import sys
import pytz
import logging_tools
import os
import pprint
import types
import logging
import mimetypes
from django.conf import settings

def keyword_check(*kwarg_list):
    def decorator(func):
        def _wrapped_view(*args, **kwargs):
            diff_set = set(kwargs.keys()) - set(kwarg_list)
            if diff_set:
                raise KeyError, "Invalid keyword arguments: %s" % (str(diff_set))
            return func(*args, **kwargs)
        return _wrapped_view
    return decorator

ALFRESCO_WS_CML_NS             = "http://www.alfresco.org/ws/cml/1.0"
ALFRESCO_WS_MODEL_CONTENT_NS   = "http://www.alfresco.org/ws/model/content/1.0"
ALFRESCO_WS_SERVICE_CONTENT_NS = "http://www.alfresco.org/ws/service/content/1.0"
ALFRESCO_WS_SERVICE_CLASS_NS   = "http://www.alfresco.org/ws/service/classification/1.0"
ALFRESCO_MODEL_CONTENT_NS      = "http://www.alfresco.org/model/content/1.0"
ALFRESCO_MODEL_SYSTEM_NS       = "http://www.alfresco.org/model/system/1.0"

def add_tzinfo(dt_obj):
    dt_obj = dt_obj.replace(tzinfo=pytz.timezone("Europe/Vienna"))
    iso_dt, iso_utc = dt_obj.isoformat().split("+")
    if iso_dt[-6:].isdigit():
        iso_dt = iso_dt[:-3]
        iso_date = "%s+%s" % (iso_dt, iso_utc)
    else:
        iso_date = "%s.000+%s" % (iso_dt, iso_utc)
    return iso_date
    
class alfresco_content(object):
    def __init__(self, alf_handler, node_obj, **kwargs):
        self.node_obj = node_obj
        if alf_handler:
            self.url = alf_handler("Content", "read",
                                   alf_handler.get_predicate(node=node_obj.reference),
                                   "{%s}content" % (ALFRESCO_MODEL_CONTENT_NS))[0].url
            full_url = "%s?ticket=%s" % (self.url,
                                         alf_handler.get_user_session().ticket)
            self.content = urllib2.urlopen(full_url).read()
        else:
            self.url, self.content = (None, None)
        self.__attr_dict = {}
        for nv in self.node_obj.properties:
            if nv.name.startswith("{"):
                key = nv.name.split("}")[1]
            else:
                key = nv.name
            value = nv.value
            self.__attr_dict[key] = value
    def keys(self):
        return self.__attr_dict.keys()
    def __getitem__(self, key):
        return self.__attr_dict[key]
    def get(self, key, def_value):
        return self.__attr_dict.get(key, def_value)
    def get_content_dict(self, *args):
        return get_content_dict(self["content"])
    def __repr__(self):
        return "alfresco content %s" % (self.node_obj.reference.path)
        
def get_content_dict(in_str):
    return dict([(str(key), value) for key, value in [sub_str.split("=", 1) for sub_str in in_str.split("|")[1:]]])
    
class CMLCreate(suds.wsse.Token):
    def __init__(self, create_id, parent, node_type, prop_list):
        suds.wsse.Token.__init__(self)
        self.id = create_id
        self.parent = parent
        self.type = node_type
        self.property = prop_list
        
class CMLDelete(suds.wsse.Token):
    def __init__(self, pred):
        suds.wsse.Token.__init__(self)
        self.where = pred
        
class CMLaddAspect(suds.wsse.Token):
    def __init__(self, aspect, pred):
        suds.wsse.Token.__init__(self)
        self.aspect = aspect
        self.property = []
        self.where = [pred]
    
class alfresco_token(suds.wsse.Token):
    def __init__(self, username=None, password=None):
        suds.wsse.Token.__init__(self)
        self.username = username
        self.password = password
    def xml(self):
        root = Element("UsernameToken", ns=suds.wsse.wssens)
        user_el = Element("Username", ns=suds.wsse.wssens)
        user_el.setText(self.username)
        root.append(user_el)
        pass_el = Element("Password", ns=suds.wsse.wssens)
        pass_el.attributes = ['Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText"']
        pass_el.setText(self.password)
        root.append(pass_el)
        return root

class alfresco_handler(object):
    def __init__(self, log_com, **kwargs):
        self.log_com = log_com
        self.host = kwargs.get("host", settings.ALFRESCO_SERVER)
        self.port = kwargs.get("port", settings.ALFRESCO_PORT)
        self.__user, self.__password = (None, None)
        directory_credentials = self.get_credentials(kwargs.get("directory"))
        if directory_credentials:
            self.set_user_credentials(directory_credentials.get("USERNAME"),
                                      directory_credentials.get("PASSWORD"))
        self.base_url = "http://%s:%d/alfresco/api" % (self.host,
                                                       self.port)
        #self.log("base_url is '%s'" % (self.base_url))
        self.__admin_user, self.__admin_password = (None, None)
        self.__admin_session, self.__user_session = (None, None)
        self.__clients = {}
        self.stores = None
        self._init_errors()
        # caching flag
        self.class_tree_already_fetched = False
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[ah] %s" % (what), log_level)
    def get_credentials(self, folder):
        return settings.ALFRESCO_DIRS.get(folder)
    def get_url(self, url_type):
        return "%s/%sService?wsdl" % (self.base_url, url_type)
    def set_admin_credentials(self, user_name, password):
        self.__admin_user, self.__admin_password = (user_name, password)
    def set_user_credentials(self, user_name, password):
        self.__user, self.__password = (user_name, password)
    def create_admin_session(self):
        if not self.__admin_session:
            self.__admin_session = self["Authentication"].service.startSession(self.__admin_user,
                                                                               self.__admin_password)[1]
            cur_sec = suds.wsse.Security()
            cur_sec.tokens.append(suds.wsse.Timestamp(0))
            cur_sec.tokens.append(alfresco_token(self.__admin_session.username,
                                                 self.__admin_session.ticket))
            self.__admin_security = cur_sec
        return self.__admin_security
    def _init_errors(self):
        self.__error_list = []
    def _get_errors(self):
        return self.__error_list
    def add_error(self, error_str):
        self.__error_list.append(error_str)
    def log_errors(self, **kwargs):
        for error in self.__error_list:
            self.log(error, logging_tools.LOG_LEVEL_ERROR)
        if kwargs.get("clear", False):
            self._init_errors()
    def _remove_last_error(self):
        if self.__error_list:
            self.__error_list.pop(-1)
    def create_user_session(self):
        if not self.__user_session:
            self.__user_session = self["Authentication"].service.startSession(self.__user,
                                                                              self.__password)[1]
            cur_sec = suds.wsse.Security()
            # fix for suds 0.3.7 -> 0.4
            cur_sec.tokens.append(suds.wsse.Timestamp(7200))
            cur_sec.tokens.append(alfresco_token(self.__user_session.username,
                                                 self.__user_session.ticket))
            self.__user_security = cur_sec
        return self.__user_security
    def get_user_session(self):
        return self.__user_session
    def __getitem__(self, sess_type):
        if sess_type not in self.__clients:
            if settings.DEBUG:
                self.__clients[sess_type] = Client(url=self.get_url(sess_type), cache=None, faults=False)
            else:
                self.__clients[sess_type] = Client(url=self.get_url(sess_type), cache=suds.cache.ObjectCache(days=1), faults=False)
        if sess_type not in ["Authentication"]:
            self.__clients[sess_type].set_options(wsse=self.create_user_session())
        return self.__clients[sess_type]
    def get_result(self, **kwargs):
        return self.__latest_result
    def close(self):
        if self.__user_session:
            self.log("closing user session (%s)" % (self.__user_session.ticket))
            self["Authentication"].service.endSession(self.__user_session.ticket)
            self.__user_session = None
            self.__user_security = None
        if self.__admin_session:
            self.log("closing admin session (%s)" % (self.__admin_session.ticket))
            self["Authentication"].service.endSession(self.__admin_session.ticket)
            self.__admin_session = None
            self.__admin_security = None
    def _fetch_aspect_tree(self, parent=None, parent_name=None):
        # not really working right now ...
        return
        if parent is None:
            self._fetch_stores()
            self.aspect_tree = {}
            print self["Dictionary"]
            cur_aspects = self["Dictionary"].service.getClasses([], [])
            print cur_aspects
            prefix = ""
        else:
            cur_classes = self["Classification"].service.getChildCategories(parent)[1]
            prefix = "%s/" % (parent_name)
        for cur_class in cur_classes:
            cur_name = "%s%s" % (prefix, cur_class.title)
            self.class_tree[cur_class.id.path] = cur_class
            self.class_tree[cur_name] = cur_class
            self._fetch_class_tree(self.get_reference(cur_class.id.path), cur_name)
        if not parent:
            short_tags = [key for key in self.class_tree.keys() if not key.startswith("/")]
            self.log("found %s: %s" % (logging_tools.get_plural("tag", len(short_tags)),
                                       ", ".join(sorted(short_tags))))
    def _fetch_class_tree(self, parent=None, parent_name=None, **kwargs):
        if kwargs.get("cache", False) and self.class_tree_already_fetched:
            return
        if parent is None:
            self._fetch_stores()
            self.class_tree = {}
            #print self["Classification"].service.getClassifications(self.store_dict["SpacesStore"])
            cur_classes = [cur_class.rootCategory for cur_class in self["Classification"].service.getClassifications(self.store_dict["SpacesStore"])[1] if cur_class.rootCategory.title in ["Tags"]]
            prefix = ""
        else:
            cur_classes = self["Classification"].service.getChildCategories(parent)[1]
            prefix = "%s/" % (parent_name)
        for cur_class in cur_classes:
            cur_name = "%s%s" % (prefix, cur_class.title)
            self.class_tree[cur_class.id.path] = cur_class
            self.class_tree[cur_name] = cur_class
            self._fetch_class_tree(self.get_reference(cur_class.id.path), cur_name)
        if not parent:
            short_tags = [key for key in self.class_tree.keys() if not key.startswith("/")]
            self.log("found %s: %s" % (logging_tools.get_plural("tag", len(short_tags)),
                                       ", ".join(sorted(short_tags))))
        if kwargs.get("cache", False):
            self.class_tree_already_fetched = True
    def _fetch_stores(self):
        if not self.stores:
            #print self["Repository"].service.getStores()
            self.stores = self["Repository"].service.getStores()[1]
            self.store_dict = dict([(cur_store.address, cur_store) for cur_store in self.stores])
            self.log("fetched %s: %s" % (logging_tools.get_plural("store", len(self.store_dict)),
                                         ", ".join(sorted(self.store_dict))))
    def child_exists_in_dir(self, full_path, child_name, **kwargs):
        # case insensitive
        if kwargs.get("init_errors", True):
            self._init_errors()
        cur_res = self._rewrite_query_result(self("Repository", "queryChildren", self.get_reference(full_path), ignore_errors=True), rqr_rowindex=False, rqr_uuid=False)
        if cur_res is None:
            # no result, child does not exist
            return None
        else:
            res_dict = dict([(key.lower().replace("{colon}", ":").replace("{slash}", "/"), key.replace("{colon}", ":").replace("{slash}", "/")) for key in cur_res.keys()])
            if child_name.lower() in res_dict:
                return res_dict[child_name.lower()]
            else:
                return child_name
    def node_exists(self, full_path, **kwargs):
        # case sensitive
        if kwargs.get("init_errors", True):
            self._init_errors()
        node_pred = self.get_predicate()
        node_pred.nodes = [self.get_reference(full_path)]
        self.__latest_result = self("Repository", "get", node_pred, ignore_errors=kwargs.get("ignore_errors", False))
        return True if self.__latest_result else False
    def get_dir_list(self, full_path, **kwargs):
        if kwargs.get("init_errors", True):
            self._init_errors()
        self.__latest_result = self._rewrite_query_result(self("Repository", "queryChildren", self.get_reference(full_path)), **kwargs)
        return True if self.__latest_result else False
    def _rewrite_query_result(self, q_result, **kwargs):
        ref_rowindex, ref_name, ref_uuid = (kwargs.get("rqr_rowindex", True),
                                            kwargs.get("rqr_name", True),
                                            kwargs.get("rqr_uuid", True))
        if q_result:
            r_dict = {}
            if q_result.resultSet.totalRowCount:
                for node in q_result.resultSet.rows:
                    node_ref = {"node" : node.node}
                    for nv in node.columns:
                        node_ref[nv.name] = nv
                        # add shortcuts
                        if nv.name.startswith("{"):
                            node_ref[nv.name.split("}")[1]] = nv.value
                    # always store name
                    if ref_rowindex:
                        r_dict[node.rowIndex] = node_ref
                    if ref_name and "{%s}name" % (ALFRESCO_MODEL_CONTENT_NS) in node_ref:
                        r_dict[node_ref["{%s}name" % (ALFRESCO_MODEL_CONTENT_NS)].value] = node_ref
                    if ref_uuid and "{%s}node-uuid" % (ALFRESCO_MODEL_SYSTEM_NS) in node_ref:
                        r_dict[node_ref["{%s}node-uuid" % (ALFRESCO_MODEL_SYSTEM_NS)].value] = node_ref
        else:
            r_dict = None
        return r_dict
    def delete_node(self, **kwargs):
        if kwargs.get("init_errors", True):
            self._init_errors()
        cur_pred, ret_node = (None, None)
        #if not self.node_exists(full_path, init_errors=False):
        #    self.add_error("path '%s' does not exist" % (full_path))
        #    return False
        #elif not self.node_exists(f_path, init_errors=False):
        #    self.add_error("parent path '%s' does not exist" % (full_path))
        #    return False
        #else:
        #    print self["Repository"]
        if "path" in kwargs:
            f_path, f_name = os.path.split(kwargs.get("path"))
            #f_path, f_name = os.path.split(full_path)
            cur_pred = self.get_predicate()
            cur_pred.nodes = [self.get_reference(f_path)]
        elif "uuid" in kwargs:
            cur_pred = self.get_predicate()
            if "version" in kwargs:
                cur_pred.nodes = [self.get_reference(None,
                                                     uuid=self.get_version_history(uuid=kwargs["uuid"])[kwargs["version"]],
                                                     path="ver2:versionedState",
                                                     store="version2Store")]
            else:
                cur_pred.nodes = [self.get_reference(None, uuid=kwargs["uuid"])]
        else:
            self.add_error("node location not specified")
        if cur_pred:
            cur_delete = self["Repository"].factory.create("{%s}CML" % (ALFRESCO_WS_CML_NS))
            cur_delete.delete = CMLDelete(cur_pred)
            ret_val = self("Repository", "update", cur_delete, info="delete node")
            self.__latest_result = ret_val
        success = True if not len(self._get_errors()) else False
        return success
    def check_path_case(self, full_path, **kwargs):
        if kwargs.get("init_errors", True):
            self._init_errors()
        f_path = full_path
        path_parts = []
        while True:
            f_path, dir_name = os.path.split(f_path)
            path_parts.append(dir_name)
            if not f_path:
                break
        path_parts.reverse()
        self.log("path_parts of '%s' is %s" % (full_path, ", ".join(path_parts)))
        dir_name = path_parts.pop(0)
        for sub_name in path_parts:
            real_sub_name = self.child_exists_in_dir(dir_name, sub_name)
            if real_sub_name is not None:
                sub_name = real_sub_name
            dir_name = os.path.join(dir_name, sub_name)
        self.log("sanitized path_name is %s" % (dir_name))
        full_path = dir_name
        return full_path
    def create_folder(self, full_path, **kwargs):
        if kwargs.get("init_errors", True):
            self._init_errors()
        # now handled by iterative creation, much faster
        #if not kwargs.get("path_name_is_sane", False):
        #    full_path = self.check_path_case(full_path)
        #    kwargs["path_name_is_sane"] = True
        check_for_existing = kwargs.get("check_for_existing", False)
        f_path, dir_name = os.path.split(full_path)
        # check for existing parent_path
        if not self.node_exists(f_path, init_errors=False, ignore_errors=True):
            if kwargs.get("recursive", False):
                kwargs["init_errors"] = False
                kwargs["return_path_on_success"] = True
                new_dir_path = self.create_folder(f_path, **kwargs)
                if new_dir_path:
                    full_path = os.path.join(new_dir_path, dir_name)
                    f_path = new_dir_path
            else:
                self.add_error("parent folder '%s' does not exist" % (f_path))
        if not self._get_errors():
            retry, retry_count = (True, 0)
            while retry and retry_count < 2:
                retry = False
                if check_for_existing and self.node_exists(full_path, ignore_errors=True, init_errors=False):
                    self.log("folder '%s' already exists in '%s'" % (dir_name,
                                                                     f_path))
                else:
                    parent_ref = self.get_parent_reference(f_path, dir_name)
                    property_list = [self.get_named_value("name", self._safe_dir_name(dir_name))]
                    for add_nv in ["author", "description"]:
                        if add_nv in kwargs:
                            property_list.append(self.get_named_value(add_nv, kwargs[add_nv]))
                    cur_create = self["Repository"].factory.create("{%s}CML" % (ALFRESCO_WS_CML_NS))
                    cur_create.create = CMLCreate("1",
                                                  parent_ref,
                                                  "{%s}folder" % (ALFRESCO_MODEL_CONTENT_NS),
                                                  property_list)
                    # node predicate
                    ret_val = self("Repository", "update", cur_create, info="create folder '%s' beneath '%s'" % (dir_name, f_path))
                    if ret_val is None:
                        if "DuplicateChildNodeNameException" in self._get_errors()[0]:
                            self.log("problem with case detected, checking...", logging_tools.LOG_LEVEL_ERROR)
                            real_dir_name = self.child_exists_in_dir(f_path, dir_name)
                            self.log("dir_name tried was '%s', should be '%s'" % (dir_name,
                                                                                  real_dir_name), logging_tools.LOG_LEVEL_WARN)
                            dir_name = real_dir_name
                            full_path = os.path.join(f_path, dir_name)
                            retry = True
                            retry_count += 1
                    self.__latest_result = ret_val
        success = True if not len(self._get_errors()) else False
        if success and kwargs.get("return_path_on_success"):
            return full_path
        else:
            return success
    def store_content(self, full_path, f_content, **kwargs):
        self._fetch_class_tree(cache=True)
        # generate path
        self._init_errors()
        f_path, f_name = os.path.split(full_path)
        # guess mimetype if not set
        if "mimetype" not in kwargs:
            g_mimetype, g_encoding = mimetypes.guess_type(f_name)
            if g_mimetype:
                kwargs["mimetype"] = g_mimetype
        parent_ref = self.get_parent_reference(f_path, f_name)
        cur_type = self.get_content_format(**kwargs)
        property_list = [self.get_named_value("name", f_name)]
        for add_nv in ["author", "description", "created"]:
            if add_nv in kwargs:
                add_value = kwargs[add_nv]
                if type(add_value) in [datetime.date, datetime.datetime]:
                    add_value = add_tzinfo(add_value)
                property_list.append(self.get_named_value(add_nv, add_value))
        cur_create = self["Repository"].factory.create("{%s}CML" % (ALFRESCO_WS_CML_NS))
        cur_create.create = CMLCreate("1",
                                      parent_ref,
                                      "{%s}content" % (ALFRESCO_MODEL_CONTENT_NS),
                                      property_list)
        # node predicate
        node_pred = self.get_predicate()
        node_pred.nodes = [self.get_reference(full_path)]
        check_for_existing = kwargs.get("check_for_existing", False)
        create_new_version_if_exists = kwargs.get("create_new_version_if_exists", False)
        # clear call_result
        call_result = None
        node_exists = False
        if check_for_existing:
            if self.get_dir_list(f_path):
                if f_name in self.get_result().keys():
                    self.log("node '%s' in %s already exists" % (f_name,
                                                                 f_path))
                    node_exists = True
        if node_exists:
            if create_new_version_if_exists:
                self.log("found previous version, creating new version")
                ret_val = True
                set_flags = False
                call_result = self("Repository", "get", node_pred)[0]
                if not "versionLabel" in [cur_prop.name.split("}", 1)[1] for cur_prop in call_result.properties]:
                    self.log("versionLabel property not set, applying set_tags", logging_tools.LOG_LEVEL_WARN)
                    cur_create = self["Repository"].factory.create("{%s}CML" % (ALFRESCO_WS_CML_NS))
                    cur_create.addAspect = [CMLaddAspect("{%s}versionable" % (ALFRESCO_MODEL_CONTENT_NS), node_pred),
                                            CMLaddAspect("{%s}generalclassifiable" % (ALFRESCO_MODEL_CONTENT_NS), node_pred)]
                    self("Repository", "update", cur_create, info="set aspects", ignore_errors=True)
            else:
                ret_val = None
        else:
            ret_val = self("Repository", "update", cur_create, info="create node %s" % (full_path))
            # update aspects and tags ?
            set_flags = True
            if ret_val:
                # first write
                pass
            else:
                # update not possible
                call_result = self("Repository", "get", node_pred)
                if call_result:
                    call_result = call_result[0]
                    # node already exists
                    if create_new_version_if_exists:
                        self.log("found previous version, creating new version")
                        self._remove_last_error()
                        ret_val = True
                        set_flags = False
                    else:
                        ret_val = None
                else:
                    call_result = None
                    # hm, strange, remove last error
                    self._remove_last_error()
        if ret_val:
            cur_ref = self.get_reference(full_path)
            if type(f_content) == file:
                f_content = f_content.read()
            if type(f_content) != types.UnicodeType:
                f_content = base64.b64encode(f_content)
            write_res = self("Content", "write", cur_ref,
                             "{%s}content" % (ALFRESCO_MODEL_CONTENT_NS),
                             f_content,
                             cur_type,
                             info="set content (length %d)" % (len(f_content)))
            if write_res:
                if set_flags:
                    cur_create = self["Repository"].factory.create("{%s}CML" % (ALFRESCO_WS_CML_NS))
                    cur_create.addAspect = [CMLaddAspect("{%s}versionable" % (ALFRESCO_MODEL_CONTENT_NS), node_pred),
                                            CMLaddAspect("{%s}generalclassifiable" % (ALFRESCO_MODEL_CONTENT_NS), node_pred)]
                    self("Repository", "update", cur_create, info="set aspects", ignore_errors=True)
                    self.set_tags(node_pred, kwargs.get("tags", []))
                # read node after writing to get the version_label and other stuff
                call_result = self("Repository", "get", node_pred)[0]
        self.__latest_result = call_result
        success = True if not len(self._get_errors()) else False
        return success
    def get_result_node(self):
        return alfresco_content(None, self.get_result())
    def set_tags(self, node_pred, tag_list):
        if tag_list:
            cur_ac = self["Classification"].factory.create("AppliedCategory")
            cur_ac.classification =  "{%s}generalclassifiable" % (ALFRESCO_MODEL_CONTENT_NS)
            cur_ac.categories = [self.get_reference(self.class_tree[cur_tag].id.path) for cur_tag in tag_list]
            self("Classification", "setCategories",
                 node_pred, cur_ac,
                 info="set %s: %s" % (logging_tools.get_plural("tag", len(tag_list)),
                                      ", ".join(tag_list)),
                 ignore_errors=True)
    def update_content(self, uuid, f_content, **kwargs):
        self._fetch_class_tree(cache=True)
        self._init_errors()
        cur_ref = self.get_reference(None, uuid=uuid)
        if type(f_content) == file:
            f_content = f_content.read()
        node_pred = self.get_predicate()
        node_pred.nodes = [cur_ref]
        ret_state, ret_list = self["Repository"].service.get(node_pred)
        cur_content = alfresco_content(None, ret_list[0])
        cur_type = self.get_content_format(**cur_content.get_content_dict())
        write_res = self("Content", "write", cur_ref,
                         "{%s}content" % (ALFRESCO_MODEL_CONTENT_NS),
                         base64.b64encode(f_content),
                         cur_type,
                         info="set content (length %d)" % (len(f_content)))
        call_result = self("Repository", "get", node_pred)[0]
        self.__latest_result = call_result
        success = True if not len(self._get_errors()) else False
        return success
    def load_content(self, **kwargs):
        self._init_errors()
        cur_pred, ret_node = (None, None)
        if "path" in kwargs:
            full_path = kwargs.get("path")
            f_path, f_name = os.path.split(full_path)
            cur_pred = self.get_predicate()
            cur_pred.nodes = [self.get_reference(full_path)]
        elif "uuid" in kwargs:
            cur_pred = self.get_predicate()
            if "version" in kwargs:
                vers_history = self.get_version_history(uuid=kwargs["uuid"])
                if vers_history:
                    cur_pred.nodes = [self.get_reference(None,
                                                         uuid=vers_history[kwargs["version"]],
                                                         path="ver2:versionedState",
                                                         store="version2Store")]
            else:
                cur_pred.nodes = [self.get_reference(None, uuid=kwargs["uuid"])]
        else:
            self.add_error("node location not specified")
        if cur_pred:
            ret_state, ret_list = self["Repository"].service.get(cur_pred)
            if ret_state == 200 and len(ret_list) == 1:
                ret_node = alfresco_content(self, ret_list[0])
        success = ret_node if not len(self._get_errors()) else False
        return success
    def get_version_history(self, **kwargs):
        self._init_errors()
        ret_node = None
        ret_state, ret_list = self["Authoring"].service.getVersionHistory(self.get_reference(None, uuid=kwargs["uuid"]))
        if ret_state == 200:
            ret_node = {}
            if len(ret_list) > 1:
                for cur_vers in ret_list[1]:
                    ret_node[cur_vers.label] = cur_vers.id.uuid
        success = ret_node if not len(self._get_errors()) else False
        return success
    def get_predicate(self, **kwargs):
        self._fetch_stores()
        cur_pred = self["Content"].factory.create("{%s}Predicate" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        if "node" in kwargs:
            cur_pred.nodes = [kwargs["node"]]
        return cur_pred
    def _encode_path(self, f_path):
        return [self._iso9075_encode(part) for part in f_path]
    def _safe_dir_name(self, dir_name, **kwargs):
        if dir_name.endswith("."):
            dir_name = "%s{dot}" % (dir_name[:-1])
        return dir_name.replace(":", "{colon}").replace("/", "{slash}").replace("?", "{qm}").replace('"', "")
    def _iso9075_encode(self, p_part):
        self._first_char = True
        cur_path = "".join([self._iso9075_char(char) for char in p_part])
        return cur_path
    def _iso9075_char(self, char):
        if char.isdigit() and self._first_char:
            char = "_x00%x_" % (ord(char))
        elif char in [" ", ",", ".", "(", ")", ":", "[", "]", "{", "}", "#", "&", "+", u"®", u"ä", u"ö", u"ü", u"Ä", u"Ü", u"Ö", u"°", u"?", unichr(186), unichr(39), '"', "~"]:
            char = "_x00%x_" % (ord(char))
        else:
            pass
        self._first_char = False
        return char
    def get_parent_reference(self, f_path, f_name):
        self._fetch_stores()
        par_ref = self["Content"].factory.create("{%s}ParentReference" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        if type(f_path) in [type(""), type(u"")]:
            f_path = f_path.split("/")
        f_path = self._encode_path(f_path)
        par_ref.path = "/app:company_home/%s" % ("/".join(["cm:%s" % (part) for part in f_path]))
        par_ref.store = self.store_dict["SpacesStore"]
        par_ref.associationType = "{%s}contains" % (ALFRESCO_MODEL_CONTENT_NS)
        par_ref.childName = "{%s}%s" % (ALFRESCO_MODEL_CONTENT_NS, f_name)
        return par_ref
    def get_reference(self, f_path, **kwargs):
        self._fetch_stores()
        cur_ref = self["Content"].factory.create("{%s}Reference" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        if f_path:
            if not f_path.startswith("/"):
                f_path = self._encode_path(f_path.split("/"))
                cor_path = "/app:company_home/%s" % ("/".join(["cm:%s" % (part) for part in f_path]))
            else:
                # path has to be encoded
                cor_path = f_path
            cur_ref.path = cor_path
        else:
            cur_ref.uuid = kwargs["uuid"]
            if "path" in kwargs:
                cur_ref.path = kwargs["path"]
        cur_ref.store = self.store_dict[kwargs.get("store", "SpacesStore")]
        return cur_ref
    def get_content_format(self, **kwargs):
        cur_type = self["Content"].factory.create("{%s}ContentFormat" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        cur_type.encoding = kwargs.get("encoding", "UTF-8")
        cur_type.mimetype = kwargs.get("mimetype", "text/plain")
        return cur_type
    def get_named_value(self, name, value, **kwargs):
        cur_prop = self["Repository"].factory.create("{%s}NamedValue" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        if kwargs.get("add_namespace", True):
            cur_prop.name = "{%s}%s" % (ALFRESCO_MODEL_CONTENT_NS, name)
        else:
            cur_prop.name = name
        cur_prop.isMultiValue = False
        cur_prop.value = value
        return cur_prop
    @keyword_check("ignore_errors", "info")
    def __call__(self, srv_name, call_name, *args, **kwargs):
        ignore_errors = kwargs.get("ignore_errors", False)
        s_time = time.time()
        if "info" in kwargs:
            self.log("%s.%s: %s" % (srv_name,
                                    call_name,
                                    kwargs["info"]))
        ret_state, ret_obj = getattr(self[srv_name].service, call_name)(*args)
        if ret_state not in [200]:
            if not ignore_errors:
                self.log("an error occured for %s (%s): %d" % (srv_name,
                                                               call_name,
                                                               ret_state),
                         logging_tools.LOG_LEVEL_ERROR)
                fault_obj_name = [key for key in dir(ret_obj) if key.lower().endswith("fault")]
                if fault_obj_name:
                    fault_obj_name = fault_obj_name[0]
                    err_str = getattr(ret_obj, fault_obj_name).message
                    self.log("fault message is '%s'" % (err_str),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    err_str = "no fault_message found"
                    self.log(err_str, logging_tools.LOG_LEVEL_ERROR)
                self.add_error("%s.%s: %s%s" % (srv_name,
                                                call_name,
                                                err_str,
                                                " (%s)" % (kwargs["info"]) if "info" in kwargs else ""))
            ret_obj = None
        e_time = time.time()
        self.log("call for %s.%s took %s" % (srv_name,
                                             call_name,
                                             logging_tools.get_diff_time_str(e_time - s_time)))
        return ret_obj

if sys.platform in ["linux2"]:
    # add suds logging on linux hosts
    logging_tools.get_logger("suds.client", "uds:/var/lib/logging-server/py_log", base_log_level=logging.ERROR, init_logger=False)

if __name__ == "__main__":
    print "loadable module, exiting..."
    sys.exit(0)
