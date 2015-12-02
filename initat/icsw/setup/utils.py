# -*- coding: utf-8 -*-

import random
import os
import shutil
import string
import tempfile

from initat.tools import logging_tools


def get_icsw_root():
    return os.environ.get(
        "ICSW_ROOT", "/opt/python-init/lib/python/site-packages"
    )


def generate_password(size=10):
    return "".join([random.choice(string.ascii_letters) for _ in range(size)])


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
        print(
            "moving away migrations above {:04d}_* ({}) to {}".format(
                self.__min_idx,
                logging_tools.get_plural("file", len(self.__move_files)),
                self.__tmp_dir,
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
