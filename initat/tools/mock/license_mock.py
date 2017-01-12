#!/usr/bin/python3-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" mock files for sge_license_tools """

import random

MOCK_DATA = {
    "s0": """
lmutil - Copyright (c) 1989-2014 Flexera Software LLC. All Rights Reserved.
Flexible License Manager status on Tue 12/20/2016 10:39

License server status: 1055@lwnsv42022
    License open(s) on lwnsv42022: C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\nsyslmd.lic:

lwnsv42022: license server UP (MASTER) v11.13.1

Vendor daemon status (on lwnsv42022):

  ansyslmd: UP v11.13.1
Feature usage info:

Users of struct:  (Total of 4 licenses issued;  Total of 4 licenses in use)

  "struct" v2017.0630, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    lwnlar1 LWNWS81360.lwn.liebherr.i LWNWS81360.lwn.liebherr.i (v2015.1110) (lwnsv42022/1055 2324), start Tue 12/20 8:26
    lwndoc0 LWNWS78440.lwn.liebherr.i LWNWS78440.lwn.liebherr.i (v2014.1110) (lwnsv42022/1055 110), start Tue 12/20 8:38
    lwnkuv0 LWNWS71510.lwn.liebherr.i LWNWS71510.lwn.liebherr.i (v2015.1110) (lwnsv42022/1055 5508), start Tue 12/20 9:53
    mcrwim6 MCRWS28500.lwn.liebherr.i MCRWS28500.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 1430), start Tue 12/20 10:06

Users of preppost:  (Total of 12 licenses issued;  Total of {:d} licenses in use)

  "preppost" v2017.0630, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    lwnfag0 LWNWS71490.lwn.liebherr.i LWNWS71490.lwn.liebherr.i (v2015.1110) (lwnsv42022/1055 4926), start Tue 12/20 8:41
    lwnpfa0 LWNWS71500.lwn.liebherr.i LWNWS71500.lwn.liebherr.i (v2015.1110) (lwnsv42022/1055 2228), start Tue 12/20 9:00
    lwnosd0 LWNWS71470.lwn.liebherr.i LWNWS71470.lwn.liebherr.i (v2016.0711) (lwnsv42022/1055 2636), start Tue 12/20 9:51
    mcrgrf3 MCRWS25380.lwn.liebherr.i MCRWS25380.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 4031), start Tue 12/20 10:01

Users of stba:  (Total of 20 licenses issued;  Total of {:d} licenses in use)

  "stba" v2017.0630, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    mcrbah2 lwnsu62024.init.prod lwnsu62024 (v2013.1008) (lwnsv42022/1055 2839), start Tue 12/20 8:15
    mcrdrc1 lwnsu62024.init.prod lwnsu62024 (v2013.1008) (lwnsv42022/1055 3807), start Tue 12/20 8:35
    mcrwim6 MCRWS28500.lwn.liebherr.i MCRWS28500.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 1943), start Tue 12/20 8:43
    lwnpfa0 lwnsu62024.init.prod lwnsu62024 (v2015.1110) (lwnsv42022/1055 3067), start Tue 12/20 9:28
    lwnpfa0 lwnsu62024.init.prod lwnsu62024 (v2015.1110) (lwnsv42022/1055 2142), start Tue 12/20 9:29
    lwnosd0 lwnsu62021.init.prod lwnsu62021 (v2013.1008) (lwnsv42022/1055 4228), start Tue 12/20 9:38
    lwnham4 LWNWS62100.lwn.liebherr.i LWNWS62100.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 3539), start Tue 12/20 10:23

Users of piproe:  (Total of 4 licenses issued;  Total of 0 licenses in use)

Users of agppi:  (Total of 6 licenses issued;  Total of 2 licenses in use)

  "agppi" v2017.0630, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    lwndoc0 LWNWS78440.lwn.liebherr.i LWNWS78440.lwn.liebherr.i (v2014.1110) (lwnsv42022/1055 3350), start Tue 12/20 8:38
    mcrwim6 MCRWS28500.lwn.liebherr.i MCRWS28500.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 4830), start Tue 12/20 10:06

Users of kinemat:  (Total of 1 license issued;  Total of 0 licenses in use)

Users of dynamics:  (Total of 1 license issued;  Total of 0 licenses in use)

Users of anshpc:  (Total of 128 licenses issued;  Total of {:d} licenses in use)

  "anshpc" v2017.0630, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    mcrmas0 MCRWS25370.lwn.liebherr.i MCRWS25370.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 4519), start Tue 12/20 8:01, 2 licenses
    mcrwic0 MCRWS20200.lwn.liebherr.i MCRWS20200.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 2008), start Tue 12/20 8:11, 3 licenses
    mcrbah2 lwnsu62024.init.prod lwnsu62024 (v2013.1008) (lwnsv42022/1055 848), start Tue 12/20 8:15, 6 licenses
    mcrdrc1 lwnsu62024.init.prod lwnsu62024 (v2013.1008) (lwnsv42022/1055 1229), start Tue 12/20 8:35, 14 licenses
    lwnpfa0 lwnsu62024.init.prod lwnsu62024 (v2015.1110) (lwnsv42022/1055 4628), start Tue 12/20 9:28, 6 licenses
    lwnpfa0 lwnsu62024.init.prod lwnsu62024 (v2015.1110) (lwnsv42022/1055 730), start Tue 12/20 9:29, 14 licenses
    lwnosd0 lwnsu62021.init.prod lwnsu62021 (v2013.1008) (lwnsv42022/1055 649), start Tue 12/20 9:38, 6 licenses
    lwnham4 LWNWS62100.lwn.liebherr.i LWNWS62100.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 4720), start Tue 12/20 10:24, 2 licenses
    lwnsca7 LWNWS71530.lwn.liebherr.i LWNWS71530.lwn.liebherr.i (v2013.1008) (lwnsv42022/1055 3434), start Tue 12/20 10:28, 2 licenses

Users of ans_act:  (Total of 1 license issued;  Total of 0 licenses in use)
""",
    "s1": """
lmutil - Copyright (c) 1989-2014 Flexera Software LLC. All Rights Reserved.
Flexible License Manager status on Tue 12/20/2016 10:40

License server status: 1055@MCRSVTBLIC
    License open(s) on MCRSVTBLIC: C:\Program Files\ANSYS Inc\Shared Files\Licensing\license_files\nsyslmd.lic:

MCRSVTBLIC: license server UP (MASTER) v11.12.1

Vendor daemon status (on MCRSVTBLIC):

  ansyslmd: UP v11.12.1
Feature usage info:

Users of struct:  (Total of 3 licenses issued;  Total of 1 license in use)

  "struct" v2016.1231, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    lwnsca7 LWNWS71530.lwn.liebherr.i LWNWS71530.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 564), start Tue 12/20 10:28

Users of preppost:  (Total of 8 licenses issued;  Total of 4 licenses in use)

  "preppost" v2016.1231, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    mcrbah2 MCRWS25340.lwn.liebherr.i MCRWS25340.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 852), start Tue 12/20 8:05
    mcrmas0 MCRWS25370.lwn.liebherr.i MCRWS25370.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 1308), start Tue 12/20 8:47
    mcrwic0 MCRWS20200.lwn.liebherr.i MCRWS20200.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 1632), start Tue 12/20 9:20
    mcrwic0 MCRWS20200.lwn.liebherr.i MCRWS20200.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 1267), start Tue 12/20 10:37

Users of stba:  (Total of 8 licenses issued;  Total of 2 licenses in use)

  "stba" v2016.1231, vendor: ansyslmd, expiry: 1-jan-0
  floating license

    mcrmas0 MCRWS25370.lwn.liebherr.i MCRWS25370.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 362), start Tue 12/20 8:01
    mcrwic0 MCRWS20200.lwn.liebherr.i MCRWS20200.lwn.liebherr.i (v2013.1008) (MCRSVTBLIC/1055 977), start Tue 12/20 8:11

Users of piproe:  (Total of 3 licenses issued;  Total of 0 licenses in use)

Users of agppi:  (Total of 3 licenses issued;  Total of 0 licenses in use)
"""
}


def mock_license_call(com_line):
    # debug code
    if com_line.count("lwnsv42022"):
        ret_code = 0
        usages = [random.randint(0, 12) for _idx in range(4)]
        out = MOCK_DATA["s0"].format(usages[0], usages[1], usages[2])
    elif com_line.count("mcrsvtblic"):
        ret_code = 0
        out = MOCK_DATA["s1"]
    return ret_code, out
