# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
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

""" url importer """

import os

from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

admin.autodiscover()

urlpatterns = []

path_name = os.path.dirname(__file__)

# for testing
# _BLACKLIST = ["webfrontend"]
_BLACKLIST = ["webfrontend_min", "__init__"]
Z800_MIGRATION = "ICSW_0800_MIGRATION" in os.environ

if settings.ICSW_INCLUDE_URLS and not Z800_MIGRATION:
    for entry in os.listdir(path_name):
        if entry.endswith(".py"):
            _py_name = entry.split(".")[0]
            if _py_name not in _BLACKLIST:
                new_mod = __import__(entry.split(".")[0], globals(), locals())
                if hasattr(new_mod, "urlpatterns"):
                    urlpatterns.extend(new_mod.urlpatterns)

urlpatterns.extend(
    [
        url(r"^{}/admin/".format(settings.REL_SITE_ROOT), include(admin.site.urls)),
    ]
)
