# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" show all current ICSW permissions """

import pprint
import time

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand
from django.db.models import Q

from initat.cluster.backbone.models import csw_permission
from initat.tools import logging_tools


class Command(BaseCommand):
    help = ("Display the current ICSW permissions",)

    def handle(self, *app_labels, **options):
        out_list = logging_tools.new_form_list()
        for perm in csw_permission.objects.all().prefetch_related(
            "content_type",
        ):
            out_list.append(
                [
                    logging_tools.form_entry(
                        perm.content_type.app_label,
                        header="App",
                    ),
                    logging_tools.form_entry(
                        perm.content_type.model,
                        header="Model",
                    ),
                    logging_tools.form_entry(
                        perm.codename,
                        header="Code",
                    ),
                    logging_tools.form_entry(
                        perm.name,
                        header="Info",
                    ),
                    logging_tools.form_entry(
                        "G/O" if perm.valid_for_object_level else "G",
                        header="Scope",
                    ),
                ]
            )
        print(
            "{} defined:".format(
                logging_tools.get_plural("Permission", len(out_list)),
            )
        )
        print unicode(out_list)
