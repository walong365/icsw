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
import getopt
import httplib
import mimetypes
import urlparse
import stat

def post_multipart(target, files, cmd_dict):
    urlparts = urlparse.urlsplit(target)
    content_type, body = encode_multipart_formdata(files, cmd_dict)
    h = httplib.HTTPConnection(urlparts[1])
    headers = {"User-Agent"   : "init.at fileuploader",
               "Content-Type" : content_type
               }
    h.request("POST", urlparts[2], body, headers)
    res = h.getresponse()
    return res.status, res.reason, "\n".join([x.strip() for x in res.read().split("\n") if x.strip()])

def encode_multipart_formdata(files, cmd_dict):
    bndry = "---------- boundary"
    cr_lf = "\r\n"
    s_list = []
    for key, value in cmd_dict.iteritems():
        s_list.extend(["--%s" % (bndry),
                       "Content-Disposition: form-data; name='%s'" % (key),
                       "",
                       value])
    for key, filename, content in files:
        s_list.extend(["--%s" % (bndry),
                       "Content-Disposition: form-data; name='%s'; filename='%s'" % (key, filename),
                       "Content-Type: %s" % (get_content_type(filename)),
                       "",
                       content])
    s_list.extend(["--%s--" % (bndry),
                   ""])
    return "multipart/form-data; boundary=%s" % (bndry), cr_lf.join(s_list)

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:h", ["help"])
    except:
        print "Error parsing commandline %s: %s (%s)" % (" ".join(sys.argv[:]),
                                                         str(sys.exc_info()[0]),
                                                         str(sys.exc_info()[1]))
        sys.exit(1)
    dest = "http://www.initat.org/cluster/upload.py"
    file_list = []
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS] (FILES)" % (pname)
            print " where options is one or more of"
            print "  -h,--help           this help"
            print "  -d dest             set destination, default is %s" % (dest)
            print " (FILES)              list of src_name,dst_name filenametuples"
            sys.exit(0)
        elif opt == "-d":
            dest = arg
    if not args:
        print "Need files"
        sys.exit(1)
    file_dict, file_lut_dict = ({}, {})
    for f_t in args:
        if f_t.count(","):
            s_file, d_file = f_t.split(",", 1)
        else:
            s_file, d_file = (f_t, f_t)
        if os.path.exists(s_file):
            file_dict[s_file]     = d_file
            file_lut_dict[d_file.startswith("http://") and d_file.split(",", 1)[1] or d_file] = s_file
        else:
            print "Error, file %s does not exist" % (s_file)
        #file_list.append((s_file, d_file, file(s_file, "r").read()))
    stat, reason, ret_page = post_multipart(dest, [], {"get_file_info" : "#".join(file_dict.values())})
    if reason == "OK":
        res_dict = {}
        for line in ret_page.split("\n"):
            line_p = line.strip().split("::")
            if len(line_p) == 2 and line_p[1] == "exists":
                res_dict[line_p[0]] = {}
            elif res_dict.has_key(line_p[0]):
                if line_p[1].startswith("stat_"):
                    res_dict[line_p[0]][{0 : "mode",
                                         1 : "inode",
                                         2 : "dev",
                                         3 : "nlink",
                                         4 : "uid",
                                         5 : "gid",
                                         6 : "size",
                                         7 : "atime",
                                         8 : "mtime",
                                         9 : "ctime"}.get(int(line_p[1][5:]), "???")] = int(line_p[2])
                else:
                    res_dict[line_p[0]][line_p[1]] = line_p[2]
        skip_files = []
        for k, v in res_dict.iteritems():
            loc_stat = os.stat(file_lut_dict[k])
            fn_parts = os.path.basename(file_lut_dict[k]).split("-")
            if fn_parts[-1].endswith(".rpm") and v.has_key("version") and v.has_key("release"):
                local_v = [int(fn_parts[-2].split(".")[0]),
                           int(fn_parts[-2].split(".")[1]),
                           int(fn_parts[-1].split(".")[0])]
                remote_v = [int(v["version"].split(".")[0]),
                            int(v["version"].split(".")[1]),
                            int(v["release"])]
                if local_v >= remote_v:
                    print "  File %s is not older (RPM-wise) than remote file (%s >= %s)" % (k,
                                                                                             ".".join(["%d" % (x) for x in local_v]),
                                                                                             ".".join(["%d" % (x) for x in remote_v]))
                skip_files.append(file_lut_dict[k])
            elif loc_stat[6] == v["size"] and v["mtime"] > loc_stat[8]:
                print "  File %s has the same size (%d bytes) and is newer on destination host" % (k,
                                                                                                   v["size"])
                skip_files.append(file_lut_dict[k])
    file_list = [(k, v, file(k, "r").read()) for k, v in file_dict.iteritems() if k not in skip_files]
    if file_list:
        print "Transfering %d files" % (len(file_list))
        for s_file, d_file, f_stuff in file_list:
            print "  File %s to %s (%d bytes)" % (s_file, d_file, len(f_stuff))
        stat, reason, ret_page = post_multipart(dest, file_list, {})
        if reason == "OK":
            print ret_page
            sys.exit(0)
        else:
            print "Error (%d): %s" % (stat, reason)
            print ret_page
            sys.exit(1)

if __name__ == "__main__":
    main()
    
