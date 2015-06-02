# -*- coding: utf-8 -*-
"""
Dump data from Django models to PostgreSQL dump format.

Some measurements:
  Stupidly writing out the data:

    with codecs.open("/tmp/outfile", "w", "utf-8") as f:
        for obj in email_log.objects.select_related("certificate", "user", "email_to_user").iterator():
            f.write(smart_unicode(obj.__dict__) + "\n")

  takes ~20s on email_log.objects.count() == 152982.

  The same operation with dumpdatafast takes about ~30s, because of the rather expensive
  datetime operations and some conversion overhead.
"""

from collections import Counter
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models import ForeignKey, OneToOneField, Model, ManyToManyField
from django.utils import datetime_safe
from django.utils.datastructures import SortedDict
from django.utils.encoding import smart_unicode
from functools import partial
from optparse import make_option
import array
import base64
import bz2
import cProfile
import codecs
import datetime
from initat.tools import logging_tools
import math
import networkx as nx
import os
from initat.tools import process_tools
import pstats
import pytz
import subprocess
import sys
import time
import zipfile
import resource
import logging

# lazy init, for use in cluster-server.py::backup_process
BASE_OBJECT = None
TIMEZONE = pytz.timezone(settings.TIME_ZONE)

logger = logging.getLogger(__name__)

class MemoryProfile(object):
    """
    Collect information on maximum memory usage. Use repeated calls to measure()
    and the max_usage attribute.
    """
    def __init__(self):
        self.max_usage = 0

    def _memory_usage(self):
        """ Return memory usage in kB (according to 'man 2 getrusage'"""
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    def measure(self):
        mem = self._memory_usage()
        # print mem
        if mem > self.max_usage:
            self.max_usage = mem
            # print "Found new max: %s" % mem


def sql_iterator(queryset, step=2000):
    """
    Iterate over queryset in *step* sized chunks. Set *step* to a callable
    to calculate the step size based on the queryset length.
    """
    length = queryset.count()
    if callable(step):
        step_size = step(length)
    else:
        step_size = step
    steps = int(math.ceil(length / float(step_size)))

    for i in xrange(steps):
        for obj in queryset[i * step_size:(i + 1) * step_size]:
            yield obj


def _init_base_object():
    # BASE_OBJECT is sometimes set externally, cf. cluster_server/backup_process.py
    global BASE_OBJECT  # pylint: disable-msg=W0603
    if BASE_OBJECT is None:
        BASE_OBJECT = logging.getLogger(__name__)


def log(x):
    _init_base_object()
    BASE_OBJECT.log(logging_tools.LOG_LEVEL_OK, x)


def error(x):
    _init_base_object()
    sys.stderr.write(x + "\n")
    BASE_OBJECT.log(logging_tools.LOG_LEVEL_ERROR, x)


