# Django settings for cluster project.
# -*- coding: utf-8 -*-
import glob
import os
import sys
from lxml import etree

from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import get_random_string
from initat.tools import logging_tools

# set unified name
logging_tools.UNIFIED_NAME = "cluster.http"

ugettext = lambda s: s  # @IgnorePep8

# monkey-patch threading for python 2.7.x
if (sys.version_info.major, sys.version_info.minor) in [(2, 7)]:
    import threading
    threading._DummyThread._Thread__stop = lambda x: 42  # @IgnorePep8

DEBUG = "DEBUG_WEBFRONTEND" in os.environ
LOCAL_STATIC = "LOCAL_STATIC" in os.environ
PIPELINE_ENABLED = not DEBUG
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ("Andreas Lang-Nevyjel", "lang-nevyjel@init.at"),
)

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ("127.0.0.1", "192.168.1.173",)

MANAGERS = ADMINS

MAIL_SERVER = "localhost"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
        # "CONN_MAX_AGE" : 30,
    }
}

DATABASE_ROUTERS = ["initat.cluster.backbone.routers.db_router"]

NEW_CONF_FILE = "/etc/sysconfig/cluster/db.cf"
OLD_CONF_FILE = "/etc/sysconfig/cluster/mysql.cf"

SLAVE_MODE = os.path.exists("/etc/sysconfig/cluster/is_slave")
SATELLITE_MODE = os.path.exists("/etc/sysconfig/cluster/is_satellite")
if not SLAVE_MODE:
    SLAVE_MODE = not os.path.exists("/opt/python-init/lib/python/site-packages/initat/cluster/frontend")

if SATELLITE_MODE:
    # satellite mode, no database configured
    conf_content = ""
else:
    if os.path.isfile(NEW_CONF_FILE):
        try:
            conf_content = file(NEW_CONF_FILE, "r").read()
        except IOError:
            raise ImproperlyConfigured("cannot read '{}', wrong permissions ?".format(NEW_CONF_FILE))
    else:
        if not os.path.isfile(OLD_CONF_FILE):
            raise ImproperlyConfigured("config '{}' and '{}' not found".format(NEW_CONF_FILE, OLD_CONF_FILE))
        else:
            try:
                conf_content = file(OLD_CONF_FILE, "r").read()
            except IOError:
                raise ImproperlyConfigured("cannot read '{}', wrong permissions ?".format(OLD_CONF_FILE))

sql_dict = {
    key.split("_")[1]: value for key, value in [
        line.strip().split("=", 1) for line in conf_content.split("\n") if line.count("=") and line.count("_") and not line.count("NAGIOS")
    ]
}

mon_dict = {
    key.split("_")[1]: value for key, value in [
        line.strip().split("=", 1) for line in conf_content.split("\n") if line.count("=") and line.count("_") and line.count("NAGIOS_")
    ]
}

for src_key, dst_key in [
    ("DATABASE", "NAME"),
    ("USER", "USER"),
    ("PASSWD", "PASSWORD"),
    ("HOST", "HOST"),
    ("ENGINE", "ENGINE")
]:
    if src_key in sql_dict:
        DATABASES["default"][dst_key] = sql_dict[src_key]

if mon_dict:
    DATABASES["monitor"] = {key: value for key, value in DATABASES["default"].iteritems()}
    for src_key, dst_key in [
        ("DATABASE", "NAME"),
        ("USER", "USER"),
        ("PASSWD", "PASSWORD"),
        ("HOST", "HOST"),
        ("ENGINE", "ENGINE")
    ]:
        if src_key in mon_dict:
            DATABASES["monitor"][dst_key] = mon_dict[src_key]

FILE_ROOT = os.path.normpath(os.path.dirname(__file__))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:11211",
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = "Europe/Vienna"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

LANGUAGES = (
    ("en", _("English")),
)

ANONYMOUS_USER_ID = -1

SITE_ID = 1

REL_SITE_ROOT = "cluster"
SITE_ROOT = "/{}".format(REL_SITE_ROOT)
LOGIN_URL = "{}/session/login/".format(SITE_ROOT)

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_ROOT = os.path.join(FILE_ROOT, "frontend", "media")

MEDIA_URL = "{}/media/".format(SITE_ROOT)

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"

# where to store static files
STATIC_ROOT_DEBUG = "/tmp/.icsw/static/"
if DEBUG:
    STATIC_ROOT = STATIC_ROOT_DEBUG
else:
    if LOCAL_STATIC:
        STATIC_ROOT = STATIC_ROOT_DEBUG
    else:
        STATIC_ROOT = "/srv/www/htdocs/icsw/static"

