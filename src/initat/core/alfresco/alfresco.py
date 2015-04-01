# -*- coding: utf-8 -*-

"""
Toolkit for accessing Alfresco. The alfresco_handler is the class
that does all the work for us.
"""

import process_tools
import cmislib
import time
import re
import logging_tools
import os
import mimetypes
import StringIO

from pkg_resources import require
require("Suds")
import suds
from suds.client import Client
from suds.sax.element import Element
import suds.wsse

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile

from initat.core.utils import keyword_check

ALFRESCO_WS_CML_NS = "http://www.alfresco.org/ws/cml/1.0"
ALFRESCO_WS_MODEL_CONTENT_NS = "http://www.alfresco.org/ws/model/content/1.0"
ALFRESCO_WS_SERVICE_CONTENT_NS = "http://www.alfresco.org/ws/service/content/1.0"
ALFRESCO_WS_SERVICE_CLASS_NS = "http://www.alfresco.org/ws/service/classification/1.0"
ALFRESCO_MODEL_CONTENT_NS = "http://www.alfresco.org/model/content/1.0"
ALFRESCO_MODEL_SYSTEM_NS = "http://www.alfresco.org/model/system/1.0"
ALFRESCO_MODEL_APPLICATION_NS = "http://www.alfresco.org/model/application/1.0"


def get_uuid(document):
    """
    Return the UUID of an alfresco cmislib document.
    """
    return document.getObjectId()[-36:]


def get_content_dict(in_str):
    return dict([(str(key), value) for key, value in [sub_str.split("=", 1) for sub_str in in_str.split("|")[1:]]])