def critical(x):
    _init_base_object()
    sys.stderr.write(x + "\n")
    BASE_OBJECT.log(logging_tools.LOG_LEVEL_CRITICAL, x)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--database', action='store', dest='database',
                    default=DEFAULT_DB_ALIAS, help='Nominates a specific database to dump '
                    'fixtures from. Defaults to the "default" database.'),
        make_option('-e', '--exclude', dest='exclude', action='append', default=[],
                    help='An appname or appname.ModelName to exclude (use multiple'
                    ' --exclude to exclude multiple apps/models).'),
        make_option('-d', '--directory', action='store', default='/tmp', help=''
                    'The output directory (default: %default'),
        make_option('-s', '--stats', action='store_true', help='Show stats for '
                    'each dumped model'),
        make_option('-i', '--iterator', action="store_true", help="Use custom "
                    "QuerySet iterator. (Saves RAM, takes more time)"),
        make_option('-c', '--count', action="store", default=None, type=int, help="Maximum count"
                    "of objects to dump per model"),
        make_option('-b', "--bz2", action="store_true", help="bzip2 the resulting"
                    " postgres dumps"),
        make_option("-p", "--progress", action="store_true", help="Print progress"
                    " bar"),
        make_option("-z", "--step-size", action="store", type=int, default=2000,
                    help="Iterator step size (default %default)"),
        make_option("--one-file", type=str, default="", help="generate one zip file (default '%default', relative to directory)"),
        make_option("-r", "--validate", action="store_true", help="Dump "
                    "only data with valid relations"),
        make_option("-m", "--missing", action="store_true", help="Print missing "
                    "foreign keys. Use with --validate")

    )
    help = "Output the contents of the database in PostgreSQL dump format. "
    args = '[appname appname.ModelName ...]'

    def handle(self, *app_labels, **options):
        try:
            return self._handle(*app_labels, **options)
        except Exception as e:
            critical("Exception occured")
            raise e

    def _handle(self, *app_labels, **options):
        from django.db.models import get_app, get_apps, get_model, get_models  # @UnresolvedImport

        _using = options.get('database')
        excludes = options.get('exclude')
        iterator = options.get("iterator")
        step_size = options.get("step_size")

        # pylint: disable-msg=W0201
        self.directory = options.get('directory')
        self.stats = options.get('stats')
        self.count = options.get("count")
        self.bz2 = options.get("bz2")
        self.progress = options.get("progress")
        self.one_file = options.get("one_file")
        self.validate = options.get("validate")
        self.validator = DatabaseValidator()
        self.missing = options.get("missing")

        if iterator:
            # self.iterator = partial(sql_iterator, step=lambda x: max(x / 100, 2000))
            self.iterator = partial(sql_iterator, step=step_size)
            self.iterator.name = "Custom SQL iterator"
        else:
            self.iterator = lambda x: x.iterator()
            self.iterator.name = "Builtin django queryset iterator()"

        log("Started with options: %s" % options)
        log("app labels: %s" % (", ".join(app_labels)))

        excluded_apps = set()
        excluded_models = set()
        for exclude in excludes:
            if '.' in exclude:
                app_label, model_name = exclude.split('.', 1)
                model_obj = get_model(app_label, model_name)
                if not model_obj:
                    msg = 'Unknown model in excludes: %s' % exclude
                    error(msg)
                    raise CommandError(msg)
                excluded_models.add(model_obj)
            else:
                try:
                    app_obj = get_app(exclude)
                    excluded_apps.add(app_obj)
                except ImproperlyConfigured:
                    msg = 'Unknown app in excludes: %s' % exclude
                    error(msg)
                    raise CommandError(msg)

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
                        msg = "Unknown application: %s" % app_label
                        error(msg)
                        raise CommandError(msg)
                    if app in excluded_apps:
                        continue
                    model = get_model(app_label, model_label)
                    if model is None:
                        msg = "Unknown model: %s.%s" % (app_label, model_label)
                        error(msg)
                        raise CommandError(msg)

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
                        msg = "Unknown application: %s" % app_label
                        error(msg)
                        raise CommandError(msg)
                    if app in excluded_apps:
                        continue
                    app_list[app] = None

        # Process the list of models
        deps = Dependencies()
        models = set()
        for app, model_list in app_list.items():
            if model_list is None:
                model_list = get_models(app)

            for model in model_list:
                models.add(model)
        models = list(models)

        file_list = []
        not_dumped = 0
        for model in models:
            if model in excluded_models:
                continue
            deps.add_to_tree(model)
            try:
                many_to_many, file_name, nd = self.dump_model(model)
            except:
                log(
                    "error dumping model {}: {}".format(
                        unicode(model),
                        process_tools.get_except_info(),
                    )
                )
            else:
                file_list.append(file_name)
                not_dumped += nd
                for m2m in many_to_many:
                    if m2m not in models:
                        models.append(m2m)

        dep_file = os.path.join(self.directory, "DEPENDENCIES")
        file_list.append(dep_file)
        if self.missing and self.validator.missing_entries:
            # print "The following database entries where found to be missing:"
            # for entry in self.validator.missing_entries:
            #    print "%s=%s" % entry
            print "Not dumped: %d" % not_dumped
            print "All missing entries are"
            for entry in self.validator.missing_entries_count.most_common():
                print "%s: %s times" % entry

        if self.validate:
            print "Writing dot file"
            self.validator.write_dot()

        with open(os.path.join(self.directory, "DEPENDENCIES"), "w") as f:
            f.writelines(["%s_%s" % (m._meta.app_label, m._meta.object_name) + "\n" for m in deps.tree])
        if self.one_file:
            if not self.one_file.endswith(".zip"):
                self.one_file = "%s.zip" % (self.one_file)
            if not self.one_file.startswith("/"):
                self.one_file = os.path.join(self.directory, self.one_file)
            new_zip_file = zipfile.ZipFile(self.one_file, "w")
            for file_name in file_list:
                new_zip_file.write(file_name, os.path.basename(file_name))
                os.unlink(file_name)
            new_zip_file.close()

    def dump_model(self, model):
        """
        Dump a model to file and return the related m2m models.
        """
        def convert(obj):
            """
            Convert to Postgres data representation.
            """
            converted_values = []
            
            for key in pg_copy.fields:
                if key in pg_copy.foreign_keys:
                    value = getattr(obj, "{}_id".format(key))
                else:
                    value = getattr(obj, key)

                if isinstance(value, bool):
                    value = u"t" if value else u"f"
                # ForeignKey or OneToOne
                elif isinstance(value, Model):
                    value = smart_unicode(value.pk)
                elif isinstance(value, datetime.datetime):
                    # Adding TZ info is costly, but we can't just append a fixed
                    # distance from UTC to our datestrings because of daylight
                    # savings time.
                    if value.tzinfo is None:
                        value = TIMEZONE.localize(value)

                    # Not much difference between formating a datetime or
                    # creating a datetime_safe and then formatting it.
                    # Each opertion is quite costly
                    value = datetime_safe.new_datetime(value).strftime("%Y-%m-%d %H:%M:%S%z")
                    value = smart_unicode(value)
                elif isinstance(value, datetime.date):
                    value = datetime_safe.new_date(value).strftime("%Y-%m-%d")
                    value = smart_unicode(value)
                elif isinstance(value, (int, float)):
                    value = smart_unicode(value)
                # Handle binary_field
                elif isinstance(value, array.array):
                    value = smart_unicode(base64.b64encode(bz2.compress(value.tostring())))
                elif value is None:
                    value = ur"\N"
                elif value == "\x00":
                    value = u""
                else:
                    # Escape all backslashes, tab, newline and CR
                    value = smart_unicode(value)
                    value = value.replace("\\", ur"\\")
                    value = value.replace("\t", ur"\t").replace("\n", ur"\n").replace("\r", ur"\r")

                converted_values.append(value)

            return u"%s\n" % u"\t".join(converted_values)

        pg_copy = PostgresCopy(model)
        model_file = os.path.join(self.directory, "%s_%s" % (model._meta.app_label, model._meta.object_name))

        # For --stats
        mem_profile = MemoryProfile()
        time_start = time.time()
        db_queries = len(connection.queries)

        # We have to explicitly pass all ForeignKey and OneToOne fields, because
        # select_related() without params does not follow FKs with null=True
        # queryset = model.objects.select_related(*pg_copy.foreign_keys)
        queryset = model.objects.all()  # select_related(*pg_copy.foreign_keys)
        if self.count > 0:
            queryset = queryset[:self.count]
        obj_count = queryset.count()
        # print "obj_count", obj_count
        # print "len", len(queryset)
        # assert obj_count == len(queryset)

        # The min is necessary to avoid 1 / 0 on small --count
        # arguments
        progress_break = min(obj_count, 30)

        msg = "%s (%s)" % (model._meta.object_name, logging_tools.get_plural("entry", int(obj_count)))
        log(msg)
        if self.progress:
            print msg

        if self.validate:
            # self.validator.clear()
            self.validator.validate_model(model)

        not_dumped = 0
        with codecs.open(model_file, "w", "utf-8") as f:
            f.write(pg_copy.header())
            loop_count = 0
            progress_string = ""
            model_name = model._meta.object_name
            for obj in self.iterator(queryset):
                if (model_name, obj.pk) in self.validator.invalid_entries:
                    # print "Not dumping %s=%d because of data errors" % (model, obj.pk)
                    not_dumped += 1
                    continue
                f.write(convert(obj))
                mem_profile.measure()
                loop_count += 1
                if self.progress:
                    if (loop_count % (obj_count / progress_break)) == 0:
                        progress_string += "."
                        sys.stdout.write("[%s" % (progress_string) .ljust(progress_break) + "]\r")
                        sys.stdout.flush()
            f.write(pg_copy.footer())
            mem_profile.measure()

        time_bz_start = time.time()
        if self.bz2:
            subprocess.check_call(["bzip2", "-f", model_file])

        if self.stats:
            if self.progress:
                print
            if self.iterator is not None:
                print "    Iterator: %s" % self.iterator.name
            print "    Count: %s" % obj_count
            print "    DB Queries: %s" % (len(connection.queries) - db_queries)
            print "    Time : %6.2f s" % (time.time() - time_start)
            if self.bz2:
                print "    Time bz: %6.2f s" % (time.time() - time_bz_start)
            print "    RAM  : %6.2f MB" % (mem_profile.max_usage / 1024.0)

        return pg_copy.many_to_many, "%s%s" % (model_file, ".bz2" if self.bz2 else ""), not_dumped