if not os.path.isdir(STATIC_ROOT_DEBUG):
    try:
        os.makedirs(STATIC_ROOT_DEBUG)
    except:
        pass

# use X-Forwarded-Host header
USE_X_FORWARDED_HOST = True

# STATIC_ROOT = "/opt/python-init/lib/python2.7/site-packages/initat/cluster/"

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "{}/static/".format(SITE_ROOT)

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_HTTPONLY = True

# Make this unique, and don't share it with anybody.
# SECRET_KEY = "av^t8g^st(phckz=9u#68k6p&amp;%3@h*z!mt=mo@3t!!ls^+4%ic"

# List of callables that know how to import templates from various sources.
TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "django.core.context_processors.media",
    "django.core.context_processors.debug",
    "initat.cluster.backbone.context_processors.add_session",
    "initat.cluster.backbone.context_processors.add_settings",
    "initat.cluster.backbone.context_processors.add_csw_permissions",
)

TEMPLATE_LOADERS = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
)

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
    "pipeline.middleware.MinifyHTMLMiddleware",

    "reversion.middleware.RevisionMiddleware",
)

if not DEBUG:
    MIDDLEWARE_CLASSES = tuple(
        ["django.middleware.gzip.GZipMiddleware"] +
        list(
            MIDDLEWARE_CLASSES
        )
    )
ROOT_URLCONF = "initat.cluster.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "initat.cluster.wsgi.application"

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(MEDIA_ROOT, "angular"),
    "/opt/cluster/share/doc/handbook/chunks",
)

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # Uncomment the next line to enable admin documentation:
    # "django.contrib.admindocs",
    "django_extensions",
    "reversion",
    "pipeline",
    "static_precompiler",
    "crispy_forms",
)
if SLAVE_MODE:
    INSTALLED_APPS = tuple([_entry for _entry in list(INSTALLED_APPS) if _entry not in ["crispy_forms"]])


ICSW_WEBCACHE = "/opt/cluster/share/webcache"

# crispy settings, bootstrap3 is angularized via a patch
CRISPY_ALLOWED_TEMPLATE_PACKS = ('bootstrap3')
CRISPY_TEMPLATE_PACK = "bootstrap3"
CRISPY_FAIL_SILENTLY = not DEBUG

# coffee settings
COFFEESCRIPT_EXECUTABLE = "/opt/cluster/bin/coffee"
# STATIC_PRECOMPILER_CACHE = not DEBUG

# pipeline settings
PIPELINE_YUGLIFY_BINARY = "/opt/cluster/lib/node_modules/yuglify/bin/yuglify"
if not SLAVE_MODE:
    if not os.path.exists(PIPELINE_YUGLIFY_BINARY):
        raise ImproperlyConfigured("no {} found".format(PIPELINE_YUGLIFY_BINARY))
PIPELINE_YUGLIFY_CSS_ARGUMENTS = "--terminal"
PIPELINE_YUGLIFY_JS_ARGUMENTS = "--terminal"
if DEBUG:
    STATICFILES_STORAGE = "pipeline.storage.PipelineStorage"
else:
    STATICFILES_STORAGE = "pipeline.storage.PipelineCachedStorage"

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "static_precompiler.finders.StaticPrecompilerFinder",
    "pipeline.finders.PipelineFinder",
)

if DEBUG:
    STATICFILES_FINDERS = tuple(list(STATICFILES_FINDERS) + ["pipeline.finders.PipelineFinder"])

STATICFILES_DIRS = []
if os.path.isdir("/opt/icinga/share/images/logos"):
    STATICFILES_DIRS.append(
        ("icinga", "/opt/icinga/share/images/logos")
    )
STATICFILES_DIRS.append(
    ("admin", "/opt/python-init/lib/python/site-packages/django/contrib/admin/static/admin"),
)
STATICFILES_DIRS = list(STATICFILES_DIRS)


# add all applications, including backbone

AUTOCOMMIT = True

INSTALLED_APPS = list(INSTALLED_APPS)
# deprecated ?
ADDITIONAL_MENU_FILES = []
ADDITIONAL_ANGULAR_APPS = []
ADDITIONAL_URLS = []
ADDITIONAL_JS = []

# my authentication backend
AUTHENTICATION_BACKENDS = (
    "initat.cluster.backbone.cluster_auth.db_backend",
)

