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
import sys

from initat.cluster.backbone.models import device, device_variable
from initat.cluster.backbone.models.rms import ext_license
from initat.cluster.backbone.models.monitoring import mon_check_command
from initat.cluster.backbone.models.user import user
from initat.cluster.backbone.models.license import LicenseLockListDeviceService, LicenseUsageDeviceService, \
    LicenseLockListUser, LicenseUsageUser, LicenseLockListExtLicense, LicenseUsageExtLicense


__all__ = [
    "lock_entity",
    "unlock_entity",
    "show_locked_entities",
    "show_cluster_id",
]


def lock_entity(opts):
    def lock_device(device_name):
        if opts.service is not None:
            return  # let service handle both together
        try:
            dev_db = device.objects.get(name=device_name)
        except device.DoesNotExist:
            raise RuntimeError("No such device: {}".format(device_name))
        else:
            LicenseLockListDeviceService.objects.get_or_create(license=opts.license, device=dev_db,
                                                               service=None)
            LicenseUsageDeviceService.objects.filter(license=opts.license, device=dev_db,
                                                     service=None).delete()
            print("Device {} is locked from using license {}.".format(device_name, opts.license))

    def lock_service(service_name):
        try:
            service_db = mon_check_command.objects.get(name=service_name)
        except device.DoesNotExist:
            raise RuntimeError("No such service: {}".format(service_name))
        else:
            if opts.device:
                try:
                    dev_db = device.objects.get(name=opts.device)
                except device.DoesNotExist:
                    raise RuntimeError("No such device: {}".format(opts.device))
            else:
                dev_db = None

            LicenseLockListDeviceService.objects.get_or_create(license=opts.license, service=service_db,
                                                               device=dev_db)
            LicenseUsageDeviceService.objects.filter(license=opts.license, service=service_db,
                                                     device=dev_db).delete()
            dev_str = "on device {} ".format(dev_db) if dev_db is not None else ""
            print("Service {} {}is locked from using license {}.".format(service_name, dev_str, opts.license))

    def lock_user(user_name):
        try:
            user_db = user.objects.get(login=user_name)
        except device.DoesNotExist:
            raise RuntimeError("No such user: {}".format(user_name))
        else:
            LicenseLockListUser.objects.get_or_create(license=opts.license, user=user_db)
            LicenseUsageUser.objects.filter(license=opts.license, user=user_db).delete()
            print("User {} is locked from using license {}.".format(user_db, opts.license))

    def lock_ext_license(ext_license_name):
        try:
            ext_license_db = ext_license.objects.get(name=ext_license_name)
        except device.DoesNotExist:
            raise RuntimeError("No such external license: {}".format(ext_license_name))
        else:
            LicenseLockListExtLicense.objects.get_or_create(license=opts.license, ext_license=ext_license)
            LicenseUsageExtLicense.objects.filter(license=opts.license, ext_license=ext_license_db).delete()
            print("External license {} is locked from using license {}.".format(ext_license_db, opts.license))

    some_value_present = False
    for param, handler in [('device', lock_device), ('user', lock_user), ('ext_license', lock_ext_license),
                           ('service', lock_service)]:
        value = getattr(opts, param, None)
        if value is not None:
            some_value_present = True
            handler(value)

    if not some_value_present:
        raise RuntimeError("Please specify some entity to lock.")

    # TODO: recheck violations?
    # make md config server recheck
    # srv_com = server_command.srv_command(command="check_license")
    # contact_server(request, "md-config", srv_com, timeout=60, log_error=True, log_result=False)


def unlock_entity(opts):
    def unlock_device(device_name):
        if opts.service is not None:
            return  # let service handle both together
        try:
            dev_db = device.objects.get(name=device_name)
        except device.DoesNotExist:
            raise RuntimeError("No such device: {}".format(device_name))
        else:
            LicenseLockListDeviceService.objects.filter(license=opts.license, device=dev_db, service=None).delete()
            print("Device {} is unlocked from using license {}.".format(device_name, opts.license))

    def unlock_service(service_name):
        try:
            service_db = mon_check_command.objects.get(name=service_name)
        except device.DoesNotExist:
            raise RuntimeError("No such service: {}".format(service_name))
        else:
            if opts.device:
                try:
                    dev_db = device.objects.get(name=opts.device)
                except device.DoesNotExist:
                    raise RuntimeError("No such device: {}".format(opts.device))
            else:
                dev_db = None

            LicenseLockListDeviceService.objects.filter(license=opts.license, service=service_db,
                                                        device=dev_db).delete()
            dev_str = "on device {} ".format(dev_db) if dev_db is not None else ""
            print("Service {} {}is unlocked from using license {}.".format(service_name, dev_str, opts.license))

    def unlock_user(user_name):
        try:
            user_db = user.objects.get(login=user_name)
        except device.DoesNotExist:
            raise RuntimeError("No such user: {}".format(user_name))
        else:
            LicenseLockListUser.objects.filter(license=opts.license, user=user_db).delete()
            print("User {} is unlocked from using license {}.".format(user_db, opts.license))

    def unlock_ext_license(ext_license_name):
        try:
            ext_license_db = ext_license.objects.get(name=ext_license_name)
        except device.DoesNotExist:
            raise RuntimeError("No such external license: {}".format(ext_license_name))
        else:
            LicenseLockListExtLicense.objects.filter(license=opts.license, ext_license=ext_license).delete()
            print("External license {} is locked from using license {}.".format(ext_license_db, opts.license))

    some_value_present = False
    for param, handler in [('device', unlock_device), ('user', unlock_user), ('ext_license', unlock_ext_license),
                           ('service', unlock_service)]:
        value = getattr(opts, param)
        if value is not None:
            some_value_present = True
            handler(value)

    if not some_value_present:
        print ("Please specify some entity to lock.")
        sys.exit(1)


def show_locked_entities(opts):
    if LicenseLockListDeviceService.objects.exists():
        print "Locked devices and services:"
        for dev_serv in LicenseLockListDeviceService.objects.all():
            if dev_serv.device is not None and dev_serv.service is not None:
                print("    {} on {} ({})".format(dev_serv.service, dev_serv.device, dev_serv.license))
            elif dev_serv.device is not None:
                print("    {} ({})".format(dev_serv.device, dev_serv.license))
            elif dev_serv.service is not None:
                print("    {} ({})".format(dev_serv.service, dev_serv.license))

    if LicenseLockListUser.objects.exists():
        print "Locked users:"
        for u in LicenseLockListUser.objects.all():
            print("    {} ({})".format(u.user, u.license))

    if LicenseLockListExtLicense.objects.exists():
        print "Locked external licenses:"
        for ext_lic in LicenseLockListExtLicense.objects.all():
            print("    {} ({})".format(ext_lic.ext_license, ext_lic.license))


def show_cluster_id(opts):
    print device_variable.objects.get_cluster_id()
