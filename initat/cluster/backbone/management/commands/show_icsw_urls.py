#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" shows all URLS """



import re

from django.conf import settings
from django.core.exceptions import ViewDoesNotExist
from django.core.management.base import BaseCommand
from django.core.urlresolvers import RegexURLPattern, RegexURLResolver, reverse
from django.utils.translation import activate


def _rewrite(name):
    rw = re.sub("([A-Z]+)", r"_\1", name.replace(":", "_")).lower().replace("__", "_").upper()
    return rw


def extract_views_from_urlpatterns(urlpatterns, base='', namespace=None):
    """
    Return a list of views from a list of urlpatterns.

    Each object in the returned list is a two-tuple: (view_func, regex)
    """
    views = []
    for p in urlpatterns:
        if isinstance(p, RegexURLPattern):
            try:
                if not p.name:
                    name = p.name
                elif namespace:
                    name = '{0}:{1}'.format(namespace, p.name)
                else:
                    name = p.name
                views.append((p.callback, base + p.regex.pattern, name))
            except ViewDoesNotExist:
                continue
        elif isinstance(p, RegexURLResolver):
            try:
                patterns = p.url_patterns
            except ImportError:
                continue
            views.extend(extract_views_from_urlpatterns(patterns, base + p.regex.pattern, namespace=(namespace or p.namespace)))
        elif hasattr(p, '_get_callback'):
            try:
                views.append((p._get_callback(), base + p.regex.pattern, p.name))
            except ViewDoesNotExist:
                continue
        elif hasattr(p, 'url_patterns') or hasattr(p, '_get_url_patterns'):
            try:
                patterns = p.url_patterns
            except ImportError:
                continue
            views.extend(extract_views_from_urlpatterns(patterns, base + p.regex.pattern, namespace=namespace))
        else:
            raise TypeError("%s does not appear to be a urlpattern object" % p)
    return views


def get_urls():
    urls = []
    if getattr(settings, 'ADMIN_FOR', None):
        settings_modules = [__import__(m, {}, {}, ['']) for m in settings.ADMIN_FOR]
    else:
        settings_modules = [settings]

    for settings_mod in settings_modules:
        try:
            urlconf = __import__(settings_mod.ROOT_URLCONF, {}, {}, [b''])
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error occurred while trying to load {}: {}".format(settings_mod.ROOT_URLCONF, str(e)))
            continue

        view_functions = extract_views_from_urlpatterns(urlconf.urlpatterns)
        for (func, regex, url_name) in view_functions:

            if hasattr(func, '__globals__'):
                func_globals = func.__globals__
            elif hasattr(func, 'func_globals'):
                func_globals = func.__globals__
            else:
                func_globals = {}

            # decorators = [d for d in decorator if d in func_globals]
            # if isinstance(func, functools.partial):
            #    func = func.func
            #    decorators.insert(0, 'functools.partial')

            if hasattr(func, '__name__'):
                func_name = func.__name__
            elif hasattr(func, '__class__'):
                func_name = '{}()'.format(func.__class__.__name__)
            else:
                func_name = re.sub(r' at 0x[0-9a-f]+', '', repr(func))

            # print regex, func, url_name
            if url_name:
                _my_re = re.compile(regex)
                try:
                    _reverse = reverse(url_name, args=[1] * _my_re.groups)
                except:
                    pass
                else:
                    _url = _rewrite(url_name)
                    urls.append((_url, _reverse))
    return urls


class Command(BaseCommand):
    help = "Displays all of the url matching routes for the project."

    def handle(self, *args, **options):
        urls = get_urls()
        for _url, _reverse in urls:
            print("        \"{}\": \"{}\",".format(_url, _reverse))
