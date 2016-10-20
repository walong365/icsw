#!/usr/bin/python-init -Ot

import urllib2
import pickle
import re

PACKAGE_NAME_PATTERN = re.compile(r".*>(.*)<.*")
ICSW_SERVER_PATTERN = re.compile(r"icsw-server.3.0.(\d*).*")

def check_for_new_packages():
    repos = [
        ("suse_42_1", "http://www.initat.org/cluster/RPMs/suse_42.1/icsw-devel/"),
        ("debian_jessie", "http://www.initat.org/cluster/debs/debian_jessie/icsw-devel/"),
        ("rhel_7_0", "http://www.initat.org/cluster/RPMs/rhel_7.0/icsw-devel/")
    ]

    try:
        f = open("release.db", "rb")
        checked_release_dict = pickle.load(f)
    except:
        checked_release_dict = {}
        for distro_name, repo_uri in repos:
            checked_release_dict[distro_name] = 0

    current_release_dict = {}

    new_packages = {}

    for distro_name, repo_uri in repos:
        data = urllib2.urlopen(repo_uri).read()

        for line in data.split("\n"):
            match = PACKAGE_NAME_PATTERN.match(line)
            if match and match.group(1):
                match = ICSW_SERVER_PATTERN.match(match.group(1))
                if match:
                    release_number = int(match.group(1))

                    if distro_name not in current_release_dict:
                        current_release_dict[distro_name] = release_number
                    current_release_dict[distro_name] = max(release_number, current_release_dict[distro_name])

        if current_release_dict[distro_name] > checked_release_dict[distro_name]:
            checked_release_dict[distro_name] = current_release_dict[distro_name]
            new_packages[distro_name] = current_release_dict[distro_name]

    with open("release.db", "wb") as f:
        pickle.dump(checked_release_dict, f)

    return new_packages


if __name__ == "__main__":
    print(check_for_new_packages())
