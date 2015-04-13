# -*- coding: utf-8 -*-
#
# Copyright (C) 2007,2011,2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" inotify tools """

import logging
import logging_tools
try:
    import pyinotify
except:
    pyinotify = None
else:
    pyinotify.log.setLevel(logging.CRITICAL)

if pyinotify:
    IN_ACCESS = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_ACCESS"]
    IN_MODIFY = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_MODIFY"]
    IN_ATTRIB = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_ATTRIB"]
    IN_CLOSE_WRITE = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_CLOSE_WRITE"]
    IN_CLOSE_NOWRITE = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_CLOSE_NOWRITE"]
    IN_OPEN = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_OPEN"]
    IN_MOVED_FROM = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_MOVED_FROM"]
    IN_MOVED_TO = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_MOVED_TO"]
    IN_DELETE = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_DELETE"]
    IN_CREATE = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_CREATE"]
    IN_ISDIR = pyinotify.EventsCodes.FLAG_COLLECTIONS["SPECIAL_FLAGS"]["IN_ISDIR"]
    IN_ONLYDIR = pyinotify.EventsCodes.FLAG_COLLECTIONS["SPECIAL_FLAGS"]["IN_ONLYDIR"]
    IN_ONESHOT = pyinotify.EventsCodes.FLAG_COLLECTIONS["SPECIAL_FLAGS"]["IN_ONESHOT"]
    IN_DONT_FOLLOW = pyinotify.EventsCodes.FLAG_COLLECTIONS["SPECIAL_FLAGS"]["IN_DONT_FOLLOW"]
    IN_MASK_ADD = pyinotify.EventsCodes.FLAG_COLLECTIONS["SPECIAL_FLAGS"]["IN_MASK_ADD"]
    IN_DELETE_SELF = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_DELETE_SELF"]
    IN_MOVE_SELF = pyinotify.EventsCodes.FLAG_COLLECTIONS["OP_FLAGS"]["IN_MOVE_SELF"]
    IN_UNMOUNT = pyinotify.EventsCodes.FLAG_COLLECTIONS["EVENT_FLAGS"]["IN_UNMOUNT"]
    IN_Q_OVERFLOW = pyinotify.EventsCodes.FLAG_COLLECTIONS["EVENT_FLAGS"]["IN_Q_OVERFLOW"]
    IN_IGNORED = pyinotify.EventsCodes.FLAG_COLLECTIONS["EVENT_FLAGS"]["IN_IGNORED"]
    ALL_EVENTS = pyinotify.ALL_EVENTS

    in_dict = {
        IN_ACCESS: "ACCESS",
        IN_MODIFY: "MODIFY",
        IN_ATTRIB: "ATTRIB",
        IN_CLOSE_WRITE: "CLOSE_WRITE",
        IN_CLOSE_NOWRITE: "CLOSE_NOWRITE",
        IN_OPEN: "OPEN",
        IN_MOVED_FROM: "MOVED_FROM",
        IN_MOVED_TO: "MOVED_TO",
        IN_DELETE: "DELETE",
        IN_CREATE: "CREATE",
        IN_ISDIR: "ISDIR",
        IN_DELETE_SELF: "DELETE_SELF",
        IN_UNMOUNT: "UNMOUNT",
        IN_Q_OVERFLOW: "Q_OVERFLOW",
        IN_DONT_FOLLOW: "DONT_FOLLOW",
        IN_IGNORED: "IGNORED",
        IN_ONESHOT: "ONESHOT",
        IN_ONLYDIR: "ONLYDIR",
        IN_MASK_ADD: "MASK_ADD",
        ALL_EVENTS: "ALL_EVENTS",
    }
else:
    ALL_EVENTS = 0


def inotify_ok():
    return pyinotify and True or False


def mask_to_str(in_mask):
    return ", ".join([value for key, value in in_dict.iteritems() if in_mask & key == key]) or "NONE"

if pyinotify:
    class inotify_watcher(pyinotify.Notifier):
        def __init__(self, **kwargs):
            self.__wm = pyinotify.WatchManager()
            self.__log_com = kwargs.get("log_com", None)
            pyinotify.Notifier.__init__(self, self.__wm)
            self.__watch_dict = {}
            self.log("init inotify_watcher")

        def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
            if self.__log_com:
                self.__log_com(u"[inw] {}".format(what), log_level)

        def add_watcher(self, ext_id, name, mask=ALL_EVENTS, process_events=None):
            if not name in self.__watch_dict:
                old_mask = 0
                self.__watch_dict[name] = {}
            else:
                old_mask = reduce(lambda v0, v1: v0 | v1, [value["mask"] for value in self.__watch_dict[name].values()])
            self.__watch_dict[name][ext_id] = {
                "mask"           : mask,
                "process_events" : process_events}
            if old_mask:
                try:
                    wd = self.__wm.get_wd(name)
                except KeyError:
                    pass
                else:
                    if wd:
                        self.__wm.rm_watch(wd)
            self.__wm.add_watch(name, mask | old_mask, self._proc_events, False)

        def _proc_events(self, event):
            if event.path in self.__watch_dict:
                # dictionary can be changed during loop
                ext_ids = [key for key in self.__watch_dict[event.path]]
                for ext_id in ext_ids:
                    if ext_id in self.__watch_dict[event.path]:
                        self.__watch_dict[event.path][ext_id]["process_events"](event)
            else:
                self.log(u"unknown event path '{}'".format(event.path), logging_tools.LOG_LEVEL_ERROR)

        def remove_watcher(self, ext_id, name):
            # remove watcher
            try:
                wd = self.__wm.get_wd(name)
            except KeyError:
                self.log(u"unknown watcher name '{}'".format(name), logging_tools.LOG_LEVEL_ERROR)
            else:
                if wd:
                    self.__wm.rm_watch(wd)
            del self.__watch_dict[name][ext_id]
            if self.__watch_dict[name]:
                self.__wm.add_watch(name, reduce(lambda v0, v1: v0 | v1, [value["mask"] for value in self.__watch_dict[name].values()]), self._proc_events, False)
            else:
                del self.__watch_dict[name]

        def check(self, timeout=0):
            self.process_events()
            self._timeout = timeout
            if self.check_events():
                self.read_events()
else:
    class inotify_watcher(object):
        def __init__(self, **kwargs):
            pass


def show_ev(*args):
    print args


def test():
    if inotify_ok():
        my_w = inotify_watcher()  # thread_safe=True)
        print "add watch to /tmp"
        my_w.add_watcher("test", "/tmp", process_events=show_ev)
        # my_w.remove_watcher("test", "/tmp")
        # my_w.add_watcher("test", "/tmp/x")
        while True:
            print "-" * 20
            my_w.check(1000)
        print my_w
    else:
        print "No inotify-support on this machine"


if __name__ == "__main__":
    test()