class PostgresCommand(object):
    def __init__(self, model):
        self.model = model
        self.table = model._meta.db_table
        self.columns = [f.column for f in model._meta.fields]
        self.fields = [f.name for f in model._meta.fields]
        self.foreign_keys = [f.name for f in model._meta.fields if isinstance(f, ForeignKey)]
        self.foreign_keys.extend([f.name for f in model._meta.fields if isinstance(f, OneToOneField)])
        self.many_to_many = []
        for m2m in self.model._meta.many_to_many:
            self.many_to_many.append(m2m.rel.through)

    @staticmethod
    def quote(value):
        return "\"%s\"" % value


class PostgresCopy(PostgresCommand):
    def header(self):
        return u"COPY %s (%s) FROM stdin;\n" % (self.quote(self.table),
                                                ",".join((self.quote(x) for x in self.columns)))

    @staticmethod
    def footer():
        return u"\\.\n\n"

    def __str__(self):
        return "<PSQL Copy '%s'>" % self.table


class Dependencies(object):
    def __init__(self):
        self.done = set()
        self.tree = []

    def add_to_tree(self, model_obj):
        self.tree.extend(self._dependency_tree(model_obj))
        if model_obj not in self.tree:
            self.tree.append(model_obj)

    @staticmethod
    def _get_fks(model_obj):
        res = []
        for field in model_obj._meta.fields:
            if isinstance(field, (ForeignKey, OneToOneField)):
                res.append(field.related.model)
        return res

    def _dependency_tree(self, model_obj):
        deps = []
        self.done.add(model_obj)
        fks = self._get_fks(model_obj)
        for fk in fks:
            if fk not in self.done:
                deps.extend(self._dependency_tree(fk))
                deps.append(fk)
        return deps


