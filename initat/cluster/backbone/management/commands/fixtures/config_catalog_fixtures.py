# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for cluster-server """

from initat.cluster.backbone import factories


def get_sys_conf_cat():
    sys_cc = factories.ConfigCatalog(name="local", system_catalog=True)
    return sys_cc


class SysConfig(factories.Config):
    def __init__(self, *args, **kwargs):
        sys_cat = get_sys_conf_cat()
        factories.Config.__init__(self, *args, config_catalog=sys_cat, **kwargs)
