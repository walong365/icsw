# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger (mallinger@init.at)
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
import os


class Parser(object):
    def link(self, sub_parser, **kwargs):
        if not kwargs["server_mode"]:
            return
        from initat.cluster.backbone.available_licenses import LicenseEnum

        lic_parser = sub_parser.add_parser("license", help="license utility")
        lic_sub_parser = lic_parser.add_subparsers()

        show_cluster_id_parser = lic_sub_parser.add_parser("show_cluster_id", help="Show Cluster ID")
        show_cluster_id_parser.set_defaults(subcom="show_cluster_id", execute=self._execute)
        show_cluster_id_parser.add_argument(
            "--without-fp",
            default=False,
            action="store_true",
            help="do not display Server Fingerprint [%(default)s]",
        )
        show_cluster_id_parser.add_argument(
            "--raw",
            default=False,
            action="store_true",
            help="enable raw mode (only data will be printed) [%(default)s]",
        )

        show_license_parser = lic_sub_parser.add_parser("show_license_info", help="Show License info")
        show_license_parser.set_defaults(subcom="show_license_info", execute=self._execute)
        reg_cluster_parser = lic_sub_parser.add_parser(
            "register_cluster",
            help="register your cluster at init.at and obtain a license file"
        )
        reg_cluster_parser.set_defaults(subcom="register_cluster", execute=self._execute)
        reg_cluster_parser.add_argument("-u", "--user", dest='user', required=True, help="your icsw user name")
        reg_cluster_parser.add_argument("-p", "--password", dest='password', required=True, help="your icsw password")
        reg_cluster_parser.add_argument(
            "-n",
            "--cluster-name",
            dest='cluster_name',
            default="",
            help="cluster name as provided by init.at"
        )

        self._add_ovum_parser(lic_sub_parser)
        install_cluster_parser = lic_sub_parser.add_parser(
            "install_license",
            help="install already downloaded license file"
        )
        install_cluster_parser.set_defaults(subcom="install_license", execute=self._execute)
        install_cluster_parser.add_argument("licensefile", help="License file")

        def add_lock_arguments(p):
            p.add_argument("-l", "--license", dest="license", help="the license to lock usage of", required=True,
                           choices=[i.name for i in LicenseEnum])
            p.add_argument("-d", "--device", dest="device", help="device name")
            p.add_argument("-s", "--service", dest="service", help="service (=check command)")
            p.add_argument("-u", "--user", dest="user", help="user name")
            p.add_argument("-e", "--ext-license", dest="ext_license", help="service (=check command)")
        lock_parser = lic_sub_parser.add_parser("lock", help="lock entities from using a license")
        lock_parser.set_defaults(subcom="lock", execute=self._execute)
        add_lock_arguments(lock_parser)

        unlock_parser = lic_sub_parser.add_parser("unlock", help="unlock entities from using a license")
        unlock_parser.set_defaults(subcom="unlock", execute=self._execute)
        add_lock_arguments(unlock_parser)

        show_lock_parser = lic_sub_parser.add_parser("show_locks", help="show current locks")
        show_lock_parser.set_defaults(subcom="show_locks", execute=self._execute)

    def _add_ovum_parser(self, sub_parser):
        _act = sub_parser.add_parser("ova", help="ova handling")
        _act.set_defaults(subcom="ova", execute=self._execute)
        _act.add_argument("--show", default=False, action="store_true", help="show ova information [%(default)s]")
        _act.add_argument("--init", default=False, action="store_true", help="init basic ova structures [%(default)s]")

    def _execute(self, opt_ns):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

        import django
        django.setup()
        if opt_ns.subcom in ["lock_entity", "unlock_entity", "show_locked_entities"]:
            from .license_lock import main
            main(opt_ns)
        else:
            from .main import main
            main(opt_ns)
