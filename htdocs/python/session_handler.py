#!/usr/bin/python-init -Otv
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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

import cPickle
import time
import random
import os
import commands
import cdef_user
from basic_defs import PHP_COMPAT, SESSION_TIMEOUT, USE_SHM_SESSIONS
# pyipc for session handling
if USE_SHM_SESSIONS:
    import pyipc
import pprint

SHM_SESSION_ID = "iwsiMARK"
SHM_FLAG_REBUILD_SERVER_ROUTES = 1

class shm_session_data(object):
    def __init__(self, shm_id, create):
        self.__shm_id = shm_id
        if create:
            self.__shm = pyipc.SharedMemory(self.__shm_id, 10000, (0600 | pyipc.IPC_CREAT | pyipc.IPC_EXCL), True)
            # write marker
            self.__shm[1] = SHM_SESSION_ID
        else:
            self.__shm = pyipc.SharedMemory(self.__shm_id, 10000, (0600), True)
            if self.__shm._get(1, len(SHM_SESSION_ID)) != SHM_SESSION_ID:
                raise EnvironmentError
            self.__flags = self.__shm.readInt(10)
            self.__content_len = self.__shm.readInt(18)
        self.__shm.detach()
    def get_shm_id(self):
        return self.__shm_id
    def get_content_len(self):
        return self.__content_len
    def get_flags(self):
        return self.__flags
    def set_flags(self, fl):
        self.__flags = fl
        self.__shm.attach()
        self.__shm.writeInt(10, self.__flags)
        self.__shm.detach()
    def get_dict(self):
        self.__shm.attach()
        if self.__content_len:
            try:
                in_dict = cPickle.loads(self.__shm._get(24, self.__content_len))
            except:
                in_dict = None
        else:
            in_dict = None
        self.__shm.detach()
        if in_dict is None:
            raise EnvironmentError
        else:
            return in_dict
    def set_dict(self, in_dict):
        self.__shm.attach()
        dict_str = cPickle.dumps(in_dict)
        self.__content_len = len(dict_str)
        self.__shm.writeInt(18, self.__content_len)
        self.__shm[24] = dict_str
        self.__shm.detach()
        
