# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
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
""" checks for Supermicro Hardware (using SMCIPMITool and others) """

import base64
import bz2
import re
import json
import commands

from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.host_monitoring_struct import ExtReturn
from initat.tools import logging_tools, process_tools, server_command

SMCIPMI_BIN = "SMCIPMITool"


# generate mock with
"""
for com in system power\ status gigabit\ status blade\ status cmm\ status ; do
    echo \ \ \ \ \ \ \ \ \"$com\": \"\"\" ;
    SMCIPMITool be2-rmi ADMIN ADMIN $com ;
    echo \"\"\", ;
done
"""

MOCK_DICT = {
    "sys1": {
        "system": """
Blade Module (20/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     | Selected |     |       | Yes |  450W | (20h)     | cpublade01
 Blade 2  | On     |          |     |       | Yes |  450W | (20h)     | cpublade02
 Blade 3  | On     |          |     |       | Yes |  450W | (20h)     | cpublade03
 Blade 4  | On     |          |     |       | Yes |  450W | (20h)     | cpublade04
 Blade 5  | On     |          |     |       | Yes |  450W | (20h)     | cpublade05
 Blade 6  | On     |          |     |       | Yes |  450W | (20h)     | cpublade06
 Blade 7  | On     |          |     |       | Yes |  450W | (20h)     | cpublade07
 Blade 8  | On     |          |     |       | Yes |  450W | (20h)     | cpublade08
 Blade 9  | On     |          |     |       | Yes |  450W | (20h)     | cpublade09
 Blade 10 | On     |          |     |       | Yes |  450W | (20h)     | cpublade10
 Blade 11 | On     |          |     |       | Yes |  450W | (20h)     | cpublade11
 Blade 12 | On     |          |     |       | Yes |  450W | (20h)     | cpublade12
 Blade 13 | On     |          |     |       | Yes |  450W | (20h)     | cpublade13
 Blade 14 | On     |          |     |       | Yes |  450W | (20h)     | cpublade14
 Blade 15 | On     |          |     |       | Yes |  450W | (20h)     | cpublade15
 Blade 16 | On     |          |     |       | Yes |  450W | (20h)     | cpublade16
 Blade 17 | On     |          |     |       | Yes |  450W | (20h)     | cpublade17
 Blade 18 | On     |          |     |       | Yes |  450W | (20h)     | cpublade18
 Blade 19 | On     |          |     |       | Yes |  450W | (20h)     | cpublade19
 Blade 20 | On     |          |     |       | Yes |  450W | (20h)     | cpublade20

Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  5381 |  5152 | 27C/ 81F |  3000 |  29.0A |  2.25A | 1.2 |  02
 PS 2 | On    |  5267 |  5381 | 27C/ 81F |  3000 |  24.0A |  1.62A | 1.2 |  02
 PS 3 | On    |  5267 |  5267 | 28C/ 82F |  3000 |  24.0A |  1.75A | 1.2 |  02
 PS 4 | On    |  5496 |  5267 | 28C/ 82F |  3000 |  24.0A |  1.62A | 1.2 |  02

CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now
""",
        "power status": """
Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  5267 |  5152 | 28C/ 82F |  3000 |  29.0A |  2.25A | 1.2 |  02
 PS 2 | On    |  5267 |  5267 | 27C/ 81F |  3000 |  24.0A |  1.62A | 1.2 |  02
 PS 3 | On    |  5381 |  5267 | 28C/ 82F |  3000 |  24.0A |  1.75A | 1.2 |  02
 PS 4 | On    |  5496 |  5267 | 28C/ 82F |  3000 |  24.0A |  1.62A | 1.2 |  02

""",
        "gigabit status": """



""",
        "ib status": """



""",
        "blade status": """
Blade Module (20/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     | Selected |     |       | Yes |  450W | (20h)     | cpublade01
 Blade 2  | On     |          |     |       | Yes |  450W | (20h)     | cpublade02
 Blade 3  | On     |          |     |       | Yes |  450W | (20h)     | cpublade03
 Blade 4  | On     |          |     |       | Yes |  450W | (20h)     | cpublade04
 Blade 5  | On     |          |     |       | Yes |  450W | (20h)     | cpublade05
 Blade 6  | On     |          |     |       | Yes |  450W | (20h)     | cpublade06
 Blade 7  | On     |          |     |       | Yes |  450W | (20h)     | cpublade07
 Blade 8  | On     |          |     |       | Yes |  450W | (20h)     | cpublade08
 Blade 9  | On     |          |     |       | Yes |  450W | (20h)     | cpublade09
 Blade 10 | On     |          |     |       | Yes |  450W | (20h)     | cpublade10
 Blade 11 | On     |          |     |       | Yes |  450W | (20h)     | cpublade11
 Blade 12 | On     |          |     |       | Yes |  450W | (20h)     | cpublade12
 Blade 13 | On     |          |     |       | Yes |  450W | (20h)     | cpublade13
 Blade 14 | On     |          |     |       | Yes |  450W | (20h)     | cpublade14
 Blade 15 | On     |          |     |       | Yes |  450W | (20h)     | cpublade15
 Blade 16 | On     |          |     |       | Yes |  450W | (20h)     | cpublade16
 Blade 17 | On     |          |     |       | Yes |  450W | (20h)     | cpublade17
 Blade 18 | On     |          |     |       | Yes |  450W | (20h)     | cpublade18
 Blade 19 | On     |          |     |       | Yes |  450W | (20h)     | cpublade19
 Blade 20 | On     |          |     |       | Yes |  450W | (20h)     | cpublade20
""",
        "cmm status": """
CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now

CMM IP address:
---------------
CMM 1 IP: 192.168.248.175
""",
    },
    "sys2": {
        "system": """
Blade Module (10/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     | Selected |     |       | Yes |  875W | B9DRG-E   | gpublade01
 Blade 2  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade02
 Blade 3  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade03
 Blade 4  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade04
 Blade 5  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade05
 Blade 6  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade06
 Blade 7  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade07
 Blade 8  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade08
 Blade 9  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade09
 Blade 10 | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade10

Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  7442 |  7442 | 26C/ 79F |  3000 |  32.0A |  2.37A | 1.2 |  02
 PS 2 | On    |  7557 |  7328 | 27C/ 81F |  3000 |  33.0A |  2.62A | 1.2 |  02
 PS 3 | On    |  7557 |  7442 | 27C/ 81F |  3000 |  28.0A |  2.37A | 1.2 |  02
 PS 4 | On    |  7557 |  7442 | 27C/ 81F |  3000 |  28.0A |  2.25A | 1.2 |  02

CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now
""",
        "power status": """
Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  7442 |  7442 | 26C/ 79F |  3000 |  32.0A |  2.37A | 1.2 |  02
 PS 2 | On    |  7557 |  7328 | 27C/ 81F |  3000 |  33.0A |  2.62A | 1.2 |  02
 PS 3 | On    |  7557 |  7442 | 27C/ 81F |  3000 |  28.0A |  2.37A | 1.2 |  02
 PS 4 | On    |  7557 |  7442 | 27C/ 81F |  3000 |  28.0A |  2.25A | 1.2 |  02

""",
        "gigabit status": """



""",
        "blade status": """
Blade Module (10/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     | Selected |     |       | Yes |  875W | B9DRG-E   | gpublade01
 Blade 2  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade02
 Blade 3  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade03
 Blade 4  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade04
 Blade 5  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade05
 Blade 6  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade06
 Blade 7  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade07
 Blade 8  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade08
 Blade 9  | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade09
 Blade 10 | On     |          |     |       | Yes |  875W | B9DRG-E   | gpublade10

""",
        "cmm status": """
CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now

CMM IP address:
---------------
CMM 1 IP: 192.168.248.174
""",
    },
    "sys3": {
        "system": """
Blade Module (10/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     |          |     |       | Yes |  875W | B9DRG     | blade01
 Blade 2  | On     |          |     |       | Yes |  875W | B9DRG     | blade02
 Blade 3  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade03
 Blade 4  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade04
 Blade 5  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade05
 Blade 6  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade06
 Blade 7  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade07
 Blade 8  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade08
 Blade 9  | On     | Selected |     |       | Yes |  875W | B9DRG-E   | blade09
 Blade 10 | On     |          |     |       | Yes |  875W | B9DRG-E   | blade10

Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  7671 |  7099 | 27C/ 81F |  3000 |  31.0A |   2.5A | 1.0 |  01
 PS 2 | On    |  7099 |  7557 | 26C/ 79F |  3000 |  35.0A |  2.87A | 1.0 |  01
 PS 3 | On    |  7557 |  7442 | 25C/ 77F |  3000 |  30.0A |  2.37A | 1.0 |  01
 PS 4 | On    |  7328 |  7557 | 24C/ 75F |  3000 |  30.0A |   2.5A | 1.0 |  01

CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now
""",
        "power status": """
Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  7671 |  7099 | 27C/ 81F |  3000 |  31.0A |   2.5A | 1.0 |  01
 PS 2 | On    |  7099 |  7557 | 26C/ 79F |  3000 |  35.0A |  2.87A | 1.0 |  01
 PS 3 | On    |  7557 |  7442 | 25C/ 77F |  3000 |  30.0A |  2.37A | 1.0 |  01
 PS 4 | On    |  7328 |  7557 | 24C/ 75F |  3000 |  30.0A |   2.5A | 1.0 |  01

""",
        "gigabit status": """



""",
        "blade status": """
Blade Module (10/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     |          |     |       | Yes |  875W | B9DRG     | blade01
 Blade 2  | On     |          |     |       | Yes |  875W | B9DRG     | blade02
 Blade 3  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade03
 Blade 4  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade04
 Blade 5  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade05
 Blade 6  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade06
 Blade 7  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade07
 Blade 8  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade08
 Blade 9  | On     | Selected |     |       | Yes |  875W | B9DRG-E   | blade09
 Blade 10 | On     |          |     |       | Yes |  875W | B9DRG-E   | blade10

""",
        "cmm status": """
CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now

CMM IP address:
---------------
CMM 1 IP: 192.168.102.130
""",
    },
    "sys4": {
        "system": """
Blade Module (10/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     |          |     |       | Yes |  875W | B9DRG     | blade01
 Blade 2  | On     |          |     |       | Yes |  875W | B9DRG     | blade02
 Blade 3  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade03
 Blade 4  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade04
 Blade 5  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade05
 Blade 6  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade06
 Blade 7  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade07
 Blade 8  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade08
 Blade 9  | On     | Selected |     |       | Yes |  875W | B9DRG-E   | blade09
 Blade 10 | On     |          |     |       | Yes |  875W | B9DRG-E   | blade10

Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  7671 |  7099 | 27C/ 81F |  3000 |  31.0A |   2.5A | 1.0 |  01
 PS 2 | On    |  7099 |  7557 | 26C/ 79F |  3000 |  35.0A |  2.87A | 1.0 |  01
 PS 3 | On    |  7557 |  7442 | 25C/ 77F |  3000 |  30.0A |  2.37A | 1.0 |  01
 PS 4 | On    |  7328 |  7557 | 24C/ 75F |  3000 |  30.0A |   2.5A | 1.0 |  01

CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now
""",
        "power status": """
Power Supply Module (4/4)
--------------------------
 PS   | Power | Fan 1 | Fan 2 | Temp.    | Watts |     DC |     AC | F/W | FRU
 --   | ----- | ----- | ----- | -----    | ----- |     -- |     -- | --- | ---
 PS 1 | On    |  7671 |  7099 | 27C/ 81F |  3000 |  31.0A |   2.5A | 1.0 |  01
 PS 2 | On    |  7099 |  7557 | 26C/ 79F |  3000 |  35.0A |  2.87A | 1.0 |  01
 PS 3 | On    |  7557 |  7442 | 25C/ 77F |  3000 |  30.0A |  2.37A | 1.0 |  01
 PS 4 | On    |  7328 |  7557 | 24C/ 75F |  3000 |  30.0A |   2.5A | 1.0 |  01

""",
        "gigabit status": """



""",
        "blade status": """
Blade Module (10/20)
--------------------
 Blade    | Power  | KVM      | UID | Error | BMC |  Watt | MB        | Name
 -----    | -----  | ---      | --- | ----- | --- |  ---- | --        | ----
 Blade 1  | On     |          |     |       | Yes |  875W | B9DRG     | blade01
 Blade 2  | On     |          |     |       | Yes |  875W | B9DRG     | blade02
 Blade 3  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade03
 Blade 4  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade04
 Blade 5  | On     |          |     |       | Yes |  375W | B9DRG-E   | blade05
 Blade 6  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade06
 Blade 7  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade07
 Blade 8  | On     |          |     |       | Yes |  875W | B9DRG-E   | blade08
 Blade 9  | On     | Selected |     |       | Yes |  875W | B9DRG-E   | blade09
 Blade 10 | On     |          |     |       | Yes |  875W | B9DRG-E   | blade10

""",
        "cmm status": """
CMM Module(1/2)
----------------
 CMM   | M/S    | Status
 ---   | ---    | ------
 CMM 1 | Master | OK

CMM 1 is being managed now

CMM IP address:
---------------
CMM 1 IP: 192.168.102.130
""",
    }
}