class CMLUpdate(suds.wsse.Token):
    def __init__(self, where, prop_list):
        suds.wsse.Token.__init__(self)
        self.where = where
        self.property = prop_list


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
        self.cmis_url = "http://%s:%d/alfresco/service/cmis" % (self.host,
                                                                self.port)
        self.log("base_url is '%s' / '%s'" % (self.base_url,
                                              self.cmis_url))
        self.__admin_user, self.__admin_password = (None, None)
        self.__admin_session, self.__user_session = (None, None)
        self.__clients = {}
        self.store_dict = None
        self.class_dict = None
        self.__cmis_client = None
        self.__cmis_result = None
        self.__error_list = []
        self.__user_security = None
        self.__admin_security = None
        self._first_char = True
        self._init_errors()

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

    def get_cmis_client(self):
        if not self.__cmis_client:
            self.__cmis_client = cmislib.CmisClient(self.cmis_url, self.__user, self.__password)
        return self.__cmis_client

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

    def get_user_session(self):
        return self.__user_session

    @property
    def stores(self):
        if not self.store_dict:
            self._fetch_stores()
        return self.store_dict

    def _fetch_stores(self):
        self.store_dict = dict([(cur_store.address, cur_store) for cur_store in self["Repository"].service.getStores()[1]])
        self.log("fetched %s: %s" % (
            logging_tools.get_plural("store", len(self.store_dict)),
            ", ".join(sorted(self.store_dict))))

    @property
    def classes(self):
        if not self.class_dict:
            self._fetch_classes()
        return self.class_dict

    def _fetch_classes(self, parent=None, parent_name=None, **kwargs):
        if parent is None:
            self.class_dict = {}
            cur_classes = [cur_class.rootCategory for cur_class in self["Classification"].service.getClassifications(self.stores["SpacesStore"])[1] if cur_class.rootCategory.title in ["Tags"]]
            prefix = ""
        else:
            cur_classes = self["Classification"].service.getChildCategories(parent)[1]
            prefix = "%s/" % (parent_name)
        for cur_class in cur_classes:
            cur_name = "%s%s" % (prefix, cur_class.title)
            self.class_dict[cur_class.id.path] = cur_class
            self.class_dict[cur_name] = cur_class
            self._fetch_classes(self.get_reference(cur_class.id.path), cur_name)
        if not parent:
            short_tags = [key for key in self.class_dict.keys() if not key.startswith("/")]
            self.log("found %s: %s" % (logging_tools.get_plural("tag", len(short_tags)),
                                       ", ".join(sorted(short_tags))))

    def __getitem__(self, sess_type):
        if sess_type not in self.__clients:
            if settings.DEBUG:
                self.__clients[sess_type] = Client(url=self.get_url(sess_type), cache=None, faults=False)
            else:
                self.__clients[sess_type] = Client(url=self.get_url(sess_type), cache=suds.cache.ObjectCache(days=1), faults=False)
        if sess_type not in ["Authentication"]:
            self.__clients[sess_type].set_options(wsse=self.create_user_session())
        return self.__clients[sess_type]

    def close(self):
        if self.__cmis_client:
            del self.__cmis_client
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

    def _node_exists(self, full_path, **kwargs):
        cmis_client = self.get_cmis_client()
        try:
            cmis_client.defaultRepository.getObjectByPath(self._safe_full_path(full_path))
        except cmislib.exceptions.ObjectNotFoundException:
            return False
        else:
            return True

    def get_dir_list(self, full_path, **kwargs):
        return self.get_cmis_client().defaultRepository.getObjectByPath(self._safe_full_path(full_path)).getChildren()

    def move_node(self, src_uuid, dst_path, **kwargs):
        cmis_client = self.get_cmis_client()
        cur_node = cmis_client.defaultRepository.getObject("workspace://SpacesStore/%s" % (src_uuid))
        parent_dir = cur_node.getObjectParents()[0]
        cur_node.move(parent_dir, cmis_client.defaultRepository.getObjectByPath(dst_path))
        return True

    def delete_node(self, **kwargs):
        try:
            old_node = self.get_cmis_client().defaultRepository.getObject("workspace://SpacesStore/%s" % (kwargs["uuid"]))
        except cmislib.exceptions.ObjectNotFoundException:
            return False
        else:
            old_node.delete()
            return True

    def create_folder(self, full_path, **kwargs):
        my_client = self.get_cmis_client()
        def_repo = my_client.defaultRepository
        f_path, dir_name_ci = os.path.split(full_path)
        self.log("using cmislib for folder creation (%s beneath %s)" % (dir_name_ci, f_path))
        try:
            parent_node = def_repo.getObjectByPath(self._safe_full_path(f_path))
        except cmislib.exceptions.ObjectNotFoundException:
            if kwargs.get("recursive", False):
                self.create_folder(f_path, **kwargs)
            else:
                self.add_error("parent folder '%s' does not exist" % (f_path))
            try:
                parent_node = def_repo.getObjectByPath(self._safe_full_path(f_path))
            except cmislib.exceptions.ObjectNotFoundException:
                # silent fail
                pass
        else:
            pass
        if not self._get_errors():
            try:
                def_repo.getObjectByPath(self._safe_full_path(full_path))
            except cmislib.exceptions.ObjectNotFoundException:
                new_folder = parent_node.createFolder(self._safe_path(dir_name_ci))
                self.set_properties(
                    new_folder.properties["cmis:objectId"].split("/")[-1],
                    dict([(key, kwargs[key]) for key in ["author", "description"] if key in kwargs]))
            else:
                self.log("folder '%s' already exists in '%s'" % (dir_name_ci,
                                                                 f_path))
        del my_client
        success = True if not len(self._get_errors()) else False
        if success and kwargs.get("return_path_on_success"):
            return full_path
        else:
            return success

    def store_content(self, full_path, f_content, **kwargs):
        self.__cmis_result = None
        # full_path can be a simple filename if parent_uuid is set
        dummy_path, f_name = os.path.split(full_path)
        self._init_errors()
        # f_name_ci : case insensitive f_name
        f_path, f_name_ci = os.path.split(full_path)
        # guess mimetype if not set
        if "mimetype" not in kwargs:
            g_mimetype, unused = mimetypes.guess_type(f_name)
            if g_mimetype:
                kwargs["mimetype"] = g_mimetype
            else:
                kwargs["mimetype"] = "text/plain"
        my_cmis = self.get_cmis_client()
        parent_node = my_cmis.defaultRepository.getObjectByPath(self._safe_full_path(f_path))
        check_for_existing = kwargs.get("check_for_existing", False)
        if check_for_existing:
            try:
                new_node = my_cmis.defaultRepository.getObjectByPath(self._safe_full_path(full_path))
            except cmislib.exceptions.ObjectNotFoundException:
                new_node = None
            else:
                self.__cmis_result = new_node
            #node_exists = self._node_exists(full_path, ignore_errors=True, init_errors=False)
            if new_node is not None:
                self.log("node '%s' in %s already exists" % (f_name_ci,
                                                             f_path))
        if not new_node:
            new_node = parent_node.createDocument(self._safe_dir_name(f_name))  # , properties={"cmis:author" : "x",
                                                                                #             "cmis:description" : "my_desc"})

            self.__cmis_result = new_node
            self.set_tags(new_node.properties["cmis:objectId"].split("/")[-1],
                          kwargs.get("tags", []))
        if new_node:
            self.log("content for path '%s' is of type %s" % (full_path,
                                                              type(f_content)))
            if type(f_content) == file:
                f_content_obj = f_content
            elif type(f_content) in [InMemoryUploadedFile, TemporaryUploadedFile]:
                f_content_obj = f_content
            else:
                if type(f_content) == unicode:
                    f_content_obj = StringIO.StringIO(f_content.encode("utf-8"))
                else:
                    f_content_obj = StringIO.StringIO(f_content)
            new_node.setContentStream(contentFile=f_content_obj, contentType=str(kwargs["mimetype"]))
            # here starts the alfresco SOAP part
            self.set_properties(
                new_node.properties["cmis:objectId"].split("/")[-1],
                dict([(key, kwargs[key]) for key in ["author", "description"] if key in kwargs]))
            # reread node to get version correct
            new_node = my_cmis.defaultRepository.getObject(new_node.properties["cmis:objectId"])
            self.__cmis_result = new_node
        del my_cmis
        success = True
        return success

    def set_properties(self, node_uuid, prop_dict):
        prop_list = self.get_property_list(**prop_dict)
        if len(prop_list):
            cur_ref = self["Content"].factory.create("{%s}Reference" % (ALFRESCO_WS_MODEL_CONTENT_NS))
            cur_ref.uuid = node_uuid
            cur_ref.store = self.stores["SpacesStore"]
            node_pred = self["Content"].factory.create("{%s}Predicate" % (ALFRESCO_WS_MODEL_CONTENT_NS))
            node_pred.nodes = [cur_ref]
            cur_create = self["Repository"].factory.create("{%s}CML" % (ALFRESCO_WS_CML_NS))
            cur_create.update = CMLUpdate(node_pred,
                                          prop_list)
            try:
                self("Repository", "update", cur_create)
            except Exception:  # pylint: disable-msg=W0703
                self.log("update failed: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)

    def get_property_list(self, **kwargs):
        return [self.get_named_value(**{key: value}) for key, value in kwargs.iteritems()]

    def get_named_value(self, **kwargs):
        cur_prop = self["Repository"].factory.create("{%s}NamedValue" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        cur_prop.isMultiValue = False
        for key, value in kwargs.iteritems():
            cur_prop.name = "{%s}%s" % (ALFRESCO_MODEL_CONTENT_NS, key)
            cur_prop.value = value
        return cur_prop

    def get_result_node(self):
        if self.__cmis_result:
            return self.__cmis_result
        else:
            return None

    def set_tags(self, node_uuid, tag_list):
        if tag_list:
            cur_ref = self["Content"].factory.create("{%s}Reference" % (ALFRESCO_WS_MODEL_CONTENT_NS))
            cur_ref.uuid = node_uuid
            cur_ref.store = self.stores["SpacesStore"]
            node_pred = self["Content"].factory.create("{%s}Predicate" % (ALFRESCO_WS_MODEL_CONTENT_NS))
            node_pred.nodes = [cur_ref]
            cur_ac = self["Classification"].factory.create("AppliedCategory")
            cur_ac.classification = "{%s}generalclassifiable" % (ALFRESCO_MODEL_CONTENT_NS)
            cur_ac.categories = [self.get_reference(self.classes[cur_tag].id.path) for cur_tag in tag_list]
            self("Classification", "setCategories",
                 node_pred,
                 cur_ac,
                 info="set %s: %s" % (logging_tools.get_plural("tag", len(tag_list)),
                                      ", ".join(tag_list)),
                 ignore_errors=True)

    def update_content(self, uuid, f_content, **kwargs):
        my_cmis = self.get_cmis_client()
        cur_node = self.get_node_by_uuid(uuid)
        if type(f_content) == unicode:
            f_obj = StringIO.StringIO(f_content.encode("utf-8"))
        else:
            f_obj = StringIO.StringIO(f_content)
        cur_node.setContentStream(contentFile=f_obj)
        cur_node = my_cmis.defaultRepository.getObject(cur_node.properties["cmis:objectId"])
        self.__cmis_result = cur_node
        del my_cmis
        return True

    def load_content(self, **kwargs):
        self.log("using cmislib for downloading")
        my_client = self.get_cmis_client()
        def_repo = my_client.defaultRepository
        if "path" in kwargs:
            sub_node = def_repo.getObjectByPath(self._safe_full_path(kwargs["path"]))
        elif "uuid" in kwargs:
            sub_node = def_repo.getObject("workspace://SpacesStore/%s" % (kwargs["uuid"]))
        del my_client
        if "version" in kwargs:
            sub_node = dict([(cn.properties["cmis:versionLabel"], cn) for cn in sub_node.getAllVersions()])[kwargs["version"]]
        ret_node = sub_node
        success = ret_node if not len(self._get_errors()) else False
        return success

    def get_version_history(self, **kwargs):
        """ returns version history for given uuid """
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

    def _encode_path(self, f_path):
        return [self._iso9075_encode(part) for part in f_path]

    def _safe_full_path(self, path):
        c_path = self._safe_path(path)
        if not c_path.startswith("/"):
            c_path = u"/%s" % (c_path)
        return c_path.encode("utf-8")

    def _safe_path(self, path):
        head, tail = os.path.split(path)
        if head:
            head = self._safe_path(head)
        c_path = os.path.join(head, self._safe_dir_name(tail))
        return c_path

    def _safe_dir_name(self, dir_name, **kwargs):
        if dir_name.endswith("."):
            dir_name = "%s{dot}" % (dir_name[:-1])
        return dir_name.replace(":", "{colon}").replace("/", "{slash}").replace("?", "{qm}").replace('"', "")  # .replace("*", "{star}")

    def _iso9075_encode(self, p_part):
        self._first_char = True
        cur_path = "".join([self._iso9075_char(char) for char in p_part])
        return cur_path

    def _iso9075_char(self, char):
        if char.isdigit() and self._first_char:  # and False:
            char = "_x00%x_" % (ord(char))
        elif char in [" ", ",", ".", "(", ")", ":", "[", "]", "{", "}", "#", "&", "+", u"®", u"°", u"?", unichr(186), unichr(39), '"', "~", ";", "!", "\\", "%", u"§", "$", u"´"]:
            char = "_x00%x_" % (ord(char))
        else:
            pass
        self._first_char = False
        return char

    def _iso9075_recode(self, p_part):
        iso_re = re.compile("^(?P<pre>.*)_x00(?P<code>[^_]+)_(?P<post>.*)")
        while True:
            re_found = iso_re.match(p_part)
            if re_found:
                p_part = "".join([re_found.group("pre"),
                                  unichr(int(re_found.group("code"), 16)),
                                  re_found.group("post")])
            else:
                break
        return p_part

    def get_parent_reference(self, f_path, f_name, **kwargs):
        """ return ParentReference structure, case sensitive """
        par_ref = self["Content"].factory.create("{%s}ParentReference" % (ALFRESCO_WS_MODEL_CONTENT_NS))
        if f_path:
            if type(f_path) in [type(""), type(u"")]:
                f_path = f_path.split("/")
                f_path = self._encode_path(f_path)
            par_ref.path = "/app:company_home/%s" % ("/".join(["cm:%s" % (part) for part in f_path]))
        else:
            par_ref.uuid = kwargs["parent_uuid"]
        par_ref.store = self.stores["SpacesStore"]
        par_ref.associationType = "{%s}contains" % (ALFRESCO_MODEL_CONTENT_NS)
        par_ref.childName = "{%s}%s" % (ALFRESCO_MODEL_CONTENT_NS, f_name)
        return par_ref

    def get_node_by_uuid(self, uuid, **kwargs):
        return self.get_cmis_client().getObject("workspace://SpacesStore/%s" % (uuid))  # pylint: disable-msg=E1101

    def get_node_by_path(self, full_path, **kwargs):
        return self.get_cmis_client().defaultRepository.getObjectByPath(self._safe_full_path(full_path))

    def get_reference(self, f_path, **kwargs):
        """ return Reference structure, case sensitive """
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
        cur_ref.store = self.stores["SpacesStore"]
        return cur_ref

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
