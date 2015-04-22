# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel
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
""" cluster-server, user_scan capability """

from django.db.models import Q
from initat.cluster.backbone.models import home_export_list, user, user_scan_result, user_scan_run
from initat.cluster_server.capabilities.base import bg_stuff
from initat.cluster_server.config import global_config
from initat.tools import logging_tools
import os
from initat.tools import process_tools
import scandir
import stat
import time


def sub_sum(_dict):
    _size = _dict.size
    for _key, _value in _dict.iteritems():
        _size += sub_sum(_value)
    return _size


class sub_dir(dict):
    def __init__(self, full_name):
        self.size = 0
        # number of dirs
        self.dirs = 0
        # number of files
        self.files = 0
        self.full_name = full_name
        dict.__init__(self)

    def add_sub_dir(self, key):
        if key not in self:
            self[key] = sub_dir(os.path.join(self.full_name, key))
        return self[key]

    def total(self, attr):
        _total = getattr(self, attr)
        for _key, _value in self.iteritems():
            _total += _value.total(attr)
        return _total

    def create_db_entries(self, new_run, name=None, parent=None):
        if name is None:
            new_entry = None
        else:
            new_entry = user_scan_result.objects.create(
                name=name,
                user_scan_run=new_run,
                parent_dir=parent,
                size=self.size,
                size_total=self.total("size"),
                num_files=self.files,
                num_dirs=self.dirs,
                num_files_total=self.total("files"),
                num_dirs_total=self.total("dirs"),
                full_name=self.full_name,
            )
        for _total_size, key in sorted([(-self[key].total("size"), key) for key in self.iterkeys()]):
            self[key].create_db_entries(new_run, key, new_entry)


class user_scan_stuff(bg_stuff):
    class Meta:
        name = "user_scan"

    def init_bg_stuff(self):
        self.__last_user_scan = None
        self.__scan_running = False

    def _call(self, cur_time, _builder):
        if not self.__scan_running:
            if not self.__last_user_scan:
                _run_scan = True
            else:
                _diff = abs(cur_time - self.__last_user_scan)
                _run_scan = _diff > global_config["USER_SCAN_TIMER"]
            if _run_scan:
                self.__last_user_scan = cur_time
                self.__scan_running = True
                self._scan_users()
                self.__scan_running = False

    def _scan_users(self):
        _hel = home_export_list()
        _scanned_ok, _scanned_error = (0, 0)
        for _key, _value in _hel.exp_dict.iteritems():
            if _value["entry"].device.pk == self.sql_info.effective_device.pk:
                for _scan_user in user.objects.filter(Q(export=_value["entry"]) & Q(scan_user_home=True)):  # @UndefinedVariable
                    _h_dir = os.path.join(_value["createdir"], _scan_user.home or _scan_user.login)
                    if os.path.isdir(_h_dir):
                        s_time = time.time()
                        self.log(u"scanning user '{}' in {}".format(_scan_user, _h_dir))
                        self.step(blocking=False, handle_timer=True)
                        self._scan_dir(_scan_user, _h_dir)
                        e_time = time.time()
                        self.log("... took {}".format(logging_tools.get_diff_time_str(e_time - s_time)))
                        _scanned_ok += 1
                    else:
                        self.log(u"homedir {} doest not exist for user '{}'".format(_h_dir, unicode(_scan_user)), logging_tools.LOG_LEVEL_ERROR)
                        _scanned_error += 1
        self.log("scan info: {:d} ok, {:d} with errors".format(_scanned_ok, _scanned_error))

    def _scan_dir(self, _scan_user, _home_dir):
        _s_time = time.time()
        _prev_runs = list(user_scan_run.objects.filter(Q(user=_scan_user)))
        new_run = user_scan_run.objects.create(user=_scan_user, running=True, scan_depth=_scan_user.scan_depth)
        new_run.save()
        _size_dict = sub_dir(_home_dir)
        _start_dir = _home_dir
        _top_depth = _start_dir.count("/")
        try:
            nfs_mounts, nfs_ignore = (set(), [])
            _last_dir = u""
            for _main, _dirs, _files in scandir.walk(_start_dir):
                if os.path.ismount(_main):
                    nfs_mounts.add(_main)
                    continue
                elif any([_main.startswith(_nfs) for _nfs in nfs_mounts]):
                    nfs_ignore.append(_nfs)
                    continue
                _last_dir = _main
                _cur_depth = _main.count("/")
                _parts = _main.split("/")
                _max_depth = min(_top_depth + _scan_user.scan_depth, _cur_depth)
                _key = "/".join(_parts[:_max_depth + 1])
                # print _parts, _key
                cur_dict = _size_dict
                for _skey in _parts[_top_depth:_max_depth + 1]:
                    cur_dict = cur_dict.add_sub_dir(_skey)
                cur_dict.dirs += 1
                for _file in _files:
                    try:
                        cur_dict.files += 1
                        cur_dict.size += os.stat(os.path.join(_main, _file))[stat.ST_SIZE]
                    except:
                        pass
            if nfs_mounts:
                self.log(
                    "ignored {} on {}".format(
                        logging_tools.get_plural("NFS directory", len(nfs_ignore)),
                        logging_tools.get_plural("NFS mount", len(nfs_mounts)),
                    )
                )
        except UnicodeDecodeError:
            self.log(
                u"UnicodeDecode: {}, _last_dir is '{}'".format(
                    process_tools.get_except_info(),
                    _last_dir,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if global_config["DEBUG"]:
                raise
        # store current
        _size_dict.create_db_entries(new_run)
        _e_time = time.time()
        new_run.current = True
        new_run.running = False
        new_run.run_time = abs((_e_time - _s_time) * 1000)
        new_run.save()
        [_prev_run.delete() for _prev_run in _prev_runs]
