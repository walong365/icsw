#!/usr/bin/env python
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of icsw
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


import logging

import platform
import os
import os.path
import subprocess
import sys

log = logging.getLogger("install_icsw")

try:
    input = raw_input  # python 2/3
except NameError:
    pass


class OSHandler(object):
    def __init__(self, opts):
        self.opts = opts

    @classmethod
    def get_local_os(cls, opts):
        """
        :rtype: OSHandler
        """
        # format as in platform module
        # for ubuntu, ubuntu is returned anyway, so supported dists does not appear to be strict
        supported_dists = ("SuSE", "centos", "debian", "ubuntu", "univention")
        distro = platform.linux_distribution(supported_dists=supported_dists,
                                             full_distribution_name=False)[0]
	distro = distro.lower().strip("\"")

        if distro == "suse":
            return SuseHandler(opts)
        elif distro == "centos":
            return CentosHandler(opts)
        elif distro in ("debian", "ubuntu", "univention"):
            return AptgetHandler(opts)
        else:
            raise RuntimeError(
                "This install script does not support your platform: {p}\n".format(p=platform.linux_distribution()[0]) +
                "Supported platforms are: {s}".format(s=supported_dists)
            )

    def add_repos(self):
        raise NotImplementedError()

    def install_icsw(self):
        raise NotImplementedError()

    def process_command(self, cmd):
        if self.opts.show_commands:
            print(" ".join(cmd))
            return 0
        else:
            print("Running:", " ".join(cmd))
            ret = subprocess.call(cmd)
            if ret != 0:
                raise RuntimeError("Failed to execute command: {c}".format(c=" ".join(cmd)))
            return ret

    def create_file(self, file_path, file_content):
        if self.opts.show_commands:
            print("Create file {f} with content:".format(f=file_path))
            print(file_content)
        else:
            with open(file_path, 'w') as repo_file:
                repo_file.write(file_content)


class SuseHandler(OSHandler):
    # version must be like "13.1"
    # CLUSTER_DEVEL_URL = "http://{user}:{password}@www.initat.org/cluster/RPMs/suse_{version}/cluster-devel"
    # EXTRA_URL = "http://{user}:{password}@www.initat.org/cluster/RPMs/suse_{version}/extra"
    ICSW_2_5_URL = "http://{user}:{password}@www.initat.org/cluster/RPMs/suse_{version}/{cluster_version}"

    def add_repos(self):
        suse_version = platform.linux_distribution()[1]
        expansions = {
            'user': self.opts.user,
            'password': self.opts.password,
            'version': suse_version,
            'cluster_version': self.opts.cluster_version,
        }
        repos = (
            # ("initat_cluster_devel", self.__class__.CLUSTER_DEVEL_URL.format(**expansions)),
            # ("initat_extra", self.__class__.EXTRA_URL.format(**expansions)),
            #("{cluster_version}".format(cluster_version=self.opts.cluster_version), self.__class__.ICSW_2_5_URL.format(**expansions)),
            (self.opts.cluster_version, self.__class__.ICSW_2_5_URL.format(**expansions)),
        )

       # for item in repos:
       #     cluster_version = item[0]
       #     repo_url = item[1]

        for cluster_version, repo_url in repos:
            repo_list = subprocess.check_output(("zypper", "repos", "--uri"))
            if cluster_version not in str(repo_list):
                command = ("zypper", "addrepo", "--refresh", "--no-gpgcheck", repo_url, cluster_version)
                self.process_command(command)
            else:
                log.info("Repo {r} already installed".format(r=cluster_version))

    def install_icsw(self):
        commands = [
            ("zypper", "refresh"),
            ("zypper", "--non-interactive", "install", "icsw-server"),
        ]

        for cmd in commands:
            self.process_command(cmd)


class CentosHandler(OSHandler):
    def add_repos(self):
        version = platform.linux_distribution()[1].lower()[0]
        if version == '6':
            version = "6.2"
        elif version == '7':
            version = "7.0"
        else:
            raise RuntimeError("Unsupported Centos version: {v}\n".format(v=platform.linux_distribution()) +
                               "Supported versions are 6 and 7.")

        expansions = {
            'user': self.opts.user,
            'password': self.opts.password,
            'version': version,
            'cluster_version': self.opts.cluster_version,
            }

        repos = (
            # (
            #     "initat_cluster_devel",
            #     "http://{user}:{password}@www.initat.org/cluster/RPMs/rhel_{version}/cluster-devel".format(**expansions)
            # ),
            # (
            #     "initat_extra",
            #     "http://{user}:{password}@www.initat.org/cluster/RPMs/rhel_{version}/extra".format(**expansions)
            # )
            (
                "initat_{cluster_version}".format(**expansions),
                "http://{user}:{password}@www.initat.org/cluster/RPMs/rhel_{version}/{cluster_version}".format(**expansions)
            ),
        )

        repo_template = """[{repo_name}]
name={repo_name}
enabled=1
autorefresh=1
baseurl={repo_url}
type=rpm-md
"""
        for repo_name, repo_url in repos:
            full_path = os.path.join("/etc/yum.repos.d", "{0}.repo".format(repo_name))
            if not os.path.exists(full_path):
                self.create_file(full_path, repo_template.format(repo_name=repo_name, repo_url=repo_url))
            else:
                log.info("Repo {r} already installed".format(r=repo_name))

    def install_icsw(self):
        self.process_command(("yum", "--assumeyes", "--nogpgcheck", "install", "icsw-server"))


