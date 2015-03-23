import os

from django.contrib import admin
from django.conf.urls import patterns, include
from django.conf import settings

admin.autodiscover()

urlpatterns = patterns("")

path_name = os.path.dirname(__file__)

for entry in os.listdir(path_name):
    if entry.endswith(".py") and entry not in ["__init__.py"]:
        new_mod = __import__(entry.split(".")[0], globals(), locals())
        urlpatterns += new_mod.url_patterns

urlpatterns += patterns(
    "",
    (r"^{}/admin/".format(settings.REL_SITE_ROOT), include(admin.site.urls)),
)