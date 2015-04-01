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
""" renders all know forms (also from other apps) """

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
from django.conf import settings
import inspect
import logging
import logging_tools
import time
import importlib
import os


class Command(BaseCommand):
    option_list = BaseCommand.option_list + ()
    help = ("Renders all known forms")
    args = ""

    def handle(self, **options):
        _check_list = [(_key, _value) for _key, _value in globals().iteritems()]
        for _addon_app in settings.ICSW_ADDON_APPS:
            try:
                _addon_form_module = importlib.import_module("initat.cluster.{}.forms".format(_addon_app))
            except ImportError as e:
                print 'No forms directory in {}.'.format(_addon_app)
            else:
                _check_list.extend(
                    [
                        (_key, getattr(_addon_form_module, _key)) for _key in dir(_addon_form_module)
                    ]
                )
        render_template = [
            "{% load i18n crispy_forms_tags coffeescript %}",
        ]
        r_dict = {}
        _forms = []
        s_time = time.time()
        _form_keys = []
        for _key, _value in _check_list:
            if inspect.isclass(_value):
                if (issubclass(_value, Form) or issubclass(_value, ModelForm)) and _value != Form and _value != ModelForm:
                    _form_keys.append(_key)
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
        try:
            _result = _temp.render(Context(r_dict))
        except:
            print("Error rendering, trying to determine defective form")
            for _key in _form_keys:
                _render_template = [
                    "{% load i18n crispy_forms_tags coffeescript %}",
                ]
                _render_template.extend(
                    [
                        "<script type='text/ng-template' id='{}'>".format(_key.lower().replace("_", ".")),
                        "    {{% crispy {0} {0}.helper %}}".format(_key),
                        "</script>",
                    ]
                )
                _temp = Template("\n".join(_render_template))
                try:
                    _result = _temp.render(Context(r_dict))
                except:
                    print("Error for key {}".format(_key))
                    raise
                else:
                    print("OK for key {}".format(_key))
        # remove all whitespaces
        _result = _result.replace("\t", " ")
        while True:
            if _result.count("  "):
                _result = _result.replace("  ", " ")
            elif _result.count("\n\n"):
                _result = _result.replace("\n\n", "\n")
            elif _result.count("\n \n"):
                _result = _result.replace("\n \n", "\n")
            else:
                break
        e_time = time.time()
        targ_file = os.path.join(
            # first SSI_ROOT is that from webfrontend
            settings.SSI_ROOTS[0],
            "forms",
            "all_forms.html"
        )
        file(targ_file, "w").write(_result)
        print(
            "rendered {} to {} in {}, filename is {}".format(
                logging_tools.get_plural("template", len(r_dict)),
                logging_tools.get_size_str(len(_result)),
                logging_tools.get_diff_time_str(e_time - s_time),
                targ_file,
            )
        )
