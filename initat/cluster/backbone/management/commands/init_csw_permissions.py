# -*- coding: utf-8 -*-
"""
scan all apps in backbone for new CSW rights
"""

from optparse import make_option
import pprint
import time

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Q
from django.utils.datastructures import SortedDict

from initat.cluster.backbone.models import csw_permission
from initat.tools import logging_tools


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--database',
            action='store',
            dest='database',
            default=DEFAULT_DB_ALIAS,
            help='Nominates a specific database to dump '
            'fixtures from. Defaults to the "default" database.'
        ),
        make_option(
            '-e',
            '--exclude',
            dest='exclude',
            action='append',
            default=[],
            help='An appname or appname.ModelName to exclude (use multiple '
            '--exclude to exclude multiple apps/models).'
        ),
    )
    help = ("Scan the installed models for new CSW permissions.")
    args = '[appname appname.ModelName ...]'

    def handle(self, *app_labels, **options):
        excludes = options.get('exclude')
        verbosity = int(options.get("verbosity"))

        excluded_apps = set()
        excluded_models = set()
        for exclude in excludes:
            if '.' in exclude:
                app_label, model_name = exclude.split('.', 1)
                model_obj = apps.get_model(app_label, model_name)
                if not model_obj:
                    raise CommandError('Unknown model in excludes: {}'.format(exclude))
                excluded_models.add(model_obj)
            else:
                try:
                    app_obj = apps.get_app(exclude)
                    excluded_apps.add(app_obj)
                except ImproperlyConfigured:
                    raise CommandError('Unknown app in excludes: {}'.format(exclude))

        if len(app_labels) == 0:
            app_list = SortedDict((app, None) for app in apps.get_apps() if app not in excluded_apps)
        else:
            app_list = SortedDict()
            for label in app_labels:
                try:
                    app_label, model_label = label.split('.')
                    try:
                        app = apps.get_app(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: {}".format(app_label))
                    if app in excluded_apps:
                        continue
                    model = apps.get_model(app_label, model_label)
                    if model is None:
                        raise CommandError("Unknown model: {}.{}".format(app_label, model_label))

                    if app in app_list.keys():
                        if app_list[app] and model not in app_list[app]:
                            app_list[app].append(model)
                    else:
                        app_list[app] = [model]
                except ValueError:
                    # This is just an app - no model qualifier
                    app_label = label
                    try:
                        app = apps.get_app(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: {}".format(app_label))
                    if app in excluded_apps:
                        continue
                    app_list[app] = None
        present_perms = csw_permission.objects.all().select_related("content_type")
        p_dict = dict([((cur_perm.content_type.app_label, cur_perm.codename), cur_perm) for cur_perm in present_perms])
        found_perms = set()
        found_perms_list = []
        full_dict = dict([((cur_perm.content_type.app_label, cur_perm.codename, cur_perm.content_type.model), cur_perm) for cur_perm in present_perms])
        for app, models in app_list.items():
            if models is None:
                models = apps.get_models(app)
            for model in models:
                if model in excluded_models:
                    continue
                start_time = time.time()
                created = 0
                errors = []
                if hasattr(model, "CSW_Meta") and hasattr(model.CSW_Meta, "permissions"):
                    app_label = model._meta.app_label
                    cur_ct = ContentType.objects.get_for_model(model)
                    for code_name, name, valid_for_object_level in model.CSW_Meta.permissions:
                        found_perms_list.append((app_label, code_name))
                        found_perms.add((app_label, code_name))
                        if (app_label, code_name) in p_dict and (app_label, code_name, cur_ct.model) not in full_dict:
                            print(
                                "removing permission '{}' from old model {}".format(
                                    unicode(p_dict[(app_label, code_name)]),
                                    cur_ct.model
                                )
                            )
                            p_dict[(app_label, code_name)].delete()
                            del p_dict[(app_label, code_name)]
                        if (app_label, code_name) not in p_dict:
                            new_perm = csw_permission.objects.create(
                                codename=code_name,
                                name=name,
                                content_type=cur_ct,
                                valid_for_object_level=valid_for_object_level,
                            )
                            p_dict[(new_perm.content_type.app_label, new_perm.codename)] = new_perm
                            full_dict[(new_perm.content_type.app_label, new_perm.codename, new_perm.content_type.model)] = new_perm
                            created += 1
                            print "Created '{}' for model {}".format(unicode(new_perm), cur_ct.model)
                        else:
                            if valid_for_object_level != p_dict[(app_label, code_name)].valid_for_object_level:
                                print(
                                    "Change valid_for_object_level to {} for {}".format(
                                        unicode(valid_for_object_level),
                                        unicode(p_dict[(app_label, code_name)])
                                    )
                                )
                                p_dict[(app_label, code_name)].valid_for_object_level = valid_for_object_level
                                p_dict[(app_label, code_name)].save()
                if created:
                    print("creation of {:d} took {:7.2f} seconds".format(created, time.time() - start_time))
                    print("found {:7d} error(s)".format(len(errors)))
                    if verbosity > 1:
                        pprint.pprint(errors)
        dup_keys = set([key for key in found_perms if found_perms_list.count(key) > 1])
        if dup_keys:
            print(
                "{} found, please fix models: {}".format(
                    logging_tools.get_plural("duplicate key", len(dup_keys)),
                    ", ".join(sorted([str(_v) for _v in dup_keys]))
                )
            )
            raise(ImproperlyConfigured("CSW permissions not unique"))
        # find old permissions
        old_perms = set(p_dict.keys()) - found_perms
        if old_perms:
            print "Removing {}: {}".format(
                logging_tools.get_plural("old permission", len(old_perms)),
                ", ".join(sorted(["{}.{}".format(app_label, code_name) for app_label, code_name in sorted(old_perms)]))
            )
            for app_label, code_name in old_perms:
                csw_permission.objects.get(Q(codename=code_name)).delete()
