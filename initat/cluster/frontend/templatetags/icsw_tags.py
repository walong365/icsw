# Django settings for ICSW
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2015 Andreas Lang-Nevyjel
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
""" simple raw-include tag for django """

import os

from django import template, conf
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def raw_include(_path):
    _found = False
    for _temp in conf.settings.TEMPLATES:
        for template_dir in _temp["DIRS"]:
            filepath = os.path.join(template_dir, _path)
            if os.path.isfile(filepath):
                _found = True
                break

    if _found:
        return mark_safe(open(filepath, "r").read())
    else:
        raise template.TemplateSyntaxError("raw_include '{}' not found".format(_path))
