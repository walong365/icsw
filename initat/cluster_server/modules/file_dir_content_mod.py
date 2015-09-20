# Copyright (C) 2007,2013-2015 Lang-Nevyjel
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
""" fetches informations from files or directories """

from initat.host_monitoring import filesys_tools

import cs_base_class


class get_file_content(cs_base_class.server_com):
    def _call(self, cur_inst):
        filesys_tools.get_file_content(cur_inst.srv_com, cur_inst.log)


class set_file_content(cs_base_class.server_com):
    def _call(self, cur_inst):
        filesys_tools.set_file_content(cur_inst.srv_com, cur_inst.log)


class get_dir_tree(cs_base_class.server_com):
    def _call(self, cur_inst):
        filesys_tools.get_dir_tree(cur_inst.srv_com, cur_inst.log)


class create_dir(cs_base_class.server_com):
    def _call(self, cur_inst):
        filesys_tools.create_dir(cur_inst.srv_com, cur_inst.log)


class remove_dir(cs_base_class.server_com):
    def _call(self, cur_inst):
        filesys_tools.remove_dir(cur_inst.srv_com, cur_inst.log)
