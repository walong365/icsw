# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2016 Andreas Lang-Nevyjel
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

"""
Django settings for ICSW
"""

from __future__ import unicode_literals, print_function

import base64
import glob
import hashlib
import os
import sys
import warnings

from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from lxml import etree
from initat.debug import ICSW_DEBUG_MODE, ICSW_DEBUG_MIN_RUN_TIME, ICSW_DEBUG_MIN_DB_CALLS, \
    ICSW_DEBUG_SHOW_DB_CALLS

from initat.constants import GEN_CS_NAME, DB_ACCESS_CS_NAME, VERSION_CS_NAME, CLUSTER_DIR, \
    SITE_PACKAGES_BASE
from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, config_store, process_tools

# set unified name
logging_tools.UNIFIED_NAME = "cluster.http"

ugettext = lambda s: s

# monkey-patch threading for python 2.7.x
if (sys.version_info.major, sys.version_info.minor) in [(2, 7)]:
    import threading
    threading._DummyThread._Thread__stop = lambda x: 42

DEBUG = ICSW_DEBUG_MODE

ADMINS = (
    ("Andreas Lang-Nevyjel", "lang-nevyjel@init.at"),
)

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = (
    "127.0.0.1",
)

MANAGERS = ADMINS

MAIL_SERVER = "localhost"

DATABASE_ROUTERS = [
    "initat.cluster.backbone.routers.icswDBRouter"
]

# config stores

# database config
_cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True, access_mode=config_store.AccessModeEnum.GLOBAL)

# version config
# TODO: check for local config when running in debug (development) mode
_vers = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
_DEF_NAMES = ["database", "software", "models"]
ICSW_VERSION_DICT = {
    _name: _vers[_name] for _name in _DEF_NAMES
}
ICSW_DATABASE_VERSION = _vers["database"]
ICSW_SOFTWARE_VERSION = _vers["software"]
ICSW_MODELS_VERSION = _vers["models"]

ICSW_DEBUG = process_tools.get_machine_name() in ["eddie", "lemmy"]

# validate settings
if _cs["password.hash.function"] not in ["SHA1", "CRYPT"]:
    raise ImproperlyConfigured(
        "password hash function '{}' not known".format(
            _cs["password.hash.function"]
        )
    )

ICSW_ALLOWED_OVERALL_STYLES = {"normal", "condensed"}
ICSW_ALLOWED_MENU_LAYOUTS = {"normal", "oldstyle"}


if "overall.style" in _cs:
    ICSW_OVERALL_STYLE = _cs["overall.style"]
else:
    ICSW_OVERALL_STYLE = "normal"

if _cs.get("missing.timezone.is.critical", True):
    warnings.filterwarnings(
        "error",
        r"DateTimeField .* received a naive datetime",
        RuntimeWarning,
        r'django\.db\.models\.fields',
    )

SECRET_KEY = _cs["django.secret.key"]
# create a somehow shorter key
SECRET_KEY_SHORT = base64.b64encode(SECRET_KEY)[0:10]
ICSW_GOOGLE_MAPS_KEY = _cs["google.maps.key"]

_c_key = hashlib.new("md5")

if config_store.ConfigStore.exists(DB_ACCESS_CS_NAME):
    _ps = config_store.ConfigStore(
        DB_ACCESS_CS_NAME,
        quiet=True,
        access_mode=config_store.AccessModeEnum.LOCAL,
        fix_prefix_on_read=False,
    )
else:
    # this only happens when check_content_stores_server was NOT called
    raise ImproperlyConfigured(
        "DB-Access not configured (store {} not found or not readable)".format(
            DB_ACCESS_CS_NAME
        )
    )


def _read_db_settings(store, key):
    if key is None:
        _r_dict = store.get_dict()
        if len(_r_dict):
            _r_dict["idx"] = "0"
    else:
        _r_dict = store[key]
        if len(_r_dict):
            _r_dict["idx"] = key
    if len(_r_dict):
        if "db.info" not in _r_dict:
            _r_dict["db.info"] = "Database {}".format(_r_dict["idx"])
    return _r_dict

_multi_db_prefix = "db"

