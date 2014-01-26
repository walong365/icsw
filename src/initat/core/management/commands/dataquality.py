# -*- coding: utf-8 -*-
"""
Compare the data in the database with the Django models
"""

from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS
from django.db.models import ForeignKey, ManyToManyField, OneToOneField
from django.utils.datastructures import SortedDict
from optparse import make_option
import pprint
import time


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--database', action='store', dest='database',
                    default=DEFAULT_DB_ALIAS, help='Nominates a specific database to dump '
                    'fixtures from. Defaults to the "default" database.'),
        make_option('-e', '--exclude', dest='exclude', action='append', default=[],
                    help='An appname or appname.ModelName to exclude (use multiple '
                    '--exclude to exclude multiple apps/models).'),
    )
    help = ("Compare the data in the database with the Django models and report "
            "incompatibilities.")
    args = '[appname appname.ModelName ...]'

    def handle(self, *app_labels, **options):
        from django.db.models import get_app, get_apps, get_model, get_models

        using = options.get('database')
        excludes = options.get('exclude')
        verbosity = int(options.get("verbosity"))

        excluded_apps = set()
        excluded_models = set()
        for exclude in excludes:
            if '.' in exclude:
                app_label, model_name = exclude.split('.', 1)
                model_obj = get_model(app_label, model_name)
                if not model_obj:
                    raise CommandError('Unknown model in excludes: %s' % exclude)
                excluded_models.add(model_obj)
            else:
                try:
                    app_obj = get_app(exclude)
                    excluded_apps.add(app_obj)
                except ImproperlyConfigured:
                    raise CommandError('Unknown app in excludes: %s' % exclude)

        if len(app_labels) == 0:
            app_list = SortedDict((app, None) for app in get_apps() if app not in excluded_apps)
        else:
            app_list = SortedDict()
            for label in app_labels:
                try:
                    app_label, model_label = label.split('.')
                    try:
                        app = get_app(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: %s" % app_label)
                    if app in excluded_apps:
                        continue
                    model = get_model(app_label, model_label)
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
                        app = get_app(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: %s" % app_label)
                    if app in excluded_apps:
                        continue
                    app_list[app] = None

        for app, models in app_list.items():
            if models is None:
                models = get_models(app)

            for model in models:
                if model in excluded_models:
                    continue
                errors = []
                start_time = time.time()
                objs = []
                validator = CustomValidator(model)
                if not model._meta.proxy:
                    print "[+] Checking model %40s (%7s objects)" % (model._meta.object_name,
                                                                     model.objects.count()),
                    objs = model.objects.iterator()

                for obj in objs:
                    tmp = validator.validate(obj)
                    if tmp:
                        errors.append(tmp)
                print "took %7.2f s" % (time.time() - start_time),
                print "found %7s error(s)" % len(errors)
                if verbosity > 1:
                    pprint.pprint(errors)


class CustomValidator(object):
    def __init__(self, model):
        self.model = model

    def validate(self, obj):
        errors = {}
        for field in self.model._meta.fields:
            if not isinstance(field, (ForeignKey, OneToOneField, ManyToManyField)):
                value = getattr(obj, field.name)
                # Check null value
                if not field.null:
                    if value is None:
                        errors.setdefault(obj.pk, {}).setdefault(field.name, []).append("null")
                # Check max_length
                if (field.max_length is not None) and (value not in (None, True, False)):
                    if field.max_length < len(getattr(obj, field.name)):
                        errors.setdefault(obj.pk, {}).setdefault(field.name, []).append("max_length")
            else:
                try:
                    value = getattr(obj, field.name)
                except ObjectDoesNotExist:
                    print getattr(obj, field.name + "_id")
        return errors
