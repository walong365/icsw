#!/usr/bin/python3-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

import urllib.request
import urllib.error
import urllib.parse
import pickle
import re


PACKAGE_NAME_PATTERN = re.compile(r".*>(.*)<.*")
ICSW_SERVER_PATTERN = re.compile(r"icsw-server.3.0.(\d*).*")

REPOS = [
    ("opensuse-leap-42-1", "http://www.initat.org/cluster/RPMs/suse_42.1/icsw-devel/"),
    ("opensuse-leap-42-2", "http://www.initat.org/cluster/RPMs/suse_42.2/icsw-devel/"),
    ("debian-jessie", "http://www.initat.org/cluster/debs/debian_jessie/icsw-devel/"),
    ("centos-7", "http://www.initat.org/cluster/RPMs/rhel_7.0/icsw-devel/")
]


def get_current_release_dict():
    current_release_dict = {}

    for distro_name, repo_uri in REPOS:
        data = urllib.request.urlopen(repo_uri).read().decode()
        current_release_dict[distro_name] = 0

        for line in data.split("\n"):
            match = PACKAGE_NAME_PATTERN.match(line)
            if match and match.group(1):
                match = ICSW_SERVER_PATTERN.match(match.group(1))
                if match:
                    release_number = int(match.group(1))

                    if distro_name in current_release_dict:
                        current_release_dict[distro_name] = max(current_release_dict[distro_name], release_number)
                    else:
                        current_release_dict[distro_name] = release_number

    return current_release_dict


def check_for_new_packages():
    repos = [
        ("opensuse-leap-42-1", "http://www.initat.org/cluster/RPMs/suse_42.1/icsw-devel/"),
        ("opensuse-leap-42-2", "http://www.initat.org/cluster/RPMs/suse_42.2/icsw-devel/"),
        ("debian-jessie", "http://www.initat.org/cluster/debs/debian_jessie/icsw-devel/"),
        ("centos-7", "http://www.initat.org/cluster/RPMs/rhel_7.0/icsw-devel/")
    ]

    try:
        f = open("release.db", "rb")
        checked_release_dict = pickle.load(f)
    except IOError:
        checked_release_dict = {}
        for distro_name, repo_uri in repos:
            checked_release_dict[distro_name] = 0

    new_packages_found = {}
    current_release_dict = get_current_release_dict()

    for distro_name, repo_uri in REPOS:
        if current_release_dict[distro_name] > checked_release_dict[distro_name]:
            new_packages_found[distro_name] = current_release_dict[distro_name]

        checked_release_dict[distro_name] = current_release_dict[distro_name]

    with open("release.db", "wb") as f:
        pickle.dump(checked_release_dict, f)

    return new_packages_found

if __name__ == "__main__":
    print((check_for_new_packages()))
