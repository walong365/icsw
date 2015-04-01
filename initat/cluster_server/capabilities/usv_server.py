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
""" cluster-server, USV handling """

from initat.cluster_server.capabilities.base import bg_stuff
import commands
import logging_tools


class usv_server_stuff(bg_stuff):
    class Meta:
        creates_machvector = True
        name = "usv_server"

    def do_apc_call(self):
        stat, out = commands.getstatusoutput("apcaccess")
        if stat:
            self.log("cannot execute apcaccess (stat=%d): %s" % (stat, str(out)),
                     logging_tools.LOG_LEVEL_ERROR)
            apc_dict = {}
        else:
            apc_dict = {
                l_part[0].lower().strip(): l_part[1].strip() for l_part in [line.strip().split(":", 1) for line in out.split("\n")] if len(l_part) == 2
            }
        return apc_dict

    def init_machvector(self):
        ret_list = []
        apc_dict = self.do_apc_call()
        if apc_dict:
            for key, _value in apc_dict.iteritems():
                if key == "linev":
                    ret_list.append("usv.volt.line:0.:Line Voltage:Volt:1:1")
                elif key == "loadpct":
                    ret_list.append("usv.percent.load:0.:Percent Load Capacity:%:1:1")
                elif key == "bcharge":
                    ret_list.append("usv.percent.charge:0.:Battery Charge:%:1:1")
                elif key == "timeleft":
                    ret_list.append("usv.time.left:0.:Time Left in Minutes:1:1:1")
                elif key == "itemp":
                    ret_list.append("usv.temp.int:0.:Internal Temperature:C:1:1")
        return ret_list

    def get_machvector(self):
        ret_list = []
        apc_dict = self.do_apc_call()
        if apc_dict:
            for key, value in apc_dict.iteritems():
                if value.split():
                    first_v = value.split()[0]
                    if key == "linev":
                        ret_list.append("usv.volt.line:f:%.2f" % (float(first_v)))
                    elif key == "loadpct":
                        ret_list.append("usv.percent.load:f:%.2f" % (float(first_v)))
                    elif key == "bcharge":
                        ret_list.append("usv.percent.charge:f:%.2f" % (float(first_v)))
                    elif key == "timeleft":
                        ret_list.append("usv.time.left:f:%.2f" % (float(first_v)))
                    elif key == "itemp":
                        ret_list.append("usv.temp.int:f:%.2f" % (float(first_v)))
        return ret_list