if _cs.get("multiple.databases", False):
    _db_idx = "{:d}".format(int(_cs["default.database.idx"]))
    if not _ps.prefix:
        raise ImproperlyConfigured(
            "prefix required but not found in DB_ACCESS file"
        )
    elif _ps.prefix != _multi_db_prefix:
        raise ImproperlyConfigured(
            "prefix '{}' has not the required value '{}'".format(
                _ps.prefix,
                _multi_db_prefix,
            )
        )
    ICSW_DATABASE_DICT = {
        _key: _read_db_settings(_ps, _key) for _key in _ps.keys()
    }

else:
    _db_idx = "0"
    if _ps.prefix:
        raise ImproperlyConfigured(
            "prefix defined but not allowed in DB_ACCESS file"
        )
    ICSW_DATABASE_DICT = {
        "0": _read_db_settings(_ps, None)
    }

# default values
DATABASES = {
    "default": {
        "ENGINE": "",
        "NAME": "",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

# filter out empty settings
ICSW_DATABASE_DICT = {key: value for key, value in ICSW_DATABASE_DICT.iteritems() if len(value)}

ICSW_ACTIVE_DATABASE_IDX = _db_idx

if _db_idx in ICSW_DATABASE_DICT:
    _database_dict = ICSW_DATABASE_DICT[_db_idx]

    for src_key, dst_key, _add_to_cache_key, _default in [
        ("db.database", "NAME", True, None),
        ("db.user", "USER", True, None),
        ("db.passwd", "PASSWORD", True, None),
        # to make cache_key the same on different machines
        ("db.host", "HOST", False, None),
        ("db.engine", "ENGINE", True, None),
        ("db.info", "ICSW_INFO", False, "Default database"),
    ]:
        if src_key in _database_dict:
            if _add_to_cache_key:
                _c_key.update(src_key)
                _c_key.update(_database_dict[src_key])
            DATABASES["default"][dst_key] = _database_dict[src_key]
        elif _default:
            DATABASES["default"][dst_key] = _default
        else:
            raise ImproperlyConfigured(
                "key {} -> {} not found in db_access_cs '{}'".format(
                    src_key,
                    dst_key,
                    DB_ACCESS_CS_NAME,
                )
            )
else:
    if DEBUG:
        print("No valid database found")

# print("*", DATABASES)

# build a cache key for accessing memcached
ICSW_CACHE_KEY_LONG = _c_key.hexdigest()
# short ICSW_CACHE_KEY
ICSW_CACHE_KEY = ICSW_CACHE_KEY_LONG[:4]

FILE_ROOT = os.path.normpath(os.path.dirname(__file__))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:{:d}".format(InstanceXML(quiet=True).get_port_dict("memcached", command=True)),
    }
}

TIME_ZONE = "Europe/Vienna"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

LANGUAGES = (
    ("en", _("English")),
)

ANONYMOUS_USER_ID = -1

SILENCED_SYSTEM_CHECKS = ["auth.C010", "auth.C009"]

SITE_ID = 1

REL_SITE_ROOT = "icsw/api/v2"
SITE_ROOT = "/{}".format(REL_SITE_ROOT)
LOGIN_URL = "{}/session/login/".format(SITE_ROOT)

USE_I18N = True

USE_L10N = True

USE_TZ = True

MEDIA_ROOT = os.path.join(FILE_ROOT, "frontend", "media")

MEDIA_URL = "{}/media/".format(SITE_ROOT)

# where to store static files
STATIC_ROOT_DEBUG = "/tmp/.icsw/static/"
if DEBUG:
    STATIC_ROOT = STATIC_ROOT_DEBUG
    ICSW_PROD_WEB_DIR = "/tmp/NOT_DEFINED"
else:
    STATIC_ROOT = "/srv/www/init.at/icsw/static"
    ICSW_PROD_WEB_DIR = "/srv/www/init.at/icsw"

if not os.path.isdir(STATIC_ROOT_DEBUG):
    try:
        os.makedirs(STATIC_ROOT_DEBUG)
    except IOError:
        pass

# where to store PDF Files
REPORT_DATA_STORAGE_DIR = os.path.join("/tmp/", ".icswReportData")
if not os.path.exists(REPORT_DATA_STORAGE_DIR):
    os.mkdir(REPORT_DATA_STORAGE_DIR)

