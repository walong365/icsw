#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" service related tools  """

import os

from initat.tools import net_tools, server_command


def query_local_meta_server(inst_xml, command, services=None, days_to_consider=1, db_limit=100):
    srv_com = server_command.srv_command(
        command="state{}".format(command),
    )
    if services:
        srv_com["services"] = ",".join(services)
    srv_com["days_to_consider"] = "{:d}".format(days_to_consider)
    srv_com["db_limit"] = "{:d}".format(db_limit)
    return net_tools.ZMQConnection(
        "icsw_state_{:d}".format(os.getpid())
    ).add_connection(
        "tcp://localhost:{:d}".format(inst_xml.get_port_dict("meta-server", command=True)),
        srv_com,
    )
