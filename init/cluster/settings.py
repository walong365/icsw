# Django settings for cluster project.

import os
import sys

ugettext = lambda s : s

DEBUG = os.uname()[1] in ["slayer"]
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ("Andreas Lang-Nevyjel", "cluster@init.at"),
)

MANAGERS = ADMINS

DATABASES = {
    "default": {
        "ENGINE"   : "django.db.backends.mysql", 
        "NAME"     : "",
        "USER"     : "",
        "PASSWORD" : "",
        "HOST"     : "",
        "PORT"     : ""
    }
}
# read from /etc/sysconfig/cluster/mysql.cf

sql_dict = dict([(key[6:], value) for key, value in [
    line.strip().split("=", 1) for line in file("/etc/sysconfig/cluster/mysql.cf", "r").read().split("\n") if line.count("=") and line.startswith("MYSQL_")]])

for src_key ,dst_key in [("DATABASE", "NAME"),
                         ("USER"    , "USER"),
                         ("PASSWD"  , "PASSWORD"),
                         ("HOST"    , "HOST"),
                         ("ENGINE"  , "ENGINE")]:
    if src_key in sql_dict:
        DATABASES["default"][dst_key] = sql_dict[src_key]

FILE_ROOT = os.path.normpath(os.path.dirname(__file__))

# compress settings
COMPRESS = not DEBUG
COMPRESS_ENABLED = COMPRESS
COMPRESS_OFFLINE = True
# rebuild once a day
COMPRESS_REBUILD_TIMEOUT = 60 * 60 * 24

CACHES = {
    "default" : {
        "BACKEND"  : "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION" : "127.0.0.1:11211",
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

SITE_ID = 1

REL_SITE_ROOT = "cluster"
SITE_ROOT = "/%s" % (REL_SITE_ROOT)
LOGIN_URL = "%s/session/login/" % (SITE_ROOT)
                                   
# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
#MEDIA_ROOT = "/usr/local/share/home/local/development/clustersoftware/build-extern/webfrontend/htdocs/static/"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_ROOT = os.path.join(FILE_ROOT, "frontend", "media")

MEDIA_URL = "%s/frontend/media/" % (SITE_ROOT)

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
#STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
#STATIC_URL = '/static/'

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_HTTPONLY = True

# Additional locations of static files
##STATICFILES_DIRS = (
##    # Put strings here, like "/home/html/static" or "C:/www/django/static".
##    # Always use forward slashes, even on Windows.
##    # Don't forget to use absolute paths, not relative paths.
##)

# List of finder classes that know how to find static files in
# various locations.
##STATICFILES_FINDERS = (
##    'django.contrib.staticfiles.finders.FileSystemFinder',
##    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
##    "compressor.finders.CompressorFinder",
##)

# Make this unique, and don't share it with anybody.
SECRET_KEY = "av^t8g^st(phckz=9u#68k6p&amp;%3@h*z!mt=mo@3t!!ls^+4%ic"

# List of callables that know how to import templates from various sources.
TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.messages.context_processors.messages",
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "django.core.context_processors.media",
    "django.core.context_processors.debug",
    "backbone.context_processors.add_session",
)

TEMPLATE_LOADERS = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    #'django.middleware.csrf.CsrfViewMiddleware',
    "django.middleware.transaction.TransactionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "backbone.middleware.database_debug",
)

ROOT_URLCONF = "init.cluster.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "init.cluster.wsgi.application"

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    #"django.contrib.staticfiles",
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # Uncomment the next line to enable admin documentation:
    "django.contrib.admindocs",
    "reversion",
    "south",
    "compressor",
    # cluster
)

# add all applications, including backbone

INSTALLED_APPS = list(INSTALLED_APPS)
if not "NO_AUTO_ADD_APPLICATIONS" in os.environ:
    # add everything below cluster
    dir_name = os.path.dirname(__file__)
    for sub_dir in os.listdir(dir_name):
        full_path = os.path.join(dir_name, sub_dir)
        if os.path.isdir(full_path):
            if any([entry.endswith("views.py") for entry in os.listdir(full_path)]):
                add_app = "init.cluster.%s" % (sub_dir)
                if add_app not in INSTALLED_APPS:
                    INSTALLED_APPS.append(add_app)
    for add_app_key in [key for key in os.environ.keys() if key.startswith("INIT_APP_NAME")]:
        add_app = os.environ[add_app_key]
        if add_app not in INSTALLED_APPS:
            INSTALLED_APPS.append(add_app)
INSTALLED_APPS = tuple(INSTALLED_APPS)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
##LOGGING = {
##    "version": 1,
##    "disable_existing_loggers": False,
##    "filters": {
##        "require_debug_false": {
##            "()": "django.utils.log.RequireDebugFalse"
##        }
##    },
##    "handlers": {
##        "mail_admins": {
##            "level": "ERROR",
##            "filters": ["require_debug_false"],
##            "class": "django.utils.log.AdminEmailHandler"
##        }
##    },
##    "loggers": {
##        "django.request": {
##            "handlers": ["mail_admins"],
##            "level": "ERROR",
##            "propagate": True,
##        },
##    }
##}
