#!/usr/bin/python-init -Otu
# Copyright (C) 2014 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone
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
""" test module dependency handler """

import module_dependency_tools
import sys
import pprint
import logging_tools

def log_com(what, log_level=logging_tools.LOG_LEVEL_OK):
    print("[{:2d}] {}".format(log_level, what))

def main():
    k_dir = module_dependency_tools.dependency_handler(sys.argv[1], log_com=log_com, linux_native=True)
    # test resolve
    k_dir.resolve(["mpt2sas.ko"], verbose=True)
    if len(sys.argv) > 2:
        m_dict = k_dir.find_module_by_modalias(sys.argv[2:])
        print sorted(list(set(sum(m_dict.values(), []))))

if __name__ == "__main__":
    main()
