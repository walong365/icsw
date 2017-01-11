#
# Copyright (C) 2001-2007,2010-2017 Andreas Lang-Nevyjel, init.at
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
""" uuid tools """



import os
import uuid

from initat.constants import CLUSTER_DIR
from initat.tools import config_store

# for simple C-progs
NEW_UUID_NAME = os.path.join(CLUSTER_DIR, "etc", ".cluster_device_uuid")

# name of datastore
DATASTORE_NAME = "icsw.device"


def get_uuid(renew=False):
    OLD_UUID_NAME = "/etc/sysconfig/cluster/.cluster_device_uuid"
    if not config_store.ConfigStore.exists(DATASTORE_NAME):
        if os.path.isfile(OLD_UUID_NAME):
            uuid_content = open(OLD_UUID_NAME, "r").read().strip()
            try:
                the_uuid = uuid.UUID(uuid_content)
            except ValueError:
                # uuid is not readable, create new
                the_uuid = uuid.uuid4()
            try:
                os.unlink(OLD_UUID_NAME)
            except (IOError, OSError):
                pass
        else:
            the_uuid = uuid.uuid4()
        _create_cs = True
    elif renew:
        the_uuid = uuid.uuid4()
        _create_cs = True
    else:
        _create_cs = False
    if _create_cs:
        _cs = config_store.ConfigStore(DATASTORE_NAME, access_mode=config_store.AccessModeEnum.GLOBAL)
        _cs["cluster.device.uuid"] = the_uuid.get_urn()
        _cs.write()
    the_uuid = uuid.UUID(
        config_store.ConfigStore(
            DATASTORE_NAME,
            quiet=True,
            access_mode=config_store.AccessModeEnum.GLOBAL,
            fix_access_mode=True,
        )["cluster.device.uuid"]
    )
    _write = False
    if not os.path.exists(NEW_UUID_NAME):
        _write = True
    else:
        old_uuid = open(NEW_UUID_NAME, "r").read().strip()
        if old_uuid != the_uuid.get_urn():
            _write = True
    if _write:
        try:
            open(NEW_UUID_NAME, "w").write("{}\n".format(the_uuid.get_urn()))
        except IOError:
            pass
    return the_uuid

if __name__ == "__main__":
    print(get_uuid())
