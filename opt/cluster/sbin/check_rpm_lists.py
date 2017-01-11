#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2015,2017 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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



import argparse

from initat.tools import logging_tools, process_tools, net_tools, server_command


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-d", dest="detail", default=False, action="store_true", help="detailed mode [%(default)s]")
    my_parser.add_argument("hosts", nargs=2, help="Devices to check [%(default)s]")
    opts = my_parser.parse_args()
    host_1, host_2 = opts.hosts
    if host_1.count(":"):
        host_1, dir_1 = host_1.split(":", 1)
    else:
        dir_1 = "/"
    if host_2.count(":"):
        host_2, dir_2 = host_2.split(":", 1)
    else:
        dir_2 = "/"
    print("Comparing rpm_lists of %s (dir %s) and %s (dir %s)" % (host_1, dir_1, host_2, dir_2))
    _ns1 = net_tools.SendCommandDefaults(host=host_1, arguments=["rpmlist", dir_1])
    my_com = net_tools.SendCommand(_ns1)
    my_com.init_connection()
    if my_com.connect():
        result_1 = my_com.send_and_receive()
    my_com.close()
    _ns2 = net_tools.SendCommandDefaults(host=host_2, arguments=["rpmlist", dir_2])
    my_com = net_tools.SendCommand(_ns2)
    my_com.init_connection()
    if my_com.connect():
        result_2 = my_com.send_and_receive()
    my_com.close()
    rpm_dict_1 = server_command.decompress(result_1["*pkg_list"], pickle=True)
    rpm_dict_2 = server_command.decompress(result_2["*pkg_list"], pickle=True)
    keys_1 = list(rpm_dict_1.keys())
    keys_2 = list(rpm_dict_2.keys())
    keys_1.sort()
    keys_2.sort()
    missing_in_1 = [x for x in keys_2 if x not in keys_1]
    missing_in_2 = [x for x in keys_1 if x not in keys_2]
    for missing_in, host, _dir in [
        (missing_in_1, host_1, dir_1),
        (missing_in_2, host_2, dir_2),
    ]:
        if missing_in:
            print(
                "{} missing on {} (dir {}):".format(
                    logging_tools.get_plural("package", len(missing_in)),
                    host,
                    _dir
                )
            )
            if opts.detail:
                print("\n".join(missing_in))
            else:
                print(" ".join(missing_in))


if __name__ == "__main__":
    main()
