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
""" cluster-server, background base object """

from initat.cluster_server.config import global_config
from initat.tools import logging_tools
from initat.tools import mail_tools


class bg_stuff(object):
    class Meta:
        min_time_between_runs = 30
        creates_machvector = False

    def __init__(self, srv_process, sql_info):
        # copy Meta keys
        for key in dir(bg_stuff.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(bg_stuff.Meta, key))
        # self.__name = name
        self.server_process = srv_process
        self.sql_info = sql_info
        self.init_bg_stuff()
        self.__last_call = None

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.server_process.log("[bg %s] %s" % (self.Meta.name, what), level)

    def init_bg_stuff(self):
        pass

    def __call__(self, cur_time, drop_com):
        if self.__last_call and abs(self.__last_call - cur_time) < self.Meta.min_time_between_runs:
            # self.log("last call only %d seconds ago, skipping" % (abs(self.__last_call - cur_time)),
            #         logging_tools.LOG_LEVEL_WARN)
            pass
        else:
            self.__last_call = cur_time
            add_obj = self._call(cur_time, drop_com.builder)
            if add_obj is not None:
                drop_com["vector_{}".format(self.Meta.name)] = add_obj
                drop_com["vector_{}".format(self.Meta.name)].attrib["type"] = "vector"

    def _call(self, cur_time, drop_com):
        self.log("dummy __call__()")
        return None

    def step(self, *args, **kwargs):
        self.server_process.step(*args, **kwargs)

    def send_mail(self, to_addr, subject, msg_body):
        new_mail = mail_tools.mail(subject, "%s@%s" % (global_config["FROM_NAME"], global_config["FROM_ADDR"]), to_addr, msg_body)
        new_mail.set_server(global_config["MAILSERVER"], global_config["MAILSERVER"])
        _stat, log_lines = new_mail.send_mail()
        return log_lines
