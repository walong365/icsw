#!/usr/bin/python-init -Otv
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2012 Andreas Lang-Nevyjel, init.at
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
import datetime
from basic_defs import SESSION_TIMEOUT
import process_tools
from init.cluster.backbone.models import user, session_data, user_var
from django.db.models import Q

class session_data_obj(object):
    def __init__(self, sess_id, user_info):
        self.__slots = ["user", "user_idx", "group_idx"]
        self.__id = sess_id
        self.user_info = user_info
        self.__properties = {}
        self.session_obj = None
        self.alias = ""
    def get_user_info(self):
        return self.user_info
    def get_session_id(self):
        return self.__id
    def set_property(self, p_name, p_val):
        self.__properties[p_name] = p_val
    def get_property(self, p_name, def_value=None):
        return self.__properties.setdefault(p_name, def_value)
    def has_property(self, p_name):
        return self.__properties.has_key(p_name)
    def del_property(self, p_name):
        del self.__properties[p_name]
    def init_session_from_dict(self, in_dict, remote_ip):
        self.__remote_ip = remote_ip
        self.set_property("remote_ip", remote_ip)
        self._check_session()
    def init_session_from_db(self):
        my_session = session_data.objects.filter(Q(logout_time=None) & Q(session_id=self.__id)).select_related("user")
        if not my_session:
            raise EnvironmentError
        my_session = my_session[0]
        self.session_obj = my_session
        self.user_info = my_session.user
        in_dict = cPickle.loads(str(my_session.value))
        if my_session.rebuild_server_routes and "server_routes" in in_dict:
            del in_dict["server_routes"]
        self.init_session(in_dict)
    def init_session(self, in_dict):
        for key, value in in_dict.iteritems():
            if key in ["user", "user_idx", "group_idx", "alias"]:
                setattr(self, key, value)
            else:
                self.set_property(key, value)
        self._check_session()
    def _check_session(self):
        # make various tests
        if self.alias:
            self.is_alias_login = True
        else:
            self.is_alias_login = False
    def add_user_info(self):
        my_vars = user_var.objects.filter(Q(user=self.user_info) & Q(user__active=True) & Q(user__group__active=True)).select_related("user")
##        sql_str = "SELECT u.*, uv.* FROM ggroup g INNER JOIN user u LEFT JOIN user_var uv ON uv.user=u.user_idx WHERE u.active AND g.active AND u.ggroup=g.ggroup_idx AND u.user_idx='%d'" % (self.user_idx)
##        dc.execute(sql_str)
        for my_var in my_vars:
            if my_var.type:
                self.user_info.add_user_var(my_var)
    def init_persistence(self):
        self.init_db()
    def init_db(self):
        new_sess = session_data(
            session_id=self.__id,
            login_time=datetime.datetime.now(),
            value=cPickle.dumps({}),
            user=self.user_info,
            remote_addr=self.__remote_ip,
            alias=self.alias)
        new_sess.save()
##        dc.execute("INSERT INTO session_data SET session_id=%s, user_idx=%s, remote_addr=%s, login_time=NOW(), logout_time=0, value='', alias=%s", (self.__id,
##                                                                                                                                                    self.user_idx,
##                                                                                                                                                    self.__remote_ip,
##                                                                                                                                                    self.alias))
    def generate_db_dict(self):
        db_dict = {}
##        db_dict = {"user"       : self.user,
##                   "user_idx"   : self.user_idx,
##                   "group_idx"  : self.group_idx,
##                   "alias"      : self.alias}
        db_dict.update(self.__properties)
        return db_dict
    def update(self, force_update=False):
        self.set_property("page_views", self.get_property("page_views", 0) + 1)
        db_dict = self.generate_db_dict()
        if self.session_obj:
            self.session_obj.value = cPickle.dumps(db_dict)
            self.session_obj.save()
        if self.user_info:
            self.user_info.save_modified_user_vars()
    def close(self):
        self.update(True)
        my_session = session_data.objects.get(session_id=self.__id)
        my_session.logout_time = datetime.datetime.now()
        my_session.save()

def init_session(req, sess_id, user_info, sess_dict):
    session_gc()
    s_data = session_data_obj(sess_id, user_info)
    s_data.init_session_from_dict(sess_dict, req.environ["REMOTE_ADDR"])
    s_data.add_user_info()
    s_data.init_persistence()
    s_data.update()
    #req.session_data = s_data
    #req.user_info = s_data.get_user_info()

def read_session(req, sess_id):
    s_data = session_data_obj(sess_id, None)
    try:
        s_data.init_session_from_db()
    except:
        s_data = None
        print "session error:", process_tools.get_except_info()
        req.info_stack.add_error("Session : Unknown or invalid session-id '%s'" % (sess_id), "auth")
        req.session_data = None
    if s_data:
        s_data.add_user_info()
        req.session_data = s_data
        req.user_info = s_data.get_user_info()
    return s_data

def update_session(req):
    if req.session_data:
        req.session_data.update()

def delete_session(sess_data):
    if sess_data:
        sess_data.close()
    session_gc()

def session_gc():
    act_sessions = session_data.objects.filter(Q(logout_time=None))
    del_sessions = []
    for db_rec in act_sessions:
        #print x
        try:
            s_value = cPickle.loads(db_rec["value"])
        except:
            pass
        else:
            print db_rec
            if time.time() - db_rec["upd_ts"] > SESSION_TIMEOUT:
                del_sessions.append(db_rec.pk)
    if del_sessions:
        session_data.objects.filter(Q(pk__in=del_sessions)).delete()
