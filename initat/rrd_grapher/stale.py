# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the icsw-server package
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
""" check for stale and old graphs, part of rrd-grapher """

import os
import stat
import time
import rrdtool  # @UnresolvedImport

from django.db import connection
from initat.cluster.backbone.models import device, MachineVector
from initat.rrd_grapher.config import global_config
from initat.tools import logging_tools, process_tools, server_mixins, \
    threading_tools


class stale_process(threading_tools.process_obj, server_mixins.OperationalErrorMixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self.register_timer(self._clear_old_graphs, 60, instant=True)
        self.register_timer(self._check_for_stale_rrds, 3600, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(what, log_level)

    def _check_for_stale_rrds(self):
        cur_time = time.time()
        # set stale after two hours
        MAX_DT = 3600 * 2
        num_changed = 0
        _total = MachineVector.objects.all().count()
        self.log("checking {}".format(logging_tools.get_plural("MachineVector", _total)))
        mv_idx = 0
        for mv in MachineVector.objects.all().prefetch_related("mvstructentry_set"):
            mv_idx += 1
            enabled, disabled = (0, 0)
            num_active = 0
            for mvs in mv.mvstructentry_set.all():
                f_name = mvs.file_name
                is_active = True if mvs.is_active else False
                if os.path.isfile(f_name):
                    _stat = os.stat(f_name)
                    if _stat[stat.ST_SIZE] < 1024:
                        self.log("file {} is too small, deleting and disabling...".format(f_name), logging_tools.LOG_LEVEL_ERROR)
                        try:
                            os.unlink(f_name)
                        except:
                            self.log("error deleting {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        is_active, stale = (False, True)
                    else:
                        c_time = os.stat(f_name)[stat.ST_MTIME]
                        stale = abs(cur_time - c_time) > MAX_DT
                        if stale:
                            # check via rrdtool
                            try:
                                # important: cast to str
                                rrd_info = rrdtool.info(str(f_name))
                            except:
                                self.log(
                                    "cannot get info for {} via rrdtool: {}".format(
                                        f_name,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                                raise
                            else:
                                c_time = int(rrd_info["last_update"])
                                stale = abs(cur_time - c_time) > MAX_DT
                    if is_active:
                        num_active += 1
                    if is_active and stale:
                        mvs.is_active = False
                        mvs.save(update_fields=["is_active"])
                        disabled += 1
                    elif not is_active and not stale:
                        mvs.is_active = True
                        mvs.save(update_fields=["is_active"])
                        enabled += 1
                else:
                    if is_active:
                        self.log(
                            "file '{}' missing, disabling".format(
                                mvs.file_name,
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        )
                        mvs.is_active = False
                        mvs.save(update_fields=["is_active"])
                        disabled += 1
            if enabled or disabled:
                num_changed += 1
                self.log(
                    "({:d} of {:d}) updated active info for {}: {:d} enabled, {:d} disabled".format(
                        mv_idx,
                        _total,
                        unicode(mv),
                        enabled,
                        disabled,
                    )
                )
            try:
                cur_dev = mv.device
            except device.DoesNotExist:
                self.log("device with pk no longer present", logging_tools.LOG_LEVEL_WARN)
            else:
                is_active = num_active > 0
                if is_active != cur_dev.has_active_rrds:
                    cur_dev.has_active_rrds = is_active
                    cur_dev.save(update_fields=["has_active_rrds"])
        self.log(
            "checked for stale entries, modified {}, took {} ({} per entry)".format(
                logging_tools.get_plural("device", num_changed),
                logging_tools.get_diff_time_str(time.time() - cur_time),
                logging_tools.get_diff_time_str((time.time() - cur_time) / max(1, _total)),
            )
        )

    def _clear_old_graphs(self):
        cur_time = time.time()
        graph_root = global_config["GRAPH_ROOT"]
        del_list = []
        if os.path.isdir(graph_root):
            for entry in os.listdir(graph_root):
                if entry.endswith(".png"):
                    full_name = os.path.join(graph_root, entry)
                    c_time = os.stat(full_name)[stat.ST_CTIME]
                    diff_time = abs(c_time - cur_time)
                    if diff_time > 5 * 60:
                        del_list.append(full_name)
        else:
            self.log("graph_root '{}' not found, strange".format(graph_root), logging_tools.LOG_LEVEL_ERROR)
        if del_list:
            self.log("clearing {} in {}".format(
                logging_tools.get_plural("old graph", len(del_list)),
                graph_root))
            for del_entry in del_list:
                try:
                    os.unlink(del_entry)
                except:
                    pass

    def loop_post(self):
        self.__log_template.close()
