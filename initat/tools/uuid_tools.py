#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2010-2015 Andreas Lang-Nevyjel, init.at
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
""" uuid tools """

import os
import uuid

from initat.tools import config_store

OLD_UUID_NAME = "/etc/sysconfig/cluster/.cluster_device_uuid"
# name of datastore
DATASTORE_NAME = "icsw.device"


def get_uuid():
    if not config_store.ConfigStore.exists(DATASTORE_NAME):
        if os.path.isfile(UUID_NAME):
            uuid_content = file(UUID_NAME, "r").read().strip()
            try:
                the_uuid = uuid.UUID(uuid_content)
            except ValueError:
                # uuid is not readable, create new
                the_uuid = uuid.uuid4()
        else:
            the_uuid = uuid.uuid4()
        _ds = config_store.ConfigStore(DATASTORE_NAME)
        _ds["cluster.device.uuid"] = the_uuid.get_urn()
        _ds.write()
    return uuid.UUID(config_store.ConfigStore(DATASTORE_NAME)["cluster.device.uuid"])

if __name__ == "__main__":
    print(get_uuid())
