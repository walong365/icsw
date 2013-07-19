#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# this file is part of python-modules-base
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

import sys
import os
import os.path
import cgi
import getopt
import httplib
from mod_python import *
from mod_python import apache
import upload_file

def parse_args(req):
    fs = util.FieldStorage(req, keep_blank_values=1)
    args, files = ({}, {})
    for v in fs.list:
        if v.name.startswith("'") and v.name.endswith("'"):
            v.name = v.name[1:-1]
        if v.filename:
            if v.filename.startswith("'") and v.filename.endswith("'"):
                v.filename = v.filename[1:-1]
            # handle files
            files[v.name] = (v.filename, v.file.read())
        else:
            k, val = (v.name, v.value)
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            if k.endswith("[]"):
                k = k[:-2]
                # is a field
                if args.has_key(k):
                    args[k].append(val)
                else:
                    args[k] = [val]
            else:
                # is a scalar
                args[k] = val
    return args, files

class dummy_ios:
    def __init__(self, req):
        self.req = req
    def write(self, what):
        self.req.write(what)
    def close(self):
        pass
    def __del__(self):
        pass

def handler(req):
    # modify handles
    sys.stdout = dummy_ios(req)
    sys.stderr = dummy_ios(req)
    req.allow_methods(["POST"])
    # check for allowed methods
    if req.method not in ["POST"]:
        raise apache.SERVER_RETURN, apache.HTTP_METHOD_NOT_ALLOWED
    args, files = parse_args(req)
    if args.has_key("get_file_info"):
        d_files = args["get_file_info"].split("#")
        local_files, remote_files = ([], [])
        for d_file in d_files:
            if d_file.count(",") and d_file.startswith("http://"):
                remote_files.append(d_file)
            else:
                local_files.append(d_file)
        for remote_file in remote_files:
            dst_host, dst_name = remote_file.split(",", 1)
            print "trying to get fileinfo for file '%s' from host '%s'" % (dst_name,
                                                                           dst_host)
            stat, reason, ret_page = upload_file.post_multipart(dst_host, [], {"get_file_info" : dst_name})
            if reason == "OK":
                print ret_page
            else:
                print "Error (%d): %s" % (stat, reason)
                print ret_page
        for local_file in local_files:
            if os.path.exists(local_file):
                print "%s::exists" % (local_file)
                l_stat = os.stat(local_file)
                for idx, val in zip(range(len(l_stat)), l_stat):
                    print "%s::stat_%d::%d" % (local_file, idx, val)
                if local_file.endswith(".rpm"):
                    fn_parts = os.path.basename(local_file).split("-")
                    print "%s::arch::%s" % (local_file, fn_parts[-1].split(".")[1])
                    print "%s::version::%s" % (local_file, fn_parts[-2])
                    print "%s::release::%s" % (local_file, fn_parts[-1].split(".")[0])
            else:
                print "%s::not found" % (local_file)
    if files:
        for f_name, (dst_name, content) in files.iteritems():
            if dst_name.startswith("'"):
                dst_name = dst_name[1:-1]
            if dst_name.count(",") and dst_name.startswith("http://"):
                dst_host, dst_name = dst_name.split(",", 1)
                print "trying to relay file '%s' to host '%s' (dst_name: '%s'), %d bytes" % (f_name,
                                                                                             dst_host,
                                                                                             dst_name,
                                                                                             len(content))
                stat, reason, ret_page = upload_file.post_multipart(dst_host, [(f_name, dst_name, content)], {})
                if reason == "OK":
                    print ret_page
                else:
                    print "Error (%d): %s" % (stat, reason)
                    print ret_page
            else:
                try:
                    file(dst_name, "w").write(content)
                except:
                    print "Error for file '%s': %s (%s)" % (dst_name,
                                                            str(sys.exc_info()[0]),
                                                            str(sys.exc_info()[1]))
                else:
                    print "Ok saved file '%s' (%d bytes)" % (dst_name,
                                                             len(content))
    return apache.OK
    
