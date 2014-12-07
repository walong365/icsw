# Django settings for cluster project.
# -*- coding: utf-8 -*-

from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import get_random_string
import logging_tools
import os
import sys
# set unified name
logging_tools.UNIFIED_NAME = "cluster.http"

ugettext = lambda s: s  # @IgnorePep8

# monkey-patch threading for python 2.7.x
if (sys.version_info.major, sys.version_info.minor) in [(2, 7)]:
    import threading
    threading._DummyThread._Thread__stop = lambda x: 42  # @IgnorePep8

DEBUG = "DEBUG_WEBFRONTEND" in os.environ
PIPELINE_ENABLED = not DEBUG
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ("Andreas Lang-Nevyjel", "lang-nevyjel@init.at"),
)

# determine product name
if os.path.isfile("/etc/sysconfig/cluster/.is_corvus"):
    INIT_PRODUCT_NAME = "CORVUS"
    # INIT_PRODUCT_FAMILY = "Corvus albicollis" # Geierrabe, 2.0
    INIT_PRODUCT_FAMILY = "Corvus frugilegus"  # Saatkrähe, 2.1
    # INIT_PRODUCT_FAMILY = "Corvus woodfordi" # Buntschnabelkrähe, 2.2
else:
    INIT_PRODUCT_NAME = "NOCTUA"
    # INIT_PRODUCT_FAMILY = "Strigidae bubo bubo" # Uhu, 2.0
    INIT_PRODUCT_FAMILY = "Strigidae ascalaphus"  # Wüstenuhu, 2.1
    # INIT_PRODUCT_FAMILY = "Strigidae pulsatrix perspicillata" # Brillenkauz, 2.2

INIT_PRODUCT_VERSION = "2.1"

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
    STATIC_ROOT = "/srv/www/htdocs/icsw/static"

if not os.path.isdir(STATIC_ROOT_DEBUG):
    try:
        os.makedirs(STATIC_ROOT_DEBUG)
    except:
        pass
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
    "initat.core.context_processors.add_session",
    "initat.core.context_processors.add_settings",
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
    # cluster
    "initat.core",
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
STATIC_PRECOMPILER_CACHE = not DEBUG

try:
    import crispy_forms
except ImportError:
    pass
else:
    _required = "1.4.0"
    if crispy_forms.__version__ != _required:
        raise ImproperlyConfigured("Crispy forms has version '{}' (required: '{}')".format(
            crispy_forms.__version__,
            _required,
        ))

# pipeline settings
PIPELINE_YUGLIFY_BINARY = "/opt/cluster/lib/node_modules/yuglify/bin/yuglify"
if not SLAVE_MODE:
    if not os.path.exists(PIPELINE_YUGLIFY_BINARY):
        raise ImproperlyConfigured("no {} found".format(PIPELINE_YUGLIFY_BINARY))
PIPELINE_YUGLIFY_CSS_ARGUMENTS = "--terminal"
PIPELINE_YUGLIFY_JS_ARGUMENTS = "--terminal"
STATICFILES_STORAGE = "pipeline.storage.PipelineCachedStorage"

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "static_precompiler.finders.StaticPrecompilerFinder",
)

if DEBUG:
    STATICFILES_FINDERS = tuple(list(STATICFILES_FINDERS) + ["pipeline.finders.PipelineFinder"])

STATICFILES_DIRS = []
if os.path.isdir("/opt/icinga/share/images/logos"):
    STATICFILES_DIRS.append(
        ("icinga", "/opt/icinga/share/images/logos")
        )
STATICFILES_DIRS.append(
    ("admin", "/opt/python-init/lib/python/site-packages/django/contrib/admin/static/admin")
    # ("frontend", os.path.join(FILE_ROOT, "frontend", "media")),
)
STATICFILES_DIRS = list(STATICFILES_DIRS)

PIPELINE_CSS = {
    "part1": {
        "source_filenames": {
            "css/smoothness/jquery-ui-1.10.2.custom.min.css",
            "css/main.css",
            "js/libs/dynatree/skin/ui.dynatree.css",
            # "css/msdropdown/dd.css",
            "css/jqModal.css",
            "css/codemirror.css",
            "css/bootstrap.css",
            "css/jquery.Jcrop.min.css",
            "css/angular-datetimepicker.css",
            # not used right now
            # "css/angular-block-ui.css",
            "js/libs/ui-select/select.css",
            "css/ladda.min.css",
        },
        "output_filename": "pipeline/css/part1.css"
    }
}