if __name__ == "__main__":
    # Run profiling
    if False:
        CODE = """
c = Command()
opts = {'count': '10000', 'stats': True, 'bz2': True, 'iterator': False,
            'database': 'default', 'pythonpath': None, 'verbosity': '1',
            'traceback': None, 'exclude': [], 'directory': '/tmp/dumps',
            'progress': True, 'settings': None}
c.handle("backend.customer", **opts)
        """
        cProfile.run(CODE, "dumpfastprof")
        p = pstats.Stats("dumpfastprof")
        s = "-" * 10
        print s, "cumulative", s
        p.sort_stats("cumulative").print_stats(20)
        print s, "time", s
        p.sort_stats("time").print_stats(20)


class DatabaseValidator(object):
    """ Valdiate if the data in the Database is consistent. """
    def __init__(self):
        self.valid_entries = set()
        self.invalid_entries = set()
        self.missing_entries = set()
        self.missing_entries_count = Counter()
        self.graph = nx.DiGraph()

    def clear(self):
        self.valid_entries = set()
        self.invalid_entries = set()
        self.missing_entries = set()
        self.missing_entries_count = Counter()
        self.graph = nx.DiGraph()

    def add_counting_edge(self, src, dst):
        try:
            data = self.graph[src][dst]
        except KeyError:
            data = {"label": 1}
        else:
            data["label"] += 1
        self.graph.add_edge(src, dst, **data)

    def validate_model(self, model):
        """ Validate all objs in the model for FK violations """

        def _is_valid(obj):
            res = True
            fields = obj._meta.fields

            key = (obj._meta.object_name, obj.pk)
            # print "checking", key
            if key in self.valid_entries:
                # print key, "already marked as valid"
                return True

            if key in self.invalid_entries:
                # print key, "already marked as INVALID"
                return False

            for field in fields:
                if isinstance(field, (ForeignKey, OneToOneField)):
                    try:
                        r_obj = getattr(obj, field.name)
                    except ObjectDoesNotExist:
                        res = False
                        self.invalid_entries.add(key)
                        self.add_counting_edge(field.rel.to._meta.object_name, obj._meta.object_name)
                        missing_key = (field.rel.to._meta.object_name, field.value_from_object(obj))
                        self.missing_entries.add(missing_key)
                        self.missing_entries_count.update([missing_key])
                    else:
                        if r_obj is not None:
                            new_res = _is_valid(r_obj)
                            if not new_res:
                                self.invalid_entries.add(key)
                                self.add_counting_edge(r_obj._meta.object_name, obj._meta.object_name)
                                res = new_res
                elif isinstance(field, (ManyToManyField,)):
                    # TODO
                    pass

            if res:
                self.valid_entries.add(key)
            return res

        objs = model.objects.iterator()
        for obj in objs:
            _is_valid(obj)

    def write_dot(self):
        nx.write_dot(self.graph, "/tmp/file.dot")
