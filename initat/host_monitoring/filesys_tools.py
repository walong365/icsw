#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
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
""" filesystem tools, also used by cluster-server """

import codecs
import base64
import os
import shutil
import stat

from lxml.builder import E  # @UnresolvedImport
from initat.tools import logging_tools, process_tools, server_command


# max file size to read, can be overridden
MAX_FILE_SIZE = 5 * 1024 * 1024


def _set_attributes(xml_el, log_com):
    try:
        if "user" in xml_el.attrib or "group" in xml_el.attrib:
            el_user = xml_el.get("user", "root")
            el_group = xml_el.get("group", "root")
            process_tools.change_user_group_path(xml_el.text, el_user, el_group, log_com=log_com)
        if "mode" in xml_el.attrib:
            os.chmod(xml_el.text, int(xml_el.get("mode"), 8))
    except:
        xml_el.attrib["error"] = "1"
        xml_el.attrib["error_str"] = process_tools.get_except_info()


def create_dir(srv_com, log_com):
    created, failed = (0, 0)
    for dir_entry in srv_com.xpath(".//ns:dir", smart_strings=False):
        if not os.path.isdir(dir_entry.text):
            try:
                os.makedirs(dir_entry.text)
            except:
                dir_entry.attrib["error"] = "1"
                dir_entry.attrib["error_str"] = process_tools.get_except_info()
                failed += 1
            else:
                dir_entry.attrib["error"] = "0"
                created += 1
        else:
            dir_entry.attrib["error"] = "0"
        if not int(dir_entry.get("error", "0")):
            _set_attributes(dir_entry, log_com)
    srv_com.set_result(
        "created {}{}".format(
            logging_tools.get_plural("directory", created),
            " ({:d} failed)".format(failed) if failed else "",
        ),
        server_command.SRV_REPLY_STATE_ERROR if failed else server_command.SRV_REPLY_STATE_OK
    )


def set_file_content(srv_com, log_com):
    for file_entry in srv_com.xpath(".//ns:file", smart_strings=False):
        try:
            if "encoding" in file_entry.attrib:
                codecs.open(file_entry.attrib["name"], "w", file_entry.attrib["encoding"]).write(file_entry.text)
            else:
                open(file_entry.attrib["name"], "r").write(file_entry.text)
        except:
            file_entry.attrib["error"] = "1"
            file_entry.attrib["error_str"] = process_tools.get_except_info()
        else:
            file_entry.attrib["error"] = "0"
        if not int(file_entry.get("error", "0")):
            _set_attributes(file_entry, log_com)
    srv_com.set_result(
        "stored file contents",
    )


def get_dir_tree(srv_com, log_com):
    for top_el in srv_com.xpath(".//ns:start_dir", smart_strings=False):
        top_el.append(E.directory(full_path=top_el.text, start_dir="1"))
        for cur_dir, dir_list, file_list in os.walk(top_el.text):
            add_el = top_el.find(".//directory[@full_path='{}']".format(cur_dir))
            for new_dir in sorted(dir_list):
                add_el.append(
                    E.directory(
                        full_path=os.path.join(add_el.attrib["full_path"], new_dir),
                        path=new_dir
                    )
                )
            for new_file in sorted(file_list):
                add_el.append(
                    E.file(
                        name=new_file,
                        size="{:d}".format(os.stat(os.path.join(cur_dir, new_file))[stat.ST_SIZE]),
                    )
                )
        for cur_idx, cur_el in enumerate(top_el.findall(".//*")):
            cur_el.attrib["idx"] = "{:d}".format(cur_idx)
    srv_com.set_result(
        "read directory tree"
    )


def remove_dir(srv_com, log_com):
    created, failed = (0, 0)
    for dir_entry in srv_com.xpath(".//ns:dir", smart_strings=False):
        if os.path.isdir(dir_entry.text):
            try:
                if int(dir_entry.get("recursive", "0")):
                    shutil.rmtree(dir_entry.text)
                else:
                    os.rmdir(dir_entry.text)
            except:
                dir_entry.attrib["error"] = "1"
                dir_entry.attrib["error_str"] = process_tools.get_except_info()
                failed += 1
            else:
                dir_entry.attrib["error"] = "0"
                created += 1
        else:
            dir_entry.attrib["error"] = "0"
    srv_com.set_result(
        "removed {}{}".format(
            logging_tools.get_plural("directory", created),
            " ({:d} failed)".format(failed) if failed else "",
        ),
        server_command.SRV_REPLY_STATE_ERROR if failed else server_command.SRV_REPLY_STATE_OK
    )


def get_file_content(srv_com, log_com, **kwargs):
    max_size = kwargs.get("max_file_size", MAX_FILE_SIZE)
    for file_entry in srv_com.xpath(".//ns:file", smart_strings=False):
        if os.path.isfile(file_entry.attrib["name"]):
            try:
                cur_size = os.stat(file_entry.attrib["name"])[stat.ST_SIZE]
            except:
                file_entry.attrib["error"] = "1"
                file_entry.attrib["error_str"] = "error stating: {}".format(process_tools.get_except_info())
            else:
                if cur_size <= max_size:
                    try:
                        if "encoding" in file_entry.attrib:
                            try:
                                content = codecs.open(file_entry.attrib["name"], "r", file_entry.attrib["encoding"]).read()
                            except UnicodeDecodeError:
                                # try without encoding
                                content = open(file_entry.attrib["name"], "r").read()
                        else:
                            content = open(file_entry.attrib["name"], "r").read()
                    except:
                        file_entry.attrib["error"] = "1"
                        file_entry.attrib["error_str"] = "error reading: {}".format(process_tools.get_except_info())
                    else:
                        try:
                            if int(file_entry.get("base64", "0")):
                                file_entry.text = base64.b64encode(content)
                            else:
                                try:
                                    file_entry.text = content
                                except:
                                    file_entry.text = content.decode("utf-8", errors="ignore")
                        except:
                            file_entry.attrib["error"] = "1"
                            file_entry.attrib["error_str"] = "error setting content: {}".format(process_tools.get_except_info())
                        else:
                            file_entry.attrib["error"] = "0"
                            file_entry.attrib["size"] = "{:d}".format(len(content))
                            file_entry.attrib["lines"] = "{:d}".format(content.count("\n") + 1)
                else:
                    file_entry.attrib["error"] = "1"
                    file_entry.attrib["error_str"] = "file is too big: {} > {}".format(
                        logging_tools.get_size_str(cur_size, long_format=True),
                        logging_tools.get_size_str(max_size, long_format=True),
                    )
        else:
            file_entry.attrib["error"] = "1"
            file_entry.attrib["error_str"] = "file does not exist"
    srv_com.set_result(
        "read file contents",
    )