class session_data(object):
    def __init__(self, sess_id, php_compat = False):
        self.__slots = ["user", "user_idx", "group_idx"]
        self.__id = sess_id
        # generate shm_id
        self.__shm_id = generate_shm_id(self.__id)
        if php_compat:
            self.__php_id = "".join([chr(random.randint(97, 122)) for x in range(16)])
        else:
            self.__php_id = None
        self.__user_info = None
        self.__properties = {}
        # attached share-memory segment
        self.__shm = None
        self.set_php_update()
    def set_php_update(self, pu=False):
        self.__update_php = pu
    def get_user_info(self):
        return self.__user_info
    def get_session_id(self):
        return self.__id
    def get_shm_id(self):
        return self.__shm_id
    def get_php_session_id(self):
        return self.__php_id
    def set_property(self, p_name, p_val):
        self.__properties[p_name] = p_val
    def get_property(self, p_name, def_value=None):
        return self.__properties.setdefault(p_name, def_value)
    def has_property(self, p_name):
        return self.__properties.has_key(p_name)
    def del_property(self, p_name):
        del self.__properties[p_name]
    def init_session_from_dict(self, in_dict, remote_ip):
        self.user      = in_dict["user"]
        self.user_idx  = in_dict["user_idx"]
        self.group_idx = in_dict["group_idx"]
        self.alias     = in_dict["alias"]
        self.__remote_ip = remote_ip
        self.set_property("remote_ip", remote_ip)
        self._check_session()
    def init_session_from_shm(self):
        self.__shm = shm_session_data(self.__shm_id, False)
        in_dict = self.__shm.get_dict()
        if self.__shm.get_flags() & SHM_FLAG_REBUILD_SERVER_ROUTES and in_dict.has_key("server_routes"):
            self.__shm.set_flags(self.__shm.get_flags() & ~ SHM_FLAG_REBUILD_SERVER_ROUTES)
            del in_dict["server_routes"]
        self.init_session(in_dict)
    def init_session_from_db(self, dc):
        dc.execute("SELECT * FROM session_data WHERE session_id='%s' AND NOT logout_time" % (self.__id))
        if not dc.rowcount:
            raise EnvironmentError
        sql_row = dc.fetchone()
        in_dict = cPickle.loads(sql_row["value"])
        if sql_row.get("rebuild_server_routes", 0) and in_dict.has_key("server_routes"):
            del in_dict["server_routes"]
        self.init_session(in_dict)
    def init_session(self, in_dict):
        self.alias = ""
        for key, value in in_dict.iteritems():
            if key in ["user", "user_idx", "group_idx", "alias"]:
                setattr(self, key, value)
            elif key == "php_session_id":
                self.__php_id = value
            else:
                self.set_property(key, value)
        self._check_session()
    def _check_session(self):
        # make various tests
        if self.alias:
            self.is_alias_login = True
        else:
            self.is_alias_login = False
    def add_user_info(self, dc, user_definition):
        sql_str = "SELECT u.*, uv.* FROM ggroup g INNER JOIN user u LEFT JOIN user_var uv ON uv.user=u.user_idx WHERE u.active AND g.active AND u.ggroup=g.ggroup_idx AND u.user_idx='%d'" % (self.user_idx)
        dc.execute(sql_str)
        for db_rec in dc.fetchall():
            if not self.__user_info:
                self.__user_info = user_definition(db_rec["login"], db_rec["user_idx"], db_rec)
            if db_rec["type"]:
                self.__user_info.add_user_var(dict([(key, db_rec[key]) for key in ["name", "type", "value", "hidden", "user", "user_var_idx", "description", "editable"]]))
    def init_persistence(self, dc):
        if USE_SHM_SESSIONS:
            self.init_shm()
        self.init_db(dc)
    def init_shm(self):
        self.__shm = shm_session_data(self.__shm_id, True)
    def init_db(self, dc):
        dc.execute("INSERT INTO session_data SET session_id=%s, user_idx=%s, remote_addr=%s, login_time=NOW(), logout_time=0, value='', alias=%s", (self.__id,
                                                                                                                                                    self.user_idx,
                                                                                                                                                    self.__remote_ip,
                                                                                                                                                    self.alias))
        if self.__php_id:
            dc.execute("INSERT INTO session_data SET session_id=%s, user_idx=%s, remote_addr=%s, login_time=NOW(), logout_time=0, value='', alias=%s", (self.__php_id,
                                                                                                                                                        self.user_idx,
                                                                                                                                                        self.__remote_ip,
                                                                                                                                                        self.alias))
    def generate_db_dict(self):
        db_dict = {"user"       : self.user,
                   "user_idx"   : self.user_idx,
                   "group_idx"  : self.group_idx,
                   "alias"      : self.alias}
        if self.__php_id:
            db_dict["php_session_id"] = self.__php_id
        if self.__shm_id:
            db_dict["shm_id"] = self.__shm_id
        db_dict.update(self.__properties)
        return db_dict
    def update(self, dc, force_update=False):
        self.set_property("page_views", self.get_property("page_views", 0) + 1)
        db_dict = self.generate_db_dict()
        if USE_SHM_SESSIONS:
            self.__shm.set_dict(db_dict)
        if self.get_property("page_views") % 10 == 0 or self.get_property("page_views") < 3 or self.__update_php or force_update or not USE_SHM_SESSIONS:
            dc.execute("UPDATE session_data SET rebuild_server_routes=0, value=%s WHERE session_id=%s", (cPickle.dumps(db_dict),
                                                                                                         self.__id))
            if self.__update_php or force_update:
                self.update_php_session(dc)
        if self.__user_info:
            self.__user_info.save_modified_user_vars(dc)
    def update_php_session(self, dc):
        if self.__php_id:
            sd_array = []
            for key in ["user_idx", "page_views", "group_idx", "user", "session_id"]:
                if key == "session_id":
                    val = self.__id
                elif key == "page_views":
                    val = str(self.get_property(key, 1))
                else:
                    val = str(getattr(self, key))
                sd_array.append("%s|%s:%s:\"%s\"" % ({"user"      : "session_user",
                                                      "group_idx" : "ggroup_idx"}.get(key, key), "s", len(val), val))
            sd_array.append("")
            dc.execute("UPDATE session_data SET value='%s' WHERE session_id='%s'" % (";".join(sd_array), self.__php_id))
    def close(self, dc):
        self.update(dc, True)
        dc.execute("UPDATE session_data SET logout_time=NOW() WHERE session_id='%s'" % (self.__id))
        if self.__php_id:
            dc.execute("UPDATE session_data SET logout_time=NOW() WHERE session_id='%s'" % (self.__php_id))
        if self.__shm_id and USE_SHM_SESSIONS:
            delete_shm(self.__shm_id)


