""" Dump django models to a postgres script for import via pg_restore. """

import bz2
import logging_tools
import process_tools
import os
import marshal
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.core.exceptions import ImproperlyConfigured
from django.core import serializers
from django.conf import settings
from django.db.models import get_app, get_model, get_models
from django.db import transaction
from initat.core.postgres_dump_serializer import Dependencies


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option("-d", "--destination", dest="destination",
                    default=".", help="set destination directory [%default]"),
        make_option("--miss-cache", dest="miss_cache",
                    default="/tmp/.global_miss_cache",
                    help="set name of global miss_cache [%default]")
    )
    help = "Output the contents of the database in Postgresql format."
    args = '[appname appname.ModelName ...]'
    style = no_style()
    logger = logging_tools.get_logger("dumpdatafast",
                                      ["uds:/var/lib/logging-server/py_log"])

    def log(self, message, level=logging_tools.LOG_LEVEL_WARN):
        self.logger.log(level, message)

    def handle(self, *app_labels, **options):
        settings.HEAVY_CACHE = True
        destination = options.get("destination")
        traceback = options.get("traceback", False)
        serializer = serializers.get_serializer("postgres_dump")()

        try:
            models_to_dump = []
            if app_labels:
                for label in app_labels:
                    if "." in label:
                        app_label, model_label = label.split('.')
                        app = get_app(app_label)
                        cur_model = get_model(app_label, model_label)
                        if cur_model is None:
                            raise ImproperlyConfigured("Model with name %s in "
                                                       "app %s could not be found" %
                                                       (model_label, app_label))
                        models_to_dump.append(cur_model)
                    else:
                        app = get_app(label)
                        models_to_dump.extend(get_models(app))
            else:
                models_to_dump = get_models()
        except ImproperlyConfigured as e:
            self.log(e.message)
            if traceback:
                raise e
            raise CommandError("Unable to dump: %s" % e)

        copy_objs = []
        for cur_model in models_to_dump:
            cur_name = cur_model._meta.db_table
            outfile = os.path.join(destination, "%s.%s.pg_dump" % (cur_model._meta.app_label, cur_name))
            self.log("dumping model %s to %s" % (cur_name, outfile))
            if os.path.isfile(outfile):
                os.unlink(outfile)

            # check if db is reachable
            try:
                with transaction.commit_on_success():
                    cur_model.objects.all().count()
            except Exception:  # pylint: disable-msg=W0703
                self.log("cannot access model '%s': %s" % (cur_name,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
            else:
                copy, m2ms = serializer.serialize(cur_model.objects.iterator())
                self.log("Table data: %s" % copy)
                self.log("m2m data: %s" % ",".join(m2ms.keys()))
                if copy is not None:
                    copy_objs.append(copy)
                    self.log("Writing bz2 file %s" % outfile)
                    table_outfile = outfile + ".bz2"
                    with bz2.BZ2File(table_outfile, "w") as f:
                        for line in copy.result():
                            f.write(line.encode("utf-8"))

                    if m2ms:
                        m2m_outfile = outfile + ".m2m.bz2"
                        self.log("Writing bz2 file m2m.%s" % outfile)
                        with bz2.BZ2File(m2m_outfile, "w") as f:
                            for m2m in m2ms.values():
                                for line in m2m.result():
                                    f.write(line.encode("utf-8"))
                else:
                    self.log("Nothing to dump for model %s" % cur_name)
        self.log("Calculating dependency tree")
        d = Dependencies()
        for cur_model in models_to_dump:
            d.add_to_tree(cur_model)
        with open(os.path.join(destination, "DEPENDENCIES"), "w") as f:
            for i in d.tree:
                f.write("%s\n" % i._meta.db_table)

    def _update_global_miss_cache(self, gmc_name, gmc_dict):
        if os.path.isfile(gmc_name):
            self.log("reading global_miss_cache from %s" % (gmc_name))
            cur_cache = marshal.loads(file(gmc_name, "r").read())
        else:
            self.log("global_miss_cache '%s' not found" % (gmc_name),
                     logging_tools.LOG_LEVEL_WARN)
            cur_cache = {}
        for key in sorted(gmc_dict):
            cur_cache.setdefault(key, set())
            cur_cache[key] |= set(gmc_dict[key].keys())
        file(gmc_name, "w").write(marshal.dumps(cur_cache))
