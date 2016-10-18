# -*- coding: utf-8 -*-
# Copyright (C) 2001-2008,2010-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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

"""
long running check implementation by sieghart, to be improved ...
"""

from __future__ import unicode_literals, print_function

from multiprocessing import Process

LONG_RUNNING_CHECK_RESULT_KEY = "long_running_check_result"


class LongRunningCheck(object):
    """ Represents a long running check.

    Objects of this class are usually returned in __call__ of a hm_command.
    Doing this signals the server that code should be executed "in the
    background".
    """
    def perform_check(self, queue):
        """ Override this method with the implementation of the actual check.
        """
        raise NotImplementedError()

    def start(self, queue):
        p = Process(target=self.perform_check, args=(queue, ))
        p.start()
        return p
