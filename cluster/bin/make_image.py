#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

import sys
import os,os.path

def main():
    s_dir="/"
    tot_size=0
    for root,dirs,files in os.walk(s_dir):
        if "dexv" in dirs:
            dirs.remove("dev")
        else:
            num_files=len(files)
            act_size=0
            for file in files:
                act_file=os.path.join(root,file)
                if os.path.islink(act_file):
                    print "Link",act_file
                elif os.path.isfile(act_file):
                    act_size+=os.path.getsize(act_file)
                else:
                    print "What?",act_file
            print "%-70s consumes %10d bytes in %4d non-directory files"%(root,act_size,num_files)
            tot_size+=act_size
    print tot_size
        
if __name__=="__main__":
    main()
    
