#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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
""" restore users / groups from old CSW """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.db.models import Q
from initat.cluster.backbone.models import group, user
from lxml import etree # @UnresolvedImport
import codecs
import logging_tools

OBJ_DICT = {
    "user" : user,
    "group" : group,
}

def main():
    if len(sys.argv) != 3:
        print "need group und user XML name"
        sys.exit(-1)
    _xml = {}
    for xml_type, name in zip(["group", "user"], sys.argv[1:3]):
        _xml[xml_type] = etree.fromstring(codecs.open(name, "r", "utf-8").read())
        print("read %s from %s, found %s" % (
            xml_type,
            name,
            logging_tools.get_plural("entry", len(_xml[xml_type])),
        ))
    # integer / boolean fields
    int_fields = ["uid", "gid", "ggroup_idx", "user_idx", "ggroup"]
    boolean_fields = ["active"]
    group_dict, group_lut = ({}, {})
    # step 1: group
    for c_type in ["group", "user"]:
        new_ot = OBJ_DICT[c_type]
        sprim_field, prim_field = {
            "group" : ("ggroupname", "groupname"),
            "user"  : ("login", "login")}[c_type]
        copy_fields = {
            "group" : [
                "active", "gid", "homestart", "scratchstart",
                ("respvname", "first_name"), ("respnname", "last_name"),
                ("resptitan", "title"), ("respemail", "email"),
                ("resptel", "tel"), ("respcom", "comment"),
                ("groupcom", "comment"), ("ggroupname" , "groupname"),
                ],
            "user" : [
                "active", "uid", "login", "aliases", "home", "shell",
                "password", "password_ssha",
                ("uservname", "first_name"), ("usernname", "last_name"),
                ("usertitan", "title"), ("useremail", "email"),
                ("userpager", "pager"), ("usercom", "comment"),
                "nt_password", "lm_password",
                ],
        }.get(c_type, [])
        def_fields = {
            "group" : {"email" : ""},
            "user"  : {"first_name" : "", "last_name" : "", "title" : "", "pager" : "", "tel" : "",
                       "nt_password" : "", "lm_password" : "", "email" : "", "comment" : ""},
        }.get(c_type, {})
        for new_obj in _xml[c_type]:
            # print etree.tostring(new_obj, pretty_print=True)
            src_dict = dict([(key, new_obj.xpath(".//field[@name='%s']/text()" % (key))) for key in new_obj.xpath(".//field[@name]/@name")])
            src_dict = dict([(key, value[0] if len(value) else None) for key, value in src_dict.iteritems()])
            prim_value = src_dict[sprim_field]
            for key in src_dict.iterkeys():
                if key in int_fields:
                    src_dict[key] = int(src_dict[key])
                elif key in boolean_fields:
                    src_dict[key] = True if int(src_dict[key]) else False
                else:
                    src_dict[key] = unicode(src_dict[key])
            try:
                db_obj = new_ot.objects.get(Q(**{prim_field : prim_value}))
            except new_ot.DoesNotExist:
                print("%s with %s='%s' not found, creating new" % (
                    c_type,
                    prim_field,
                    prim_value)
                      )
                db_obj = new_ot()
                if c_type == "user":
                    db_obj.group = group_lut[src_dict["ggroup"]]
                db_obj.save()
            else:
                print("%s with %s='%s' already exists" % (
                    c_type,
                    prim_field,
                    prim_value)
                      )
                if c_type == "user":
                    if db_obj.export_id == 0:
                        db_obj.export = None

            for copy_id in copy_fields:
                if type(copy_id) == tuple:
                    src_key, dst_key = (copy_id[0], copy_id[1])
                else:
                    src_key, dst_key = (copy_id, copy_id)
                if src_key in src_dict:
                    new_val = src_dict[src_key]
                    if not new_val:
                        new_val = def_fields.get(dst_key, new_val)
                    if dst_key == "password":
                        new_val = "CRYPT:%s" % (new_val)
                    setattr(db_obj, dst_key, new_val)
            if c_type == "group":
                db_obj.homestart = str(db_obj.homestart)
                if not db_obj.homestart.startswith("/"):
                    db_obj.homestart = "/%s" % (db_obj.homestart)
            elif c_type == "user":
                if db_obj.aliases == "None":
                    db_obj.aliases = ""
            db_obj.save()
            if c_type == "group":
                # store by primary value and db_pk
                group_lut[src_dict["ggroup_idx"]] = db_obj
                group_dict[prim_value] = db_obj
                group_dict[db_obj.pk] = db_obj
    # print etree.tostring(_xml["user"], pretty_print=True)

if __name__ == "__main__":
    main()

