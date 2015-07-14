# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel
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
from initat.tools import logging_tools
from initat.host_monitoring import hm_classes


class usv_server_stuff(bg_stuff):
    class Meta:
        creates_machvector = True
        name = "usv_server"

    def do_apc_call(self):
        _c_stat, out = commands.getstatusoutput("apcaccess")
        if _c_stat:
            self.log(
                "cannot execute apcaccess (stat={:d}): {}".format(_c_stat, str(out)),
                logging_tools.LOG_LEVEL_ERROR
            )
            apc_dict = {}
        else:
            apc_dict = {
                l_part[0].lower().strip(): l_part[1].strip() for l_part in [
                    line.strip().split(":", 1) for line in out.split("\n")
                ] if len(l_part) == 2
            }
        return apc_dict

    def _call(self, cur_time, builder):
        apc_dict = self.do_apc_call()
        if apc_dict and self.Meta.creates_machvector:
            my_vector = builder("values")
            valid_until = cur_time + self.Meta.min_time_between_runs * 2
            for key, value in apc_dict.iteritems():
                if value.split():
                    first_v = value.split()[0]
                    if key == "linev":
                        my_vector.append(
                            hm_classes.mvect_entry(
                                "usv.volt.line",
                                info="Line voltage",
                                default=0.,
                                first_v=float(first_v),
                                base=1000,
                                valid_until=valid_until,
                                unit="Volt",
                            ).build_xml(builder)
                        )
                    elif key == "loadpct":
                        my_vector.append(
                            hm_classes.mvect_entry(
                                "usv.percent.load",
                                info="Percent Load Capacity",
                                default=0.,
                                value=float(first_v),
                                base=1,
                                valid_until=valid_until,
                                unit="%",
                            ).build_xml(builder)
                        )
                    elif key == "bcharge":
                        my_vector.append(
                            hm_classes.mvect_entry(
                                "usv.percent.charge",
                                info="Battery charge",
                                default=0.,
                                value=float(first_v),
                                base=1,
                                valid_until=valid_until,
                                unit="%",
                            ).build_xml(builder)
                        )
                    elif key == "timeleft":
                        my_vector.append(
                            hm_classes.mvect_entry(
                                "usv.time.left",
                                info="Time left in minutes",
                                default=0.,
                                value=float(first_v),
                                base=1,
                                valid_until=valid_until,
                                unit="m",
                            ).build_xml(builder)
                        )
                    elif key == "itemp":
                        my_vector.append(
                            hm_classes.mvect_entry(
                                "usv.temp.int",
                                info="Internal temperature",
                                default=0.,
                                value=float(first_v),
                                base=1,
                                valid_until=valid_until,
                                unit="C",
                            ).build_xml(builder)
                        )
        else:
            my_vector = None
        return my_vector