ICSW_ADDON_APPS = []
# add everything below cluster
dir_name = os.path.dirname(__file__)
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
                        pass
                    else:
                        ICSW_ADDON_APPS.append(sub_dir)
                        ADDITIONAL_ANGULAR_APPS.extend(
                            [_el.attrib["name"] for _el in _tree.findall(".//app")]
                        )
                        ADDITIONAL_URLS.extend(
                            [
                                (
                                    _el.attrib["name"],
                                    _el.attrib["url"],
                                    [
                                        _part for _part in _el.get("arguments", "").strip().split() if _part
                                    ]
                                ) for _el in _tree.findall(".//url")
                            ]
                        )
                        js_full_paths = glob.glob(os.path.join(full_path, "static", "js", "*.js"))
                        ADDITIONAL_JS.extend(
                            [
                                os.path.join("js", os.path.basename(js_file)) for js_file in js_full_paths
                            ]
                        )
                INSTALLED_APPS.append(add_app)

ADDITIONAL_JS = tuple(ADDITIONAL_JS)

for rem_app_key in [key for key in os.environ.keys() if key.startswith("INIT_REMOVE_APP_NAME")]:
    rem_app = os.environ[rem_app_key]
    if rem_app.endswith("."):
        INSTALLED_APPS = [_entry for _entry in INSTALLED_APPS if not _entry.startswith(rem_app)]
    else:
        if rem_app in INSTALLED_APPS:
            INSTALLED_APPS.remove(rem_app)

if any([_app.startswith("initat.cluster.") for _app in INSTALLED_APPS]):
    AUTH_USER_MODEL = "backbone.user"

INSTALLED_APPS = tuple(INSTALLED_APPS)

PIPELINE_COMPILERS = (
    "pipeline.compilers.coffee.CoffeeScriptCompiler",
)

PIPELINE_COFFEE_SCRIPT_BINARY = "/opt/cluster/bin/coffee"
PIPELINE_COFFEE_SCRIPT_ARGUMENTS = ""

PIPELINE_CSS = {
    "part1": {
        "source_filenames": {
            "css/smoothness/jquery-ui-1.10.2.custom.min.css",
            "css/main.css",
            "css/ui.fancytree.css",
            "css/jqModal.css",
            "css/codemirror.css",
            "css/bootstrap.css",
            "css/jquery.Jcrop.min.css",
            "css/angular-datetimepicker.css",
            "css/angular-block-ui.css",
            "css/select.css",
            "css/ladda.min.css",
            "css/tooltip.css",
            "css/smart-table.css",
            "css/font-awesome.min.css",
            "css/icsw.css",
            "css/toaster.css",
            "css/bootstrap-dialog.css",
        },
        "output_filename": "pipeline/css/part1.css"
    }
}

PIPELINE_JS = {
    "js_jquery_new": {
        "source_filenames": {
            "js/modernizr-2.8.1.min.js",
            "js/jquery-2.1.3.min.js",
        },
        "output_filename": "pipeline/js/jquery_new.js"
    },
    "js_base": {
        "source_filenames": (
            "js/jquery-ui-1.10.2.custom.js",
            "js/angular-1.3.15.js",
            "js/lodash.js",
            "js/bluebird.js",
            "js/codemirror/codemirror.js",
            "js/bootstrap.js",
            "js/jquery.color.js",
            "js/jquery.blockUI.js",
            "js/moment-with-locales.js",
            "js/jquery.Jcrop.min.js",
            "js/spin.js",
            "js/ladda.js",
            "js/angular-ladda.js",
            "js/hamster.js",
            "js/toaster.js",
            "js/angular-gettext.min.js",
            "js/webfrontend_translation.js",
        ),
        "output_filename": "pipeline/js/base.js"
    },
    "js_extra1": {
        "source_filenames": (
            "js/codemirror/addon/selection/active-line.js",
            "js/codemirror/mode/python/python.js",
            "js/codemirror/mode/xml/xml.js",
            "js/codemirror/mode/shell/shell.js",
            # "js/jquery-ui-timepicker-addon.js",
            "js/angular-route.min.js",
            "js/angular-resource.min.js",
            "js/angular-cookies.min.js",
            "js/angular-sanitize.min.js",
            "js/angular-animate.min.js",
            "js/angular-file-upload.js",
            "js/restangular.min.js",
            "js/angular-block-ui.js",
            "js/select.js",
            "js/ui-bootstrap-tpls.min.js",
            "js/angular-ui-router.js",
            # must use minified version, otherwise the minifier destroys injection info
            "js/ui-codemirror.min.js",
            "js/angular-datetimepicker.js",
            # "js/angular-strap.min.js",
            # "js/angular-strap.tpl.min.js",
            "js/angular-noVNC.js",
            "js/FileSaver.js",
            "js/mousewheel.js",
            "js/smart-table.js",
            "js/angular-google-maps.min.js",
            "js/bootstrap-dialog.js",
        ),
        "output_filename": "pipeline/js/extra1.js"
    },
    "js_icsw_modules": {
        "source_filenames": ADDITIONAL_JS,
        "output_filename": "pipeline/js/icsw_modules.js"
    },
    "icsw_cs1": {
        "source_filenames": (
            "icsw/*/*.coffee",
            "icsw/*/*/*.coffee",
        ),
        "output_filename": "pipeline/js/icsw1.js"
    }
}

