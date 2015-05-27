# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>
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

import ast
# noinspection PyUnresolvedReferences
import pytz
import datetime
# noinspection PyUnresolvedReferences
from django.db.models import Q
import django.utils.timezone
from initat.cluster.backbone.models import duration


def print_tree(t, i=0):
    print " " * i, t, t.origin.type
    for p in t.origin.operands:
        print_tree(p, i + 8)


class KpiUtils(object):
    @staticmethod
    def parse_kpi_time_range_from_kpi(kpi_db):
        start, end = KpiUtils.parse_kpi_time_range(kpi_db.time_range, kpi_db.time_range_parameter)
        if start is None:
            raise RuntimeError("get_historic called for kpi with no defined time range.")
        return start, end

    @staticmethod
    def parse_kpi_time_range(time_range, time_range_parameter):
        """
        return datetime.datetime.combine(datetime.date(2014, 01, 18),
                                         datetime.datetime.min.time()).replace(tzinfo=pytz.utc),\
               datetime.datetime.combine(datetime.date(2014, 02, 01),
                                         datetime.datetime.min.time()).replace(tzinfo=pytz.utc)
        # """

        def get_duration_class_start_end(duration_class, time_point):
            start = duration_class.get_time_frame_start(
                time_point
            )
            end = duration_class.get_end_time_for_start(start)
            return start, end

        start, end = None, None

        if time_range == 'none':
            pass
        elif time_range == 'yesterday':
            start, end = get_duration_class_start_end(
                duration.Day,
                django.utils.timezone.now() - datetime.timedelta(days=1),
                )
        elif time_range == 'last week':
            start, end = get_duration_class_start_end(
                duration.Week,
                django.utils.timezone.now() - datetime.timedelta(days=7),
                )
        elif time_range == 'last month':
            start, end = get_duration_class_start_end(
                duration.Month,
                django.utils.timezone.now().replace(day=1) - datetime.timedelta(days=1)
            )
        elif time_range == 'last year':
            start, end = get_duration_class_start_end(
                duration.Year,
                django.utils.timezone.now().replace(day=1, month=1) - datetime.timedelta(days=1)
            )
        elif time_range == 'last n days':
            start = duration.Day.get_time_frame_start(
                django.utils.timezone.now() - datetime.timedelta(days=time_range_parameter)
            )
            end = start + datetime.timedelta(days=time_range_parameter)

        return (start, end)


def astdump(node, annotate_fields=True, include_attributes=False, indent='  '):
    """
    Return a formatted dump of the tree in *node*.  This is mainly useful for
    debugging purposes.  The returned string will show the names and the values
    for fields.  This makes the code impossible to evaluate, so if evaluation is
    wanted *annotate_fields* must be set to False.  Attributes such as line
    numbers and column offsets are not dumped by default.  If this is wanted,
    *include_attributes* can be set to True.
    """
    def _format(node, level=0):
        if isinstance(node, ast.AST):
            fields = [(a, _format(b, level)) for a, b in ast.iter_fields(node)]
            if include_attributes and node._attributes:
                fields.extend([(a, _format(getattr(node, a), level))
                               for a in node._attributes])
            return ''.join([
                node.__class__.__name__,
                '(',
                ', '.join(('%s=%s' % field for field in fields) if annotate_fields else (b for a, b in fields)),
                ')'])
        elif isinstance(node, list):
            lines = ['[']
            lines.extend((indent * (level + 2) + _format(x, level + 2) + ','
                          for x in node))
            if len(lines) > 1:
                lines.append(indent * (level + 1) + ']')
            else:
                lines[-1] += ']'
            return '\n'.join(lines)
        return repr(node)
    if not isinstance(node, ast.AST):
        raise TypeError('expected AST, got %r' % node.__class__.__name__)
    return _format(node)