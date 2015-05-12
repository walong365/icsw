# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server, base objects """

import array
import os
import stat


class new_config_object(object):
    # path and type [(f)ile, (l)ink, (d)ir, (c)opy]
    def __init__(self, destination, c_type, **kwargs):
        self.dest = destination
        self.c_type = c_type
        self.content = []
        self.binary = False
        self.source_configs = set()
        self.source = kwargs.get("source", "")
        self.uid, self.gid = (0, 0)
        if self.c_type not in ["i", "?"]:
            cur_config = kwargs["config"]
            self.mode = cur_config.dir_mode if self.c_type == "d" else (cur_config.link_mode if self.c_type == "l" else cur_config.file_mode)
            if "config" not in kwargs:
                cur_config._add_object(self)
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def get_effective_type(self):
        return self.c_type

    def __eq__(self, other):
        if self.dest == other.dest and self.c_type == other.c_type:
            return True
        else:
            return False

    def set_config(self, conf):
        self.add_config(conf.get_name())
    # compatibility calls (mode, uid and gid)

    def set_mode(self, mode):
        self.mode = mode

    def set_uid(self, uid):
        self.uid = uid

    def set_gid(self, gid):
        self.gid = gid

    def _set_mode(self, mode):
        if isinstance(mode, basestring):
            self.__mode = int(mode, 8)
        else:
            self.__mode = mode

    def _get_mode(self):
        return self.__mode
    mode = property(_get_mode, _set_mode)

    def append(self, what):
        self +=what

    def __iadd__(self, line):
        if isinstance(line, basestring):
            self.content.append("%s\n" % (line))
        elif type(line) == list:
            self.content.extend(["%s\n" % (s_line) for s_line in line])
        elif type(line) == dict:
            for key, value in line.iteritems():
                self.content.append("%s='%s'\n" % (key, value))
        elif type(line) == type(array.array("b")):
            self.content.append(line.tostring())
        return self

    def bin_append(self, in_bytes):
        # force binary
        self.binary = True
        if type(in_bytes) == type(array.array("b")):
            self.content.append(in_bytes.tostring())
        else:
            self.content.append(in_bytes)

    def write_object(self, t_file):
        return "__override__ write_object (%s)" % (t_file)


class file_object(new_config_object):
    def __init__(self, destination, **kwargs):
        """ example from ba/ca:
        a=config.add_file_object("/etc/services", from_image=True, dev_dict=dev_dict)
        new_content = []
        print len(a.content)
        for line in a.content:
            if line.lstrip().startswith("mult"):
                print line
        """
        new_config_object.__init__(self, destination, "f", **kwargs)
        self.set_mode("0644")
        if kwargs.get("from_image", False):
            s_dir = kwargs["dev_dict"]["image"].get("source", None)
            if s_dir:
                s_content = file("%s/%s" % (s_dir, destination), "r").read()
                self +=s_content.split("\n")

    def set_config(self, ref_config):
        self.mode = ref_config.file_mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid

    def write_object(self, t_file):
        file(t_file, "w").write("".join(self.content))
        return "%d %d %s %s" % (
            self.uid,
            self.gid,
            oct(self.mode),
            self.dest)


class link_object(new_config_object):
    def __init__(self, destination, source, **kwargs):
        new_config_object.__init__(self, destination, "l", source=source, **kwargs)

    def set_config(self, ref_config):
        self.mode = ref_config.file_mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid

    def write_object(self, t_file):
        return "%s %s" % (
            self.source,
            self.dest)


class dir_object(new_config_object):
    def __init__(self, destination, **kwargs):
        new_config_object.__init__(self, destination, "d", **kwargs)

    def set_config(self, ref_config):
        self.mode = ref_config.dir_mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid

    def write_object(self, t_file):
        return "%d %d %s %s" % (
            self.uid,
            self.gid,
            oct(self.mode),
            self.dest)


class delete_object(new_config_object):
    def __init__(self, destination, **kwargs):
        new_config_object.__init__(self, destination, "e", **kwargs)
        self.recursive = kwargs.get("recursive", False)

    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)

    def write_object(self, t_file):
        return "%d %s" % (
            self.recursive,
            self.dest)


class copy_object(new_config_object):
    def __init__(self, destination, source, **kwargs):
        new_config_object.__init__(self, destination, "c", source=source, **kwargs)
        self.content = [file(self.source, "r").read()]
        orig_stat = os.stat(self.source)
        self.uid, self.gid, self.mode = (
            orig_stat[stat.ST_UID],
            orig_stat[stat.ST_GID],
            stat.S_IMODE(orig_stat[stat.ST_MODE]))

    def get_effective_type(self):
        return "f"

    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_dir_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())

    def write_object(self, t_file):
        file(t_file, "w").write("".join(self.content))
        os.chmod(t_file, 0644)
        return "%d %d %s %s" % (
            self.uid,
            self.gid,
            oct(self.mode),
            self.dest)
