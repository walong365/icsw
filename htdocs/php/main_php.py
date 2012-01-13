#!/usr/bin/python -Otv
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

import mod_python
from mod_python import *
import os.path
import sys
import process_tools
import logging_tools
import cgi
from basic_defs import *

def parse_args(req):
    fs = util.FieldStorage(req, keep_blank_values=1)
    args, files = ({}, {})
    for v in fs.list:
        if v.filename:
            # handle files
            files[v.name] = (v.filename, v.file.read())
        else:
            k, val = (v.name, v.value)
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

def handle_direct_module_call(req, module_name):
    try:
        if globals().has_key(module_name) and sys.modules.has_key(module_name):
            mod = sys.modules[module_name]
        else:
            mod = __import__(module_name, globals(), locals(), [])
    except:
        # oops
        pass
    else:
        mod.process_page(req)
    return apache.OK
    
class dummy_ios:
    def __init__(self, req):
        self.req = req
    def write(self, what):
        self.req.write(cgi.escape(what).replace("\n", "<br>\n").replace(" ", "&nbsp;"))
    def close(self):
        pass
    def __del__(self):
        pass

def handler(req):
    # direct modules, no session-id checking
    direct_modules = ["netbotzdrop"]
    # modify handles
    sys.stdout = dummy_ios(req)
    sys.stderr = dummy_ios(req)
    #php_pathes = [p for p in sys.path if p.count("/php")]
    #python_pathes = [p.replace("php", "python") for p in php_pathes]
    #sys.path.extend([py_p for py_p in python_pathes if py_p not in sys.path])
    req.allow_methods(["GET", "POST", "HEAD"])
    # check for allowed methods
    if req.method not in ["GET", "POST", "HEAD"]:
        raise apache.SERVER_RETURN, apache.HTTP_METHOD_NOT_ALLOWED
    # parse args and set conf
    args, files = parse_args(req)
    req.sys_args = args
    req.my_files = files
    mod_path, module_name = os.path.split(req.filename)
    module_name = module_name.split(".")[0]
    req.module_name = module_name
    req.title = req.module_name
    req.content_type = "text/html"
    if module_name in direct_modules:
        ret = handle_direct_module_call(req, module_name)
    else:
        ret = apache.OK
    return ret