# use X-Forwarded-Host header
USE_X_FORWARDED_HOST = True

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "{}/static/".format(SITE_ROOT)

THEMES = [
    ("default", "Default"),
    ("cora", "Cora"),
    ("sirocco", "Sirocco"),
]
THEME_DEFAULT = "default"

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_HTTPONLY = True

# Make this unique, and don't share it with anybody.
# SECRET_KEY = "av^t8g^st(phckz=9u#68k6p&amp;%3@h*z!mt=mo@3t!!ls^+4%ic"

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    # "django.middleware.transaction.TransactionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "initat.cluster.backbone.middleware.thread_local_middleware",
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',

    "backbone.middleware.database_debug",
    # "django.middleware.gzip.GZipMiddleware",

    "reversion.middleware.RevisionMiddleware",
)

if not DEBUG:
    MIDDLEWARE_CLASSES = tuple(
        # ["django.middleware.gzip.GZipMiddleware"] +
        list(
            MIDDLEWARE_CLASSES
        )
    )
ROOT_URLCONF = "initat.cluster.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "initat.cluster.wsgi.application"


INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # Uncomment the next line to enable admin documentation:
    "django_extensions",
    "reversion",
    "channels"
)

ICSW_WEBCACHE = os.path.join(CLUSTER_DIR, "share", "webcache")

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# print STATICFILES_FINDERS, STATICFILES_STORAGE

STATICFILES_DIRS = []
if os.path.isdir("/opt/icinga/share/images/logos"):
    STATICFILES_DIRS.append(
        ("icinga", "/opt/icinga/share/images/logos")
    )

STATICFILES_DIRS.append(
    ("admin", os.path.join(SITE_PACKAGES_BASE, "django", "contrib", "admin", "static", "admin")),
)

STATICFILES_DIRS = list(STATICFILES_DIRS)

# print STATICFILES_DIRS

# add all applications, including backbone

AUTOCOMMIT = True

INSTALLED_APPS = list(INSTALLED_APPS)
ADDITIONAL_ANGULAR_APPS = []
# ADDITIONAL_URLS = []
ICSW_ADDITIONAL_JS = []
ICSW_ADDITIONAL_HTML = []
# dict:
ICSW_ADDITIONAL_APPS = {}

# my authentication backend
AUTHENTICATION_BACKENDS = (
    "initat.cluster.backbone.cluster_auth.db_backend",
)

ICSW_ADDON_APPS = []
# add everything below cluster
dir_name = os.path.dirname(__file__)
ICSW_PRODUCTION_MODE = dir_name.startswith("/opt/python")
ICSW_SERVICE_ENUM_LIST = []

for sub_dir in os.listdir(dir_name):
    full_path = os.path.join(dir_name, sub_dir)
    if os.path.isdir(full_path):
        if any([entry.endswith("views.py") for entry in os.listdir(full_path)]):
            add_app = "initat.cluster.{}".format(sub_dir)
            if add_app not in INSTALLED_APPS:
                # search for icsw meta
                icsw_meta = os.path.join(full_path, "ICSW.meta.xml")
                if os.path.exists(icsw_meta):
                    try:
                        _tree = etree.fromstring(file(icsw_meta, "r").read())
                    except:
                        raise
                    else:
                        ICSW_ADDON_APPS.append(sub_dir)
                        ICSW_ADDITIONAL_APPS[sub_dir] = {
                            "config": os.path.join(sub_dir, "config", "config.xml")
                        }
                        ADDITIONAL_ANGULAR_APPS.extend(
                            [_el.attrib["name"] for _el in _tree.findall(".//app")]
                        )
                        if not ICSW_PRODUCTION_MODE:
                            # search local dirs in debug mode
                            js_full_paths = glob.glob(os.path.join(dir_name, "addons", sub_dir, "initat", "cluster", "work", "icsw", "*.js"))
                            html_full_paths = glob.glob(os.path.join(dir_name, "addons", sub_dir, "initat", "cluster", "work", "icsw", "*.html"))
                        else:
                            # search static_root in production mode
                            js_full_paths = []
                            for _js_glob in _tree.findall(".//app/js-glob"):
                                js_full_paths.extend(glob.glob(os.path.join(ICSW_PROD_WEB_DIR, _js_glob.text)))
                            html_full_paths = []
                            for _html_glob in _tree.findall(".//app/html-glob"):
                                html_full_paths.extend(glob.glob(os.path.join(ICSW_PROD_WEB_DIR, _html_glob.text)))
                        ICSW_ADDITIONAL_JS.extend(
                            [
                                js_file for js_file in js_full_paths
                            ]
                        )
                        ICSW_ADDITIONAL_HTML.extend(
                            [
                                html_file for html_file in html_full_paths
                            ]
                        )
                INSTALLED_APPS.append(add_app)

