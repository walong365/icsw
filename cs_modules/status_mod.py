#!/usr/bin/python -Ot
#
# Copyright (C) 2007 Andreas Lang-Nevyjel
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
""" returns status of the cluster and updates the cluster_name if necessary """
import sys
import cs_base_class
import configfile
import os

CLUSTER_NAME_FILE = "/etc/sysconfig/cluster/cluster_name"

class status(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_showtime(0)
        self.set_write_log(0)
    def call_it(self, opt_dict, call_params):
        tp = call_params.get_thread_pool()
        if tp:
            call_params.dc.execute("SELECT d.device_idx FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx AND dg.cluster_device_group")
            if call_params.dc.rowcount:
                cd_idx = call_params.dc.fetchone()["device_idx"]
                dv = configfile.device_variable(call_params.dc, cd_idx, "CLUSTER_NAME")
                if dv.is_set():
                    new_name = dv.get_value()
                    if os.path.isfile(CLUSTER_NAME_FILE):
                        try:
                            old_name = file(CLUSTER_NAME_FILE, "r").read().strip().split()[0]
                        except:
                            old_name = ""
                    else:
                        old_name = ""
                    if new_name != old_name:
                        try:
                            file(CLUSTER_NAME_FILE, "w").write(dv.get_value())
                        except:
                            pass
            num_threads, num_ok = (tp.num_threads(False),
                                   tp.num_threads_running(False))
            if num_ok == num_threads:
                ret_str = "OK: all %d threads running, version %s" % (num_ok, call_params.get_l_config()["VERSION_STRING"])
            else:
                ret_str = "ERROR: only %d of %d threads running, version %s" % (num_ok, num_threads, call_params.get_l_config()["VERSION_STRING"])
        else:
            ret_str = "warn running local"
        return ret_str
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
