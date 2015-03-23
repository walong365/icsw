# -*- coding: utf-8 -*-

from pynag.Model import Host, ObjectFetcher

from initat.cluster.backbone.models import (
    peer_information, mon_check_command, mon_service_templ
)

from .transformations import transform_host
from .utils import connect_objects, get_connected_object


def create_devices():
    devices = []
    for host in Host.objects.all:
        devices.append(transform_host(host))
    return devices


def create_peering_information(devices):
    for device in devices:
        child = get_connected_object(device)

        # Note: A bug in pynag in ObjectFetcher.reload_cache prevents us
        # from using get_effective_network_parents() - we do it by hand instead.
        parents = child["parents"]
        if parents:
            parents = [i.strip() for i in parents.split(",")]
            parents = [Host.objects.filter(host_name=i)[0] for i in parents]
            parents = [get_connected_object(i) for i in parents]

            for parent in parents:
                peer_information.objects.get_or_create(
                    s_netdevice=device.netdevice_set.get(),
                    d_netdevice=parent.netdevice_set.get(),
                )


def unify_templates(devices):
    """
        Find all mon_check_commands and their mon_service_templ objects
        associated with a host.

        Find the biggest group of service templates that are equal, disassociate
        them from the checks and put a unified mon_service_templ on mon_device_templ.

        Find service templates that are not used any more.
    """
    print devices
    print "#" * 20
    for i in mon_service_templ.objects.all():
        print i, i.mon_check_command_set.all()
    print "#" * 20
    for command in mon_check_command.objects.all():
        print "c", command
        print "mst", command.mon_service_templ
