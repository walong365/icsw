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

if settings.ICSW_INCLUDE_URLS:
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
