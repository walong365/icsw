# -*- coding: utf-8 -*-

import argparse

from pynag import Model
from pynag.Model import Host

import django
from django.db.transaction import atomic

from .operations import create_devices, create_peering_information

from initat.cluster.backbone.models import *


@atomic
def main(config_file):
    # Test cleanup:
    mon_period.objects.all().delete()
    device.objects.all().delete()
    device_group.objects.create(name="cdg")
    mon_check_command.objects.all().delete()
    mon_service_templ.objects.all().delete()

    Model.cfg_file = config_file

    devices = create_devices()
    create_peering_information(devices)


if __name__ == "__main__":
    django.setup()
    parser = argparse.ArgumentParser(
        description="Migrate existing icinga/nagios configs to Noctua"
    )
    parser.add_argument("config_file", help="Main icinga/nagios config file")
    args = parser.parse_args()
    main(args.config_file)
