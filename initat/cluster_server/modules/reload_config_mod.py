# Copyright (C) 2007,2012-2014 Andreas Lang-Nevyjel
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
""" reload global_config, needed / working ? """

from initat.cluster_server.config import global_config
import configfile
import cs_base_class

class reload_config(cs_base_class.server_com):
    def _call(self, cur_inst):
        configfile.read_config_from_db(global_config, self.dc, "server")
        # log config
        for conf_line in global_config.get_config_info():
            self.log("Config : {}".format(conf_line))
        cur_inst.srv_com.set_result(
            "ok reloaded config",
        )
