# Copyright (C) 2012-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" dump django database to XML """

from collections import OrderedDict
from optparse import make_option

from django.apps import apps
from django.core import serializers
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS
from django.db.models import ForeignKey, OneToOneField


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--format', default='json', dest='format',
            help='Specifies the output serialization format for fixtures.'
        ),
        make_option(
            '--indent', default=None, dest='indent', type='int',
            help='Specifies the indent level to use when pretty-printing output'
        ),
        make_option(
            '--database', action='store', dest='database',
            default=DEFAULT_DB_ALIAS, help='Nominates a specific database to dump fixtures from. Defaults to the "default" database.'
        ),
        make_option(
            '-e', '--exclude', dest='exclude', action='append', default=[],
            help='An appname or appname.ModelName to exclude (use multiple --exclude to exclude multiple apps/models).'
        ),
        make_option(
            '-n', '--natural', action='store_true', dest='use_natural_keys', default=False,
            help='Use natural keys if they are available.'
        ),
        make_option(
            '-a', '--all', action='store_true', dest='use_base_manager', default=False,
            help="Use Django's base manager to dump all models stored in the database, "
            "including those that would otherwise be filtered or modified by a custom manager."
        ),
        make_option(
            '-t', '--traceback', action='store_true', default=True,
        )
    )
    help = ("Output the contents of the database as a fixture of the given "
            "format (using each model's default manager unless --all is "
            "specified).")
    args = '[appname appname.ModelName ...]'

    def handle(self, *app_labels, **options):

        _format = options.get('format')
        indent = options.get('indent')
        using = options.get('database')
        excludes = options.get('exclude')
        show_traceback = options.get('traceback')
        use_natural_keys = options.get('use_natural_keys')
        # use_base_manager = options.get('use_base_manager')

        excluded_apps = set()
        excluded_models = set()
        for exclude in excludes:
            if '.' in exclude:
                app_label, model_name = exclude.split('.', 1)
                model_obj = apps.get_model(app_label, model_name)
                if not model_obj:
                    raise CommandError('Unknown model in excludes: %s' % exclude)
                excluded_models.add(model_obj)
            else:
                try:
                    app_obj = apps.get_app_config(exclude)
                    excluded_apps.add(app_obj)
                except ImproperlyConfigured:
                    raise CommandError('Unknown app in excludes: %s' % exclude)
        apps_list = apps.get_app_configs()
        if len(app_labels) == 0:
            app_list = OrderedDict((app, None) for app in apps.get_app_config() if app not in excluded_apps)
        else:
            app_list = OrderedDict()
            for label in app_labels:
                try:
                    app_label, model_label = label.split('.')
                    try:
                        app = apps.get_app_config(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: %s" % app_label)
                    if app in excluded_apps:
                        continue
                    model = apps.get_model(app_label, model_label)
                    if model is None:
                        raise CommandError("Unknown model: %s.%s" % (app_label, model_label))

                    if app in app_list.keys():
                        if app_list[app] and model not in app_list[app]:
                            app_list[app].append(model)
                    else:
                        app_list[app] = [model]
                except ValueError:
                    # This is just an app - no model qualifier
                    app_label = label
                    try:
                        app = apps.get_app_config(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: %s" % app_label)
                    if app in excluded_apps:
                        continue
                    app_list[app] = None

        # Check that the serialization format exists; this is a shortcut to
        # avoid collating all the objects and _then_ failing.
        if _format not in serializers.get_public_serializer_formats():
            raise CommandError("Unknown serialization format: %s" % _format)

        try:
            serializers.get_serializer(_format)
        except KeyError:
            raise CommandError("Unknown serialization format: %s" % _format)

        deps = Dependencies()
        models = set()
        for app_config, model_list in app_list.items():
            if model_list is None:
                model_list = app_config.get_models()

            for model in model_list:
                models.add(model)
        models = list(models)

        for model in models:
            if model in excluded_models:
                continue
            deps.add_to_tree(model)
            # many_to_many, file_name = self.dump_model(model)
            # file_list.append(file_name)
            # for m2m in many_to_many:
            #    if m2m not in models:
            #        models.append(m2m)
        deps.generate_tree()

        def get_objects(models):
            for model in models:
                if model in excluded_models:
                    continue
                for obj in model.objects.using(using).order_by(model._meta.pk.name).iterator():
                    yield obj

        try:
            self.stdout.ending = None
            serializers.serialize(
                _format, get_objects(deps.tree), indent=indent,
                use_natural_keys=use_natural_keys, stream=self.stdout)
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)


class Dependencies(object):
    def __init__(self):
        # self.done = set()
        self.__models = set()
        self.__dep_list = []

    def add_to_tree(self, model_obj):
        strong_fks, weak_fks = self._get_fks(model_obj)
        self.__models.add(model_obj)
        self.__dep_list.append((model_obj, strong_fks, weak_fks))

    def generate_tree(self):
        model_list = []
        model_deps = self.__dep_list
        while model_deps:
            # print "-" * 50, len(model_deps)
            skipped, changed = ([], False)
            while model_deps:
                model, s_deps, w_deps = model_deps.pop()
                found = True
                for cand in ((d not in self.__models or d in model_list) for d in s_deps):
                    if not cand:
                        found = False
                if found:
                    model_list.append(model)
                    changed = True
                else:
                    skipped.append((model, s_deps, w_deps))
            if not changed:
                raise CommandError(
                    "Can't resolve %d dependencies for %s in serialized app list." % (
                        len(skipped),
                        ', '.join('%s.%s' % (model._meta.app_label, model._meta.object_name)
                                  for model, s_deps, w_deps in sorted(skipped, key=lambda obj: obj[0].__name__))
                    )
                )
            model_deps = skipped
        self.tree = model_list

    @staticmethod
    def _get_fks(model_obj):
        strong_res, weak_res = ([], [])
        for field in model_obj._meta.fields:
            if isinstance(field, (ForeignKey, OneToOneField)):
                if field.null:
                    weak_res.append(field.related.model)
                else:
                    strong_res.append(field.related.model)
        return strong_res, weak_res
