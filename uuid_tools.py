#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2010-2014 Andreas Lang-Nevyjel, init.at
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

UUID_NAME = "/etc/sysconfig/cluster/.cluster_device_uuid"

def get_uuid():
    write_uuid = False
    if os.path.isfile(UUID_NAME):
        uuid_content = file(UUID_NAME, "r").read().strip()
        try:
            the_uuid = uuid.UUID(uuid_content)
        except ValueError:
            # uuid is not readable, create new
            write_uuid = True
    else:
        write_uuid = True
    if write_uuid:
        # changed from uuid1 to uuid4 by ALN, 20120726
        the_uuid = uuid.uuid4()
        uuid_dir = os.path.dirname(UUID_NAME)
        if not os.path.isdir(uuid_dir):
            try:
                os.makedirs(uuid_dir)
            except:
                pass
        try:
            file(UUID_NAME, "w").write("{}\n".format(the_uuid.get_urn()))
        except IOError:
            print "Cannot write uuid to {}".format(UUID_NAME)
        else:
            pass
    return the_uuid

if __name__ == "__main__":
    print get_uuid()

