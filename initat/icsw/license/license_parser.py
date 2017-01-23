# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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
        return self._add_license_parser(sub_parser)

    def _add_license_parser(self, sub_parser):

        lic_parser = sub_parser.add_parser("license", help="license utility")
        lic_parser.set_defaults(subcom="show-cluster-id", execute=self._execute, raw=False, without_fp=True)
        lic_sub_parser = lic_parser.add_subparsers()

        show_cluster_id_parser = lic_sub_parser.add_parser("show-cluster-id", help="Show Cluster ID")
        show_cluster_id_parser.set_defaults(subcom="show-cluster-id", execute=self._execute)
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

        show_license_parser = lic_sub_parser.add_parser("show-license-info", help="Show License info")
        show_license_parser.set_defaults(subcom="show-license-info", execute=self._execute)
        show_license_parser.add_argument("--raw", default=False, action="store_true", help="show raw info [%(default)s]")
        reg_cluster_parser = lic_sub_parser.add_parser(
            "register-cluster",
            help="register your cluster at init.at and obtain a license file"
        )
        reg_cluster_parser.set_defaults(subcom="register-cluster", execute=self._execute)
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
            "install-license-file",
            help="install already downloaded license file"
        )
        install_cluster_parser.set_defaults(subcom="install-license-file", execute=self._execute)
        install_cluster_parser.add_argument("licensefile", help="License file")
        raw_list_parser = lic_sub_parser.add_parser("raw-license-info", help="Show raw License data")
        raw_list_parser.set_defaults(subcom="raw-license-info", execute=self._execute)
        raw_list_parser.add_argument("--mark-error", default=False, action="store_true", help="Mark all LicenseFiles with error as invalid [%(default)s]")
        raw_list_parser.add_argument("--unmark-all", default=False, action="store_true", help="Unmark all LicenseFiles [%(default)s]")
        raw_list_parser.add_argument("--only-valid", default=False, action="store_true", help="Show only valid licenses [%(default)s]")

    def _add_ovum_parser(self, sub_parser):
        _act = sub_parser.add_parser("ova", help="ova handling")
        _act.set_defaults(subcom="ova", execute=self._execute)
        _act.add_argument("--show", default=False, action="store_true", help="show ova information [%(default)s]")
        _act.add_argument("--init", default=False, action="store_true", help="init basic ova structures [%(default)s]")

    def _execute(self, opt_ns):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

        import django
        django.setup()
        from .main import main
        main(opt_ns)
