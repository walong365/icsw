#!/usr/bin/python-init
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of host-monitoring
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

import time
import sys
import re
import os
import time
import pprint

def main():
    mf_obj = mail_log_object(seek_to_end=False)
    while True:
        mf_obj.parse_lines()
        print mf_obj.get_snapshot()
        break
        time.sleep(2)
        
if __name__ == "__main__":
    main()
