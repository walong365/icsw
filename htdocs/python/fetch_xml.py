#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2008 Andreas Lang-Nevyjel, init.at
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
""" fetch database structs as xml """

import xml_tools
import process_tools

def handle_partition_fetch(req, result_xml, part_idx):
    # partition_fs stuff
    req.dc.execute("SELECT * FROM partition_fs")
    part_fs_dict = dict([(db_rec["partition_fs_idx"], db_rec) for db_rec in req.dc.fetchall()])
    # sys partitions
    req.dc.execute("SELECT sp.* FROM sys_partition sp WHERE sp.partition_table=%s", (part_idx))
    sys_parts_xml = xml_tools.xml_entity("sys_partitions")
    for db_rec in req.dc.fetchall():
        act_sp_xml = xml_tools.xml_entity("sys_partition")
        act_sp_xml.add_entity(xml_tools.xml_entity("name", text=db_rec["name"]))
        act_sp_xml.add_entity(xml_tools.xml_entity("mountpoint", text=db_rec["mountpoint"]))
        act_sp_xml.add_entity(xml_tools.xml_entity("mount_options", text=db_rec["mount_options"]))
        sys_parts_xml.add_entity(act_sp_xml)
    # part table
    req.dc.execute("SELECT pt.name, pt.valid, pd.*, p.* FROM partition_table pt " + \
                   "LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx LEFT JOIN " + \
                   "partition p ON p.partition_disc=pd.partition_disc_idx " + \
                   "WHERE pt.partition_table_idx=%s ORDER BY pd.priority, p.pnum", (part_idx))
    disc_list_xml = xml_tools.xml_entity("disc_list")
    act_disc, act_disc_xml = (None, None)
    for db_rec in req.dc.fetchall():
        #result_xml.add_flag("rec", str(db_rec))
        if db_rec["disc"] != act_disc:
            if act_disc_xml:
                disc_list_xml.add_entity(act_disc_xml)
            act_disc = db_rec["disc"]
            act_disc_xml = xml_tools.xml_entity("disc")
            act_disc_xml.add_entity(xml_tools.xml_entity("disc_name", text=act_disc))
        act_part_xml = xml_tools.xml_entity("partition")
        act_part_xml.add_entity(xml_tools.xml_entity("num", text=str(db_rec["pnum"])))
        act_part_xml.add_entity(xml_tools.xml_entity("bootable", text="1" if db_rec["bootable"] else "0"))
        act_part_xml.add_entity(xml_tools.xml_entity("fs_freq", text=str(db_rec["fs_freq"])))
        act_part_xml.add_entity(xml_tools.xml_entity("fs_passno", text=str(db_rec["fs_passno"])))
        act_part_xml.add_entity(xml_tools.xml_entity("size", text=str(db_rec["size"])))
        act_part_xml.add_entity(xml_tools.xml_entity("hex_id", text=str(db_rec["partition_hex"])))
        part_fs = part_fs_dict.get(db_rec["partition_fs"], None)
        if part_fs:
            act_part_xml.add_entity(xml_tools.xml_entity("base_type", text=str(part_fs["identifier"])))
            act_part_xml.add_entity(xml_tools.xml_entity("fs_type", text=str(part_fs["name"])))
            act_part_xml.add_entity(xml_tools.xml_entity("mount_point", text=str(db_rec["mountpoint"])))
            act_part_xml.add_entity(xml_tools.xml_entity("mount_options", text=str(db_rec["mount_options"])))
#        else:
#            act_part_xml.add_entity(xml_tools.xml_entity("
        act_disc_xml.add_entity(act_part_xml)
    disc_list_xml.add_entity(act_disc_xml)
    result_xml.add_entity(disc_list_xml)
    result_xml.add_entity(sys_parts_xml)

def process_page(req):
    req.content_type = "text/plain"
    req.headers_out["Content-Disposition"] = "filename=\"xml_content\""
    req.send_http_header()
    to_send = req.sys_args.get("type", "type_not_set")
    result_xml = xml_tools.xml_entity(to_send, top_node=True)
    if to_send == "partition":
        part_idx = req.sys_args.get("partition_idx", "not_set")
        if part_idx.isdigit():
            part_idx = int(part_idx)
            try:
                handle_partition_fetch(req, result_xml, part_idx)
            except:
                result_xml.add_flag("error", True)
                result_xml.add_flag("cause", "error creating partition_xml: %s" % (process_tools.get_except_info()))
            else:
                result_xml.add_flag("error", False)
        else:
            result_xml.add_flag("error", True)
            result_xml.add_flag("cause", "cannot parse partition_idx '%s'" % (part_idx))
    else:
        result_xml.add_flag("error", True)
        result_xml.add_flag("cause", "unknown fetch_type '%s'" % (to_send))
    req.write(str(result_xml))