PIPELINE_JS = {
    "js_jquery_new": {
        "source_filenames": {
            "js/libs/modernizr-2.8.1.min.js",
            # "js/plugins.js",
            "js/libs/jquery-2.1.1.min.js",
        },
        "output_filename": "pipeline/js/jquery_new.js"
    },
    "js_base": {
        "source_filenames": {
            "js/libs/jquery-ui-1.10.2.custom.js",
            # "js/libs/jquery-migrate-1.2.1.min.js",
            # now via bootstrap
            # "js/libs/jquery.layout-latest.min.js",
            # "js/jquery.sprintf.js_8.txt",
            # "js/jquery.timers-1.2.js",
            "js/jquery.noty.packaged.js",
            "js/libs/lodash.min.js",
            "js/bluebird.js",
            # "js/jquery.dd.min.js",
            "js/jquery.simplemodal.js",
            "js/codemirror/codemirror.js",
            "js/bootstrap.js",
            "js/libs/jquery.color.js",
            "js/libs/jquery.blockUI.js",
            "js/libs/angular.min.js",
            "js/libs/moment-with-locales.min.js",
            "js/libs/jquery.Jcrop.min.js",
            "js/spin.min.js",
            "js/ladda.min.js",
            "js/angular-ladda.min.js",
            "js/hamster.js",
        },
        "output_filename": "pipeline/js/base.js"
    },
    "js_extra1": {
        "source_filenames": {
            "js/codemirror/addon/selection/active-line.js",
            "js/codemirror/mode/python/python.js",
            "js/codemirror/mode/xml/xml.js",
            "js/codemirror/mode/shell/shell.js",
            # "js/libs/jquery-ui-timepicker-addon.js",
            "js/libs/angular-route.min.js",
            "js/libs/angular-resource.min.js",
            "js/libs/angular-cookies.min.js",
            "js/libs/angular-sanitize.min.js",
            "js/libs/angular-animate.min.js",
            "js/libs/angular-file-upload.js",
            "js/libs/restangular.min.js",
            # not used right now
            # "js/libs/angular-block-ui.js",
            "js/libs/ui-select/select.js",
            "js/libs/ui-bootstrap-tpls.min.js",
            # now in common_function as coffeescript
            # "js/libs/ui-codemirror.min.js",
            "js/libs/angular-datetimepicker.js",
            # "js/libs/angular-strap.min.js",
            # "js/libs/angular-strap.tpl.min.js",
            "js/angular-noVNC.js",
            "js/libs/angular-dimple.js",
            "js/libs/FileSaver.js",
            "js/mousewheel.js",
        },
        "output_filename": "pipeline/js/extra1.js"
    },
    "js_gmaps": {
        "source_filenames": {
            # google maps
            "js/angular-google-maps.min.js",
            # "js/ng-map.min.js",
        },
        "output_filename": "pipeline/js/gmaps.js"
    },
}

# add all applications, including backbone

AUTOCOMMIT = True

INSTALLED_APPS = list(INSTALLED_APPS)
ADDITIONAL_MENU_FILES = []

AUTHENTICATION_BACKENDS = (
    "initat.cluster.backbone.cluster_auth.db_backend",
)
AUTH_USER_MODEL = "backbone.user"

# my authentication backend

# add everything below cluster
dir_name = os.path.dirname(__file__)
for sub_dir in os.listdir(dir_name):
    full_path = os.path.join(dir_name, sub_dir)
    if os.path.isdir(full_path):
        if any([entry.endswith("views.py") for entry in os.listdir(full_path)]):
            add_app = "initat.cluster.{}".format(sub_dir)
            if add_app not in INSTALLED_APPS:
                # search for menu file
                templ_dir = os.path.join(full_path, "templates")
                if os.path.isdir(templ_dir):
                    for templ_name in os.listdir(templ_dir):
                        if templ_name.endswith("_menu.html"):
                            ADDITIONAL_MENU_FILES.append(templ_name)
                INSTALLED_APPS.append(add_app)
for add_app_key in [key for key in os.environ.keys() if key.startswith("INIT_APP_NAME")]:
    add_app = os.environ[add_app_key]
    if add_app not in INSTALLED_APPS:
        INSTALLED_APPS.append(add_app)

INSTALLED_APPS = tuple(INSTALLED_APPS)

AUTO_CREATE_NEW_DOMAINS = True

HANDBOOK_DIR = "/opt/cluster/share/doc/handbook"

HANDBOOK_PDF_PRESENT = os.path.exists(os.path.join(HANDBOOK_DIR, "main.html"))

HANDBOOK_CHUNKS = {}
if os.path.isdir(os.path.join(HANDBOOK_DIR, "chunks")):
    for _path, _dirs, _files in os.walk(os.path.join(HANDBOOK_DIR, "chunks")):
        for _add in [_entry for _entry in _files if _entry.endswith(".xhtml")]:
            HANDBOOK_CHUNKS[_add.split(".")[0]] = os.path.join(_path, _add)

HANDBOOK_CHUNKS_PRESENT = True if len(HANDBOOK_CHUNKS) else False

PASSWORD_HASH_FUNCTION = "SHA1"

LOGIN_SCREEN_TYPE = "big"

LOCAL_CONFIG = "/etc/sysconfig/cluster/local_settings.py"

_config_ok = False
if os.path.isfile(LOCAL_CONFIG):
    local_dir = os.path.dirname(LOCAL_CONFIG)
    sys.path.append(local_dir)
    try:
        from local_settings import SECRET_KEY, PASSWORD_HASH_FUNCTION, GOOGLE_MAPS_KEY  # @UnresolvedImport
    except:
        pass
    else:
        _config_ok = True
    sys.path.remove(local_dir)
if not _config_ok:
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    SECRET_KEY = get_random_string(50, chars)
    GOOGLE_MAPS_KEY = ""

# validate settings
if PASSWORD_HASH_FUNCTION not in ["SHA1", "CRYPT"]:
    raise ImproperlyConfigured("password hash function '{}' not known".format(PASSWORD_HASH_FUNCTION))

INSTALLED_APPS = tuple(list(INSTALLED_APPS) + ["rest_framework"])

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

rest_renderers = (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []) + [
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
            "()": "logging_tools.initat_formatter",
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
            "class": "logging_tools.init_handler_unified",
            "formatter": "initat",
        },
        "init": {
            "level": 'INFO' if DEBUG else "WARN",
            "class": "logging_tools.init_handler",
            "formatter": "initat",
        },
        "init_mail": {
            "level": "ERROR",
            "class": "logging_tools.init_email_handler",
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
