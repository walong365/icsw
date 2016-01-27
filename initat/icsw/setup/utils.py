# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2016 Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
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

""" utility functions for database setup and migration """

import os
import random
import shutil
import string
import tempfile

from initat.constants import SITE_PACKAGES_BASE
from initat.tools import logging_tools, process_tools


def get_icsw_root():
    return os.environ.get(
        "ICSW_ROOT", SITE_PACKAGES_BASE
    )


def generate_password(size=10):
    return "".join([random.choice(string.ascii_letters) for _ in range(size)])


class DummyFile(object):
    def __init__(self, file_name, content):
        self.__file_name = file_name
        self.__content = content
        self._existed = os.path.exists(self.__file_name)
        print("File {} is {}".format(self.__file_name, "present" if self._existed else "not present"))
        if not self._existed:
            file(self.__file_name, "w").write(self.__content)

    def restore(self):
        if not self._existed:
            print("removing dummy file {}".format(self.__file_name))
            os.unlink(self.__file_name)


class DirSave(object):
    def __init__(self, dir_name, min_idx):
        self.__dir_name = dir_name
        self.__tmp_dir = tempfile.mkdtemp()
        self.__min_idx = min_idx
        print("Init DirSave for {} (min_idx={:d})".format(self.__dir_name, self.__min_idx))
        self.save()

    def _match(self, f_name):
        return True if f_name[0:4].isdigit() and int(f_name[0:4]) > self.__min_idx else False

    def save(self):
        self.__move_files = [
            _entry for _entry in os.listdir(self.__dir_name) if _entry.endswith(".py") and self._match(_entry)
        ]
        _del_files = [
            _entry for _entry in os.listdir(self.__dir_name) if _entry.endswith(".pyc") or _entry.endswith(".pyo")
        ]
        print(
            "moving away migrations above {:04d}_* ({}) to {}, removing {}".format(
                self.__min_idx,
                logging_tools.get_plural("file", len(self.__move_files)),
                self.__tmp_dir,
                logging_tools.get_plural("file", len(_del_files)),
            )
        )
        if _del_files:
            for _del_file in _del_files:
                _path = os.path.join(self.__dir_name, _del_file)
                try:
                    os.unlink(_path)
                except:
                    print(
                        "error removing {}: {}".format(
                            _path,
                            process_tools.get_except_info(),
                        )
                    )
        for _move_file in self.__move_files:
            shutil.move(os.path.join(self.__dir_name, _move_file), os.path.join(self.__tmp_dir, _move_file))

    def restore(self, idx=None):
        if idx is not None:
            __move_files = [_entry for _entry in self.__move_files if int(_entry[0:4]) == idx]
        else:
            __move_files = self.__move_files
        self.__move_files = [_entry for _entry in self.__move_files if _entry not in __move_files]
        print(
            "moving back {} above {:04d}_* ({})".format(
                logging_tools.get_plural("migration", len(__move_files)),
                self.__min_idx,
                logging_tools.get_plural("file", len(__move_files)))
        )
        for _move_file in __move_files:
            shutil.move(os.path.join(self.__tmp_dir, _move_file), os.path.join(self.__dir_name, _move_file))

    def cleanup(self):
        shutil.rmtree(self.__tmp_dir)


def remove_pyco(start_dir):
    # remove pyc / pyo files
    _removed = []
    print("remove pyc/pyo files in {} ..:".format(start_dir))
    for _dir, _dir_list, _file_list in os.walk(start_dir):
        for _file in _file_list:
            if _file.endswith(".pyc") or _file.endswith(".pyo"):
                _path = os.path.join(_dir, _file)
                _removed.append(_path)
                os.unlink(_path)
    if _removed:
        print("    removed {}".format(logging_tools.get_plural("file", len(_removed))))
