# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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

""" scan all apps in backbone for new ICSW rights """

import pprint
import time
from optparse import make_option

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand
from django.db.models import Q

from initat.cluster.backbone.models import csw_permission
from initat.tools import logging_tools


class Command(BaseCommand):
    help = ("Scan the installed models for new CSW permissions.")
    option_list = BaseCommand.option_list + (
        make_option(
            "--modify",
            action="store_true",
            default=False,
            help="Modify permissions instead of displaying them",
        ),
    )

    def handle(self, **options):
        if options.get("modify"):
            self.modify(**options)
        else:
            self.show(**options)

    def _get_perms(self):
        return csw_permission.objects.all().select_related(
            "content_type"
        ).order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        )

    def show(self, **opions):

        present_perms = self._get_perms()
        out_list = logging_tools.new_form_list()
        for perm in present_perms:
            out_list.append(
                [
                    logging_tools.form_entry(perm.content_type.app_label, header="App Label"),
                    logging_tools.form_entry(perm.content_type.model, header="Model"),
                    logging_tools.form_entry(perm.codename, header="Code"),
                    logging_tools.form_entry(perm.name, header="Info"),
                    logging_tools.form_entry_center("G/O" if perm.valid_for_object_level else "G", header="Scope"),
                    logging_tools.form_entry(perm.created.strftime("%Y-%m-%d %H:%M:%S"), header="Created"),
                    logging_tools.form_entry_right(perm.user_permission_set.all().count(), header="UserPerms"),
                    logging_tools.form_entry_right(perm.csw_object_permission_set.all().count(), header="UserObjPerms"),
                    logging_tools.form_entry_right(perm.group_permission_set.all().count(), header="GroupPerms"),
                    logging_tools.form_entry_right(perm.csw_object_permission_set.all().count(), header="GroupObjPerms"),
                ]
            )
        print unicode(out_list)

    def modify(self, **options):
        verbosity = int(options.get("verbosity"))

        excluded_apps = set()
        excluded_models = set()
        app_list = apps.get_app_configs()
        present_perms = self._get_perms()
        found_perms = set()
        found_perms_list = []
        full_dict = {
            (cur_perm.content_type.app_label, cur_perm.codename, cur_perm.content_type.model): cur_perm for cur_perm in present_perms
        }
        created = 0
        for app_config in app_list:
            models = app_config.get_models()
            for model in models:
                if model in excluded_models:
                    continue
                start_time = time.time()
                _local_created = 0
                errors = []
                if hasattr(model, "CSW_Meta") and hasattr(model.CSW_Meta, "permissions"):
                    app_label = model._meta.app_label
                    cur_ct = ContentType.objects.get_for_model(model)
                    model_name = cur_ct.model
                    # print app_label, cur_ct, dir(model._meta), model._meta.model_name
                    for code_name, name, valid_for_object_level in model.CSW_Meta.permissions:
                        # print "found", app_label, code_name
                        found_perms_list.append((app_label, code_name, cur_ct.model))
                        found_perms.add((app_label, code_name, model_name))
                        if (app_label, code_name, model_name) not in full_dict:
                            new_perm = csw_permission.objects.create(
                                codename=code_name,
                                name=name,
                                content_type=cur_ct,
                                valid_for_object_level=valid_for_object_level,
                            )
                            # p_dict[(new_perm.content_type.app_label, new_perm.codename, new_perm.content_type.model)] = new_perm
                            full_dict[(new_perm.content_type.app_label, new_perm.codename, new_perm.content_type.model)] = new_perm
                            _local_created += 1
                            print(
                                "Created '{}' for model {}".format(
                                    unicode(new_perm),
                                    cur_ct.model
                                )
                            )
                        else:
                            if valid_for_object_level != full_dict[(app_label, code_name, model_name)].valid_for_object_level:
                                print(
                                    "Change valid_for_object_level to {} for {}".format(
                                        unicode(valid_for_object_level),
                                        unicode(full_dict[(app_label, code_name, model_name)])
                                    )
                                )
                                full_dict[(app_label, code_name, model_name)].valid_for_object_level = valid_for_object_level
                                full_dict[(app_label, code_name, model_name)].save()
                if _local_created:
                    created += _local_created
                    print(
                        "creation of {:d} took {:7.2f} seconds".format(
                            _local_created,
                            time.time() - start_time
                        )
                    )
                    print(
                        "found {}".format(
                            logging_tools.get_plural("error", len(errors))
                        )
                    )
                    if verbosity > 1:
                        pprint.pprint(errors)
        dup_keys = {key for key in found_perms if found_perms_list.count(key) > 1}
        unique_keys = {key for key in found_perms}
        print("Permissions found: {:d}".format(len(unique_keys)))
        if dup_keys:
            print(
                "{} found, please fix models".format(
                    logging_tools.get_plural("duplicate key", len(dup_keys)),
                )
            )
            for dup_key in dup_keys:
                print(
                    "    {}: {:d}".format(
                        str(dup_key),
                        found_perms_list.count(dup_key),
                    )
                )
            raise(ImproperlyConfigured("CSW permissions not unique"))
        # find old permissions
        old_perms = set(full_dict.keys()) - found_perms
        deleted = len(old_perms)
        if old_perms:
            print(
                "Removing {}: {}".format(
                    logging_tools.get_plural("old permission", len(old_perms)),
                    ", ".join(
                        sorted(
                            [
                                "{}.{}.{}".format(app_label, model_name, code_name) for app_label, code_name, model_name in sorted(old_perms)
                            ]
                        )
                    )
                )
            )
            for app_label, code_name, model_name in old_perms:
                csw_permission.objects.get(
                    Q(codename=code_name) &
                    Q(content_type__model=model_name)
                ).delete()

        if created or deleted:
            self.show(**options)
