#!/usr/bin/python-init -Ot
#
# Copyright (c) 2007,2009 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" stackless tools """

import stackless

class named_tasklet(stackless.tasklet):
    def __new__(self, name):
        return stackless.tasklet.__new__(self)
    def __init__(self, name):
        self.name = name
        stackless.tasklet.__init__(self)

def name_main_tasklet(name):
    # not working, has to reside in main_code
    new_main = named_tasklet(name)
    new_main.capture()

def get_act_tasklet_name(default_name="NONAME"):
    try:
        act_name = stackless.getcurrent().name
    except:
        act_name = default_name
    return act_name