SSI_ROOTS = []
SSI_FILES = []
SSI_ROOT_DICT = {}
for _local_ssi_root in ["frontend"] + ICSW_ADDON_APPS:
    _SSI_ROOT = os.path.normpath(os.path.join(__file__, "..", _local_ssi_root, "static", "icsw"))
    SSI_ROOT_DICT[_local_ssi_root] = _SSI_ROOT
    # print _SSI_ROOT
    if os.path.exists(_SSI_ROOT):
        for _dir, _dirlist, _filelist in os.walk(_SSI_ROOT):
            if _dir == _SSI_ROOT:
                continue
            for _file in _filelist:
                if _file.endswith(".html"):
                    # print "*", _dir, _file
                    SSI_FILES.append(os.path.join(_dir, _file))
        SSI_ROOTS.append(_SSI_ROOT)
ALLOWED_INCLUDE_ROOTS = SSI_ROOTS

HANDBOOK_DIR = "/opt/cluster/share/doc/handbook"

HANDBOOK_PDF_PRESENT = bool(glob.glob(os.path.join(HANDBOOK_DIR, "*.pdf")))

HANDBOOK_CHUNKS_PRESENT = bool(glob.glob(os.path.join(HANDBOOK_DIR, "*chunk")))

LOCAL_CONFIG = "/etc/sysconfig/cluster/local_settings.py"

_config_ok = False

if os.path.isfile(LOCAL_CONFIG):
    local_dir = os.path.dirname(LOCAL_CONFIG)
    sys.path.append(local_dir)
    try:
        from local_settings import SECRET_KEY, PASSWORD_HASH_FUNCTION, GOOGLE_MAPS_KEY,\
            PASSWORD_CHARACTER_COUNT, AUTO_CREATE_NEW_DOMAINS, LOGIN_SCREEN_TYPE  # @UnresolvedImport
    except:
        pass
    else:
        _config_ok = True
    sys.path.remove(local_dir)

if not _config_ok:
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    SECRET_KEY = get_random_string(50, chars)
    GOOGLE_MAPS_KEY = ""
    PASSWORD_CHARACTER_COUNT = 8
    PASSWORD_HASH_FUNCTION = "SHA1"
    AUTO_CREATE_NEW_DOMAINS = True
    LOGIN_SCREEN_TYPE = "big"


# validate settings
if PASSWORD_HASH_FUNCTION not in ["SHA1", "CRYPT"]:
    raise ImproperlyConfigured("password hash function '{}' not known".format(PASSWORD_HASH_FUNCTION))

INSTALLED_APPS = tuple(list(INSTALLED_APPS) + ["rest_framework"])

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

rest_renderers = (
    [
        "rest_framework.renderers.BrowsableAPIRenderer"
    ] if DEBUG else []
) + [
    "rest_framework.renderers.JSONRenderer",
    # "rest_framework_csv.renderers.CSVRenderer",
    "rest_framework.renderers.XMLRenderer",
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': tuple(rest_renderers),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.XMLParser",
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
    'disable_existing_loggers': True,
    'formatters': {
        "initat": {
            "()": "initat.tools.logging_tools.initat_formatter",
        },
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(message)s %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        "init_unified": {
            "level": "INFO" if DEBUG else "WARN",
            "class": "initat.tools.logging_tools.init_handler_unified",
            "formatter": "initat",
        },
        "init": {
            "level": 'INFO' if DEBUG else "WARN",
            "class": "initat.tools.logging_tools.init_handler",
            "formatter": "initat",
        },
        "init_mail": {
            "level": "ERROR",
            "class": "initat.tools.logging_tools.init_email_handler",
            "formatter": "initat",
        },
    },
    'loggers': {
        'django': {
            'handlers': ['init_unified', "init_mail"],
            'propagate': True,
            'level': 'WARN',
        },
        'initat': {
            'handlers': ['init_unified', "init_mail"],
            'propagate': True,
            'level': 'WARN',
        },
        'cluster': {
            'handlers': ['init', "init_mail"],
            'propagate': True,
            'level': 'INFO' if DEBUG else "WARN",
        },
    }
}