def generate_shm_id(w_id):
    s_id = 0
    for x_e in w_id:
        s_id = (s_id << 2) ^ ord(x_e)
    # limit to lower 32 bits
    s_id = s_id & ((1 << 31) - 1)
    return s_id

def get_act_shm_dict():
    shm_dict = {}
    all_shm_ids = get_all_shm_ids()
    for key, value in all_shm_ids.iteritems():
        if value["key"]:
            try:
                new_shm = shm_session_data(value["key"], False)
            except:
                pass
            else:
                shm_dict[new_shm.get_shm_id()] = new_shm
    return shm_dict

def get_all_shm_ids():
    my_uid, my_gid = (os.getuid(), os.getgid())
    try:
        # 'not' is needed for '0'-strings
        all_shm_ids = [[not y.isdigit() and y or int(y) for y in x.strip().split()] for x in file("/proc/sysvipc/shm", "r").read().split("\n") if x.strip()]
    except:
        all_shm_ids = {}
    else:
        headers = all_shm_ids.pop(0)
        all_shm_ids = dict([(x[1], dict([(k, v) for k, v in zip(headers, x)])) for x in all_shm_ids])
        all_shm_ids = dict([(k, v) for k, v in all_shm_ids.iteritems() if v["cgid"] == my_gid and v["cuid"] == my_uid])
    return all_shm_ids

def delete_shm(shm_key):
    com = "/usr/bin/ipcrm -M %d" % (shm_key)
    try:
        stat, out = commands.getstatusoutput(com)
    except:
        pass
            
def init_session(req, sess_id, sess_dict):
    session_gc(req)
    s_data = session_data(sess_id, PHP_COMPAT)
    s_data.init_session_from_dict(sess_dict, req.environ["REMOTE_ADDR"])
    s_data.init_persistence(req.dc)
    s_data.add_user_info(req.dc, cdef_user.user)
    s_data.update(req.dc)
    req.session_data = s_data
    req.user_info = s_data.get_user_info()

def read_session(req, sess_id):
    s_data = session_data(sess_id)
    try:
        if USE_SHM_SESSIONS:
            s_data.init_session_from_shm()
        else:
            raise EnvironmentError
    except:
        try:
            s_data.init_session_from_db(req.dc)
        except:
            s_data = None
            req.info_stack.add_error("Session : Unknown or invalid session-id '%s'" % (sess_id), "auth")
            req.session_data = None
    if s_data:
        s_data.add_user_info(req.dc, cdef_user.user)
        req.session_data = s_data
        req.user_info = s_data.get_user_info()

def update_session(req):
    if req.session_data:
        req.session_data.update(req.dc)

def delete_session(req):
    if req.session_data:
        req.session_data.close(req.dc)
        req.session_data = None
    session_gc(req)

def session_gc(req):
    # delete old php-sessions
    req.dc.execute("SELECT UNIX_TIMESTAMP(date) AS upd_ts, session_id, value FROM session_data WHERE NOT logout_time")
    del_sessions, php_sessions, sub_php_session_ids, del_shm_ids = ([], [], [], [])
    for db_rec in req.dc.fetchall():
        #print x
        try:
            s_value = cPickle.loads(db_rec["value"])
        except:
            php_sessions.append(db_rec["session_id"])
        else:
            if time.time() - db_rec["upd_ts"] > SESSION_TIMEOUT:
                del_sessions.append(db_rec["session_id"])
                if s_value and s_value.has_key("php_session_id"):
                    sub_php_session_ids = s_value["php_session_id"]
                if s_value.has_key("shm_id"):
                    del_shm_ids.append(s_value["shm_id"])
                else:
                    del_shm_ids.append(generate_shm_id(db_rec["session_id"]))
    #print del_sessions, php_sessions, sub_php_session_ids
    del_sessions.extend([x for x in php_sessions if x in sub_php_session_ids])
    if del_sessions:
        req.dc.execute("UPDATE session_data SET logout_time=NOW(), forced_logout=1 WHERE %s" % (" OR ".join(["session_id='%s'" % (x) for x in del_sessions])))
    if del_shm_ids:
        for del_shm_id in del_shm_ids:
            delete_shm(del_shm_id)
