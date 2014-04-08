#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2006,2014 Andreas Lang-Nevyjel, init.at
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
""" generates /etc/sysconfig/ethtool/config for ethtool-init """

import os

def main():
    conf_file = "/etc/sysconfig/ethtool/config"
    if not os.path.isdir(os.path.dirname(conf_file)):
        os.mkdir(os.path.dirname(conf_file))
    conf_data = file(conf_file, "w")
    net_dir = "/sys/class/net"
    drv_dict = {}
    if os.path.isdir(net_dir):
        for entry in os.listdir(net_dir):
            device_link = os.path.join(net_dir, entry, "device")
            driver_link = os.path.join(net_dir, entry, "driver")
            if not os.path.islink(driver_link):
                driver_link = os.path.join(device_link, "driver")
            if os.path.islink(device_link) and os.path.islink(driver_link):
                driver = os.path.basename(os.path.normpath(os.path.join(net_dir, entry, os.readlink(driver_link))))
                pci_info = os.path.basename(os.path.normpath(os.path.join(net_dir, entry, os.readlink(device_link))))
                drv_dict.setdefault(driver, []).append(entry)
                conf_data.write("pci_{}=\"{}\"\n".format(entry, pci_info))
                conf_data.write("drv_{}=\"{}\"\n".format(entry, driver))
                #print entry, pci_info, driver
    for driv_name, driv_nets in drv_dict.iteritems():
        conf_data.write("net_{}=\"{}\"\n".format(driv_name, " ".join(driv_nets)))
    conf_data.close()

if __name__ == "__main__":
    main()
    
