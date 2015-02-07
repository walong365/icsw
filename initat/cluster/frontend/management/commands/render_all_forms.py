#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
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
""" renders all know forms """

from initat.cluster.frontend.forms import *
from initat.cluster.frontend.forms.boot import *
from initat.cluster.frontend.forms.config import *
from initat.cluster.frontend.forms.monitoring import *
from initat.cluster.frontend.forms.package import *
from initat.cluster.frontend.forms.partition import *
from initat.cluster.frontend.forms.user import *
from initat.cluster.frontend.forms.network import *
from initat.cluster.backbone.render import render_string
from django.core.management.base import BaseCommand
from django.db.models import Q
from initat.cluster.backbone import routing
from django.template import Template, Context
from django.template.loader import render_to_string
from django.forms import Form, ModelForm
import inspect
import logging
import logging_tools
import time

class Command(BaseCommand):

    option_list = BaseCommand.option_list + ()
    help = ("Renders all known forms")
    args = ""

    def handle(self, **options):
        render_template = [
            "{% load i18n crispy_forms_tags coffeescript %}",
        ]
        r_dict = {}
        _forms = []
        s_time = time.time()
        for _key, _value in globals().iteritems():
            if inspect.isclass(_value):
                if (issubclass(_value, Form) or issubclass(_value, ModelForm)) and _value != Form and _value != ModelForm:
                    if _key in ["package_search_form"]:
                        continue
                    render_template.extend(
                        [
                            "<script type='text/ng-template' id='{}'>".format(_key.lower().replace("_", ".")),
                            "    {{% crispy {0} {0}.helper %}}".format(_key),
                            "</script>",
                        ]
                    )
                    r_dict[_key] = _value()
        _temp_str = "\n".join(render_template)
        _temp = Template(_temp_str)
        _result = _temp.render(Context(r_dict))
        e_time = time.time()
        print(
            "rendered {} to {} in {}".format(
                logging_tools.get_plural("template", len(r_dict)),
                logging_tools.get_size_str(len(_result)),
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
        print len(_result)
