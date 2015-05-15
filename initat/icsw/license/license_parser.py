#!/usr/bin/python-init -OtB
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger (mallinger@init.at)
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of icsw
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
import os

# noinspection PyUnresolvedReferences
from lxml import etree
from initat.icsw.license.license_lock import lock_entity, unlock_entity, show_locked_entities, show_cluster_id
from initat.cluster.backbone.available_licenses import LicenseEnum
from initat.icsw.license.register_cluster import register_cluster


class Parser(object):
    def link(self, sub_parser):
        def run_with_db(fun):
            def decorated_fun(*args, **kwargs):
                # don't do this in global scope, we might not have a database on this machine
                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

                import django
                django.setup()

                fun(*args, **kwargs)
            return decorated_fun

        lic_parser = sub_parser.add_parser("license", help="license utility")
        lic_sub_parser = lic_parser.add_subparsers()

        show_cluster_id_parser = lic_sub_parser.add_parser("show_cluster_id")
        show_cluster_id_parser.set_defaults(execute=run_with_db(show_cluster_id))

        reg_cluster_parser = lic_sub_parser.add_parser(
            "register_cluster",
            help="register your cluster at init.at and obtain a license file"
        )
        reg_cluster_parser.set_defaults(execute=run_with_db(register_cluster))
        reg_cluster_parser.add_argument("-u", "--user", dest='user', required=True, help="your icsw user name")
        reg_cluster_parser.add_argument("-p", "--password", dest='password', required=True, help="your icsw password")
        reg_cluster_parser.add_argument("-n", "--cluster-name", dest='cluster_name', required=True,
                                        help="cluster name as provided by init.at")
        reg_cluster_parser.add_argument("-i", "--cluster-id", dest='cluster_id',
                                        help="will use local one if not specified)")

        def add_lock_arguments(p):
            p.add_argument("-l", "--license", dest="license", help="the license to lock usage of", required=True,
                           choices=[i.name for i in LicenseEnum])
            p.add_argument("-d", "--device", dest="device", help="device name")
            p.add_argument("-s", "--service", dest="service", help="service (=check command)")
            p.add_argument("-u", "--user", dest="user", help="user name")
            p.add_argument("-e", "--ext-license", dest="ext_license", help="service (=check command)")
        lock_parser = lic_sub_parser.add_parser("lock", help="lock entities from using a license")
        lock_parser.set_defaults(execute=run_with_db(lock_entity))
        add_lock_arguments(lock_parser)

        unlock_parser = lic_sub_parser.add_parser("unlock", help="unlock entities from using a license")
        unlock_parser.set_defaults(execute=run_with_db(unlock_entity))
        add_lock_arguments(unlock_parser)

        show_lock_parser = lic_sub_parser.add_parser("show_locks")
        show_lock_parser.set_defaults(execute=run_with_db(show_locked_entities))