class _general(hm_classes.hm_module):
    pass


def generate_dict(in_list):
    r_dict = {}
    cur_mode, sense_flag, handle_lines = (None, True, False)
    for line in in_list:
        parts = line.lower().strip().split()
        if sense_flag:
            if parts:
                cur_mode = parts[0]
                handle_lines = line.endswith(")")
                if handle_lines:
                    cur_mode = parts[0]
                    num_present, num_possible = [int(entry) for entry in line.split("(")[1].split(")")[0].split("/")]
                    cur_dict = {
                        "possible": num_possible,
                        "present": num_present,
                        "info": line.split("(")[0].strip(),
                    }
                    r_dict[cur_mode] = cur_dict
                offset = 0
                sense_flag = False
        else:
            if not parts:
                sense_flag = True
            else:
                if handle_lines:
                    offset += 1
                    if offset == 2:
                        cur_map = [entry.strip() for entry in line.lower().split("|")]
                    elif offset > 3:
                        parts = [entry.strip() for entry in line.lower().split("|")]
                        num = int(parts[0].split()[-1])
                        loc_dict = dict(zip(cur_map, parts))
                        cur_dict[num] = loc_dict
    return r_dict


MOCK_MODE = None  # "sys1"  # None  # "sys1"


class SMCIpmiStruct(hm_classes.subprocess_struct):
    g_error_cache = {}

    class Meta:
        max_usage = 128
        id_str = "supermicro"
        verbose = False

    def __init__(self, log_com, srv_com, com, real_com, hm_command):
        self.__log_com = log_com
        self.__real_com = real_com
        self.__hm_command = hm_command
        if MOCK_MODE:
            com = "sleep 5"
        hm_classes.subprocess_struct.__init__(
            self,
            srv_com,
            com,
        )

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[smcipmi] {}".format(what), level)

    def process(self):
        if MOCK_MODE is None:
            output = self.read()
        else:
            output = MOCK_DICT[MOCK_MODE][self.__real_com]
        if output is not None:
            if output.count("java.lang.NullPointerException"):
                self.log(
                    "call problem: {}".format(
                        output,
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                if self.__real_com in SMCIpmiStruct.g_error_cache:
                    self.log("return last sane value", logging_tools.LOG_LEVEL_WARN)
                    output = SMCIpmiStruct.g_error_cache[self.__real_com]
            else:
                # store to global error cache
                SMCIpmiStruct.g_error_cache[self.__real_com] = output
            # self.log(
            #    "output has {:d} bytes: {}".format(
            #        len(output),
            #        re.sub("-+", "-", re.sub("\s+", " ", output)),
            #    )
            # )
            self.__hm_command.store_object(self.__real_com, output)
            self.srv_com["output"] = output


class SMCRetrievePendingStruct(hm_classes.subprocess_struct):
    class Meta:
        max_usage = 128

    def __init__(self, srv_com, real_com):

        hm_classes.subprocess_struct.__init__(
            self,
            srv_com,
            None,
        )
        # cache set via resolve_cache
        self._obj = None

    def resolve_cache(self, obj):
        self._obj = obj

    def finished(self):
        if self._obj:
            self.srv_com["output"] = self._obj
            return True
        else:
            return False


class smcipmi_command(hm_classes.hm_command, hm_classes.HMCCacheMixin):
    class Meta:
        cache_timeout = 60
    info_str = "SMCIPMITool frontend"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--user", dest="user", type=str, default="ADMIN")
        self.parser.add_argument("--passwd", dest="passwd", type=str, default="ADMIN")
        self.parser.add_argument("--ip", dest="ip", type=str)
        # self.parser.add_argument("--passive", default=False, action="store_true")
        self.parser.add_argument("--passive-check-prefix", type=str, default="-")
        self.__smcipmi_binary = process_tools.find_file(SMCIPMI_BIN)
        self.__smcipmi_version = None
        _KNOWN_VERSIONS = {2110, 2140}
        _DEF_VERSION = 2110
        if self.__smcipmi_binary:
            self.log("found {} at {}".format(SMCIPMI_BIN, self.__smcipmi_binary))
            _stat, _out = commands.getstatusoutput("{}".format(self.__smcipmi_binary))
            vers_re = re.compile("^smc\s*ipmi\s*tool\s*(?P<version>v\d+[^(]+).*$", re.IGNORECASE)
            for _line in _out.split("\n"):
                _match = vers_re.match(_line.strip())
                if _match:
                    _vers_str = _match.group("version").replace("V", "")
                    _vers_int = int(_vers_str.replace(".", ""))
                    if _vers_int in _KNOWN_VERSIONS:
                        self.log("found known version '{}' -> {:d}".format(_vers_str, _vers_int))
                    else:
                        self.log(
                            "found unknown version '{}' -> {:d}, mapping to {:d}".format(
                                _vers_str,
                                _vers_int,
                                _DEF_VERSION,
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )
                        _vers_int = _DEF_VERSION
                    self.__smcipmi_version = _vers_int
        else:
            self.log("no SMCIPMI binary found", logging_tools.LOG_LEVEL_WARN)

    def _map_command(self, in_com):
        _com = {
            "counter": "system",
            "power": "power status",
            "gigabit": "gigabit status",
            "blade": "blade status",
            "ib": "ib status",
            "ibqdr": "ib status",
            "ibfdr": "ib status",
            "cmm": "cmm status",
        }.get(in_com, in_com)
        if self.__smcipmi_version > 2110:
            _com = "superblade {}".format(_com)
        return _com

    def __call__(self, srv_com, cur_ns):
        _mock = None
        args = cur_ns.arguments
        if not len(args):
            srv_com.set_result(
                "no arguments specified",
                server_command.SRV_REPLY_STATE_ERROR,
            )
            cur_smcc = None
        elif not self.__smcipmi_binary and not MOCK_MODE:
            srv_com.set_result(
                "no {} binary found".format(SMCIPMI_BIN),
                server_command.SRV_REPLY_STATE_ERROR,
            )
            cur_smcc = None
        else:
            com = args[0]
            real_com = self._map_command(com)
            srv_com["orig_command"] = com
            srv_com["mapped_command"] = real_com
            srv_com["version"] = "{:d}".format(self.__smcipmi_version)
            if self.cache_valid(real_com):
                cur_smcc = None
                srv_com["output"] = self.load_object(real_com)
            elif self.retrieval_pending(real_com):
                self.log("{} (pend)".format(com))
                cur_smcc = SMCRetrievePendingStruct(
                    srv_com,
                    real_com,
                )
                self.register_retrieval_client(real_com, cur_smcc)
            else:
                self.start_retrieval(real_com)
                self.log("mapping command '{}' to '{}'".format(com, real_com))
                _com = "{} {} {} {} {}".format(
                    self.__smcipmi_binary,
                    cur_ns.ip,
                    cur_ns.user,
                    cur_ns.passwd,
                    real_com,
                )
                cur_smcc = SMCIpmiStruct(
                    self.log,
                    srv_com,
                    _com,
                    real_com,
                    self,
                )
        return cur_smcc

    def _handle_power(self, in_dict, **kwargs):
        if in_dict["power"] == "on":
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        cur_temp = float(in_dict["temp."].split("/")[0][:-1])
        cur_ac = float(in_dict["ac"][:-1])
        return ret_state, "PS '{}' is {}, temp: {:.2f} C, fan1/2: {:d}/{:d}, {:.2f} A | smcipmi psu={:d} temp={:.2f} amps={:.2f} fan1={:d} fan2={:d}".format(
            in_dict["ps"],
            in_dict["power"],
            cur_temp,
            int(in_dict["fan 1"]),
            int(in_dict["fan 2"]),
            cur_ac,
            int(in_dict["ps"].split()[-1]),
            cur_temp,
            cur_ac,
            int(in_dict["fan 1"]),
            int(in_dict["fan 2"]),
        )

    def _handle_blade(self, in_dict, **kwargs):
        if in_dict["power"] == "on" or in_dict["error"]:
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        return ret_state, "blade '{}' is {} ({})".format(
            in_dict["blade"],
            in_dict["power"],
            in_dict["error"] if in_dict["error"] else "no error",
        )

    def _handle_gigabit(self, in_dict, **kwargs):
        if in_dict["power"] == "on" or in_dict["error"]:
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        return ret_state, "gigabit switch '{}' is {} ({})".format(
            in_dict["gbsw"],
            in_dict["power"],
            in_dict["error"] if in_dict["error"] else "no error",
        )

    def _handle_cmm(self, in_dict, **kwargs):
        if in_dict["status"] == "ok":
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        return ret_state, "CMM '{}' is {} ({})".format(
            in_dict["cmm"],
            in_dict["status"],
            in_dict["m/s"],
        )

    def _handle_ibqdr(self, in_dict, **kwargs):
        return self._handle_ib(in_dict, **kwargs)

    def _handle_ibfdr(self, in_dict, **kwargs):
        return self._handle_ib(in_dict, **kwargs)

    def _handle_ib(self, in_dict, **kwargs):
        obj_type = kwargs["obj_type"]
        if in_dict["power"] == "on":
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        return ret_state, "IB switch '{}' is {}".format(
            in_dict[obj_type],
            in_dict["power"],
        )

    def interpret(self, srv_com, cur_ns):
        orig_com, _mapped_com = (
            srv_com.xpath(".//ns:orig_command/text()", smart_strings=False)[0],
            srv_com.xpath(".//ns:mapped_command/text()", smart_strings=False)[0],
        )
        r_dict = generate_dict(srv_com.xpath(".//ns:output/text()", smart_strings=False)[0].split("\n"))
        if orig_com == "counter":
            _g_ret_state = limits.nag_STATE_OK
            ascii_chunk = None
            _g_ret_str = ", ".join(
                [
                    "{} : {:d} of {:d}".format(
                        key,
                        value["present"],
                        value["possible"],
                    ) for key, value in r_dict.iteritems()
                ]
            )
            _prefix = cur_ns.passive_check_prefix
            if _prefix != "-":
                _list = []
                for m_key in sorted(r_dict):
                    _struct = r_dict[m_key]
                    for e_key in sorted([_key for _key in _struct.iterkeys() if type(_key) in [int]]):
                        _handle = getattr(self, "_handle_{}".format(m_key))
                        _state, _result = _handle(r_dict[m_key][e_key], obj_type=m_key)
                        _list.append(
                            (
                                u"{} {:d}".format(_struct["info"], e_key),
                                _state,
                                _result,
                            )
                        )
                _passive_dict = {
                    "list": _list,
                    "prefix": _prefix,
                }
                ascii_chunk = base64.b64encode(bz2.compress(json.dumps(_passive_dict)))
            return ExtReturn(_g_ret_state, _g_ret_str, ascii_chunk=ascii_chunk)
        else:
            # get number
            obj_type = orig_com
            _arg = srv_com.xpath(".//ns:arguments/ns:rest/text()", smart_strings=False)[0]
            try:
                obj_num = int(_arg.strip().split()[-1])
            except:
                return limits.nag_STATE_CRITICAL, "cannot extract obj_num from argument '{}'".format(_arg)
            else:
                # obj_key = {"ib" : "ibqdr"}.get(obj_type, obj_type)
                if obj_type in r_dict:
                    if obj_num in r_dict[obj_type]:
                        return getattr(self, "_handle_{}".format(obj_type))(r_dict[obj_type][obj_num], obj_type=obj_type)
                    else:
                        return limits.nag_STATE_CRITICAL, "no {}#{:d} found".format(
                            obj_type,
                            obj_num,
                        )
                else:
                    if r_dict:
                        return limits.nag_STATE_CRITICAL, "key {} not found in {}".format(
                            obj_type,
                            ", ".join(sorted(r_dict.keys()))
                        )
                    else:
                        return limits.nag_STATE_CRITICAL, "key {} not found, null result".format(
                            obj_type,
                        )