_show_apps = False
for rem_app_key in [key for key in os.environ.keys() if key.startswith("INIT_REMOVE_APP_NAME")]:
    rem_app = os.environ[rem_app_key]
    _show_apps = True
    if rem_app.endswith("."):
        INSTALLED_APPS = [_entry for _entry in INSTALLED_APPS if not _entry.startswith(rem_app)]
    else:
        if rem_app in INSTALLED_APPS:
            INSTALLED_APPS.remove(rem_app)

if any([_app.startswith("initat.cluster.") for _app in INSTALLED_APPS]):
    ICSW_INCLUDE_URLS = True
    AUTH_USER_MODEL = "backbone.user"
else:
    ICSW_INCLUDE_URLS = False
# print(AUTH_USER_MODEL)

INSTALLED_APPS = tuple(INSTALLED_APPS)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(MEDIA_ROOT, "angular"),
            os.path.join(CLUSTER_DIR, "share", "doc", "handbook", "chunks"),
        ],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.template.context_processors.debug",
            ],
            "debug": DEBUG,
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },

    }
]

INSTALLED_APPS = tuple(list(INSTALLED_APPS) + ["rest_framework"])

# fake migrations
if "ICSW_DISABLE_MIGRATIONS" in os.environ:
    MIGRATION_MODULES = {_app.split(".")[-1]: None for _app in list(INSTALLED_APPS)}

if _show_apps:
    print(
        "{:d} INSTALLED_APPS: {}".format(
            len(INSTALLED_APPS),
            " ".join(INSTALLED_APPS),
        )
    )

TEST_RUNNER = "django.test.runner.DiscoverRunner"

rest_renderers = (
    [
        "rest_framework.renderers.BrowsableAPIRenderer"
    ] if DEBUG else []
) + [
    "rest_framework.renderers.JSONRenderer",
    # "rest_framework_csv.renderers.CSVRenderer",
    "rest_framework_xml.renderers.XMLRenderer",
]

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': tuple(rest_renderers),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework_xml.parsers.XMLParser",
        "rest_framework.parsers.JSONParser",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "initat.cluster.frontend.rest_views.csw_exception_handler",
    "ID_FIELD_NAME": "idx",
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        "initat": {
            "()": "initat.tools.logging_net.icswInitFormatter",
        },
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        "console": {
            "level": "INFO" if DEBUG else "WARN",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "init_unified": {
            "level": "INFO" if DEBUG else "WARN",
            "class": "initat.tools.logging_net.icswInitHandlerUnified",
            "formatter": "initat",
        },
        "init": {
            "level": 'INFO' if DEBUG else "WARN",
            "class": "initat.tools.logging_net.icswInitHandler",
            "formatter": "initat",
        },
        "init_mail": {
            "level": "ERROR",
            "class": "initat.tools.logging_net.icswInitEmailHandler",
            "formatter": "initat",
        },
    },
    'loggers': {
        'django': {
            'handlers': ['init_unified', "init_mail", "console"],
            'propagate': True,
            'level': 'INFO',
        },
        'initat': {
            'handlers': ['init_unified', "init_mail"],
            'propagate': True,
            'level': 'WARN',
        },
        'cluster': {
            'handlers': ["init_unified", "init", "init_mail"],
            'propagate': True,
            'level': 'INFO' if DEBUG else "WARN",
        },
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "asgi_redis.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                ("127.0.0.1", 6379)
            ],
        },
        "ROUTING": "initat.cluster.backbone.channel_routing.channel_routing",
    },
}