class AptgetHandler(OSHandler):

    def add_repos(self):
        distro = platform.linux_distribution()[0].lower()
        distro = distro.lower().strip("\"")
        expansions = {
            'user': self.opts.user,
            'password': self.opts.password,
            'cluster_version': self.opts.cluster_version,
        }
        if distro == "ubuntu":
            # we only support 12.04 explicitly as of now
            repos = (
                (
                    "initat_{cluster_version}.list".format(**expansions),
                    "deb http://{user}:{password}@www.initat.org/cluster/DEBs/ubuntu_12.04/{cluster_version} precise main\n"
                    .format(**expansions)
                ),
            )
        elif distro == "debian" or distro == "univention":
            debian_version = platform.linux_distribution()[1].strip("\"")
            if debian_version.startswith("6"):
                debian_release = "squeeze"
            elif debian_version.startswith("7"):
                debian_release = "wheezy"
            elif debian_version.startswith("4") and distro == "univention":
                debian_release = "wheezy"
            elif debian_version.startswith("8"):
                debian_release = "jessie"
            else:
                raise RuntimeError("Unsupported debian version: {v}.\n".format(v=platform.linux_distribution()) +
                                   "Currently squeeze and wheezy are supported.")
            repos = (
                (
                    "initat_{cluster_version}.list".format(**expansions),
                    "deb http://{user}:{password}@www.initat.org/cluster/DEBs/debian_{rel}/{cluster_version} {rel} main\n"
                    .format(rel=debian_release, **expansions)
                ),
            )
        else:
            raise RuntimeError("Unsupported debian platform: {v}.\n".format(v=platform.linux_distribution()))

        for repo_file_name, file_content in repos:
            full_repo_file_path = os.path.join("/etc/apt/sources.list.d", repo_file_name)
            if not os.path.exists(full_repo_file_path):
                self.create_file(full_repo_file_path, file_content)
            else:
                log.info("File {f} already exists.".format(f=full_repo_file_path))

    def install_icsw(self):
        self.process_command(("apt-get", "update"))
        self.process_command(("apt-get", "--yes", "--allow-unauthenticated", "install", "icsw-server"))


def parse_args():
    try:
        import argparse
        parser = argparse.ArgumentParser(prog="install_icsw.py")
        parser.add_argument("-s", "--show-commands", dest="show_commands", action="store_true",
                            help="only show commands without actually executing them")
        parser.add_argument("-u", "--user", dest='user', required=True, help="your icsw user name")
        parser.add_argument("-p", "--password", dest='password', required=True, help="your icsw password")
        parser.add_argument("-n", "--cluster-name", dest='cluster_name', required=True,
                            help="cluster name as provided by init.at")
        parser.add_argument("-v", "--cluster-version", dest='cluster_version', required=True,
                            help="choose the version to install, either icsw-2.5 or icsw-devel")
        parser.add_argument( "--assume-yes", dest='assume_yes', action="store_true",
                            help="Don't ask user to confirm install")
        parser.add_argument( "--do-not-config", dest='do_not_config', action="store_true",
                    help="Do also a base configuration of database and license file")
        opts = parser.parse_args()
    except ImportError:
        import optparse
        parser = optparse.OptionParser()
        parser.add_option("-s", "--show-commands", dest="show_commands", action="store_true",
                          help="only show commands without actually executing them")
        parser.add_option("-u", "--user", dest='user', help="your icsw user name")
        parser.add_option("-p", "--password", dest='password', help="your icsw password")
        parser.add_option("-n", "--cluster-name", dest='cluster_name',
                          help="cluster name as provided by init.at")
        parser.add_option("-v", "--cluster-version", dest='cluster_version',
                            help="choose the version to install, either 2.5 or devel")
        parser.add_option("-y", "--assume-yes", dest='assume_yes', action="store_true",
                            help="Don't ask user to confirm install")
        parser.add_option("--do-not-config", dest='do_not_config', action="store_true",
                    help="Do also a base configuration of database and license file")
        # emulate required
        opts, _ = parser.parse_args()
        if opts.user is None:
            raise optparse.OptParseError("argument -u/--user is required")
        if opts.password is None:
            raise optparse.OptParseError("argument -p/--password is required")
        if opts.cluster_name is None:
            raise optparse.OptParseError("argument -n/--cluster-name is required")
        if opts.cluster_version is None:
            raise optparse.OptParseError("argument -v/--cluster-version is required")

    return opts


def main():

    logging.basicConfig(level=logging.DEBUG)

    opts = parse_args()

    if not opts.show_commands and not opts.assume_yes:
        answer = eval(input("This script will add repositories and install packages using your package management. " +
                       "Continue? (y/n) "))
        if answer.lower() != "y":
            print("Exiting.")
            sys.exit(0)

    if opts.show_commands:
        print("The following commands need to be executed:")

    local_os = OSHandler.get_local_os(opts)

    log.debug("Adding repos")
    local_os.add_repos()

    log.debug("Installing packages")
    local_os.install_icsw()

    if not opts.do_not_config:
        log.debug("Setting up database")
        local_os.process_command(
            (
                "/opt/cluster/sbin/icsw",
                "setup",
            )
        )

        log.debug("Installing license file")
        local_os.process_command(
            (
                "/opt/cluster/sbin/icsw",
                "license",
                "register_cluster",
                "--user", opts.user,
                "--password", opts.password,
                "--cluster-name", opts.cluster_name,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Exiting due to error: {}".format(e))
        sys.exit(1)
