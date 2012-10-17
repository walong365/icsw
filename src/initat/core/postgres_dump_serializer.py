"""
A data serializer to postgres dumps
"""

# Add the following to your settings.py to make this serializer available
# throughout your app

#SERIALIZATION_MODULES = {
#    "postgres_dump": "initat.core.postgres_dump_serializer"
#}

import datetime
import pytz
from collections import defaultdict

from django.conf import settings
from django.core.serializers import base
from django.utils.encoding import is_protected_type
from django.utils import datetime_safe


class Serializer(base.Serializer):
    """
    Serializes a QuerySet to a postgres data dump
    """
    def __init__(self):
        self.copy = None
        self.m2ms = {}
        super(Serializer, self).__init__()

    def start_serialization(self):
        pass

    def end_serialization(self):
        pass

    def start_object(self, obj):
        if self.copy is None:
            self.copy = PostgresCopy(obj._meta.db_table)

        # Handle primary keys
        self.copy.row[obj._meta.pk.column] = obj.pk

    def end_object(self, obj):
        self.copy.new_row()

    def handle_field(self, obj, field):
        value = field._get_val_from_obj(obj)
        # Protected types (i.e., primitives like None, numbers, dates,
        # and Decimals) are passed through as is. All other values are
        # converted to string first.
        if is_protected_type(value):
            self.copy.row[field.column] = value
        else:
            self.copy.row[field.column] = field.value_to_string(obj)

    def handle_fk_field(self, obj, field):
        if self.use_natural_keys and hasattr(field.rel.to, 'natural_key'):
            related = getattr(obj, field.name)
            if related:
                value = related.natural_key()
            else:
                value = None
        else:
            value = getattr(obj, field.get_attname())
        self.copy.row[field.column] = value

    def handle_m2m_field(self, obj, field):
        through = field.rel.through
        manager = getattr(obj, field.name)
        table = field.m2m_db_table()
        if field.rel.through._meta.auto_created:
            if not table in self.m2ms:
                self.m2ms[table] = PostgresCopy(table)

            related_filter = {field.m2m_column_name(): obj.pk}
            values = (through._meta.pk.column, manager.source_field_name + "_id",
                      manager.target_field_name + "_id")
            for dict_ in through.objects.filter(**related_filter).values(*values):
                self.m2ms[table].row.update(dict_)
                self.m2ms[table].new_row()

    def getvalue(self):
        return self.copy, self.m2ms


class PostgresCommand(object):
    def quote(self, value):
        return "\"%s\"" % value

    def to_postgres(self, value):
        def escape(value):
            value = unicode(value)
            # Escape all backslashes
            value = value.replace("\\", r"\\")
            # Tab, newline and carriage return
            value = value.replace("\t", r"\t").replace("\n", r"\n").replace("\r", r"\r")
            return value

        def timezone_datetime(value):
            if value.tzinfo is None:
                timezone = pytz.timezone(settings.TIME_ZONE)
                value = timezone.localize(value)

            return datetime_safe.new_datetime(value).strftime("%Y-%m-%d %H:%M:%S%z")

        lookup = defaultdict(lambda: escape)
        lookup.update({
            bool: lambda x: "t" if x else "f",
            datetime.datetime: timezone_datetime,
            datetime.date: lambda x: datetime_safe.new_date(x).strftime("%Y-%m-%d"),
            None.__class__: lambda x: r"\N"
        })

        return lookup[value.__class__](value)


class PostgresCopy(PostgresCommand):
    def __init__(self, name):
        self.name = name

        self.data = []
        self.row = {}
        super(PostgresCopy, self).__init__()

    def new_row(self):
        self.data.append(self.row.copy())
        self.row = {}

    def result(self):
        if self.data:
            fields = sorted(self.data[0].keys())

            yield "COPY %s (%s) FROM stdin;\n" % (self.quote(self.name),
                                                  ",".join((self.quote(x) for x in fields)))
            for row in self.data:
                sorted_data = [row[key] for key in fields]
                yield "%s\n" % "\t".join([self.to_postgres(value) for value in sorted_data])
            yield "\.\n\n"

        else:
            yield "\.\n\n"
