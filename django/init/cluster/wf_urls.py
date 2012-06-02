from django.conf.urls import patterns, include, url
from django.conf import settings
import sys

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

transfer_patterns = patterns(
    "init.cluster.transfer",
    url(r"^$", "views.redirect_to_main"),
    url(r"transfer/", "views.transfer", name="main"),
    url(r"transfer/(.*)", "views.transfer", name="main")
)

my_url_patterns = patterns(
    "",
    url(r"static/(?P<path>.*)$", "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
    url(r"^", include(transfer_patterns, namespace="transfer"))
)

url_patterns = patterns(
    "",
    # hack for icons
    url(r"icons-init/(?P<path>.*)$", "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT[:-14] + "/icons"}),
    url(r"^%s/" % (settings.REL_SITE_ROOT), include(my_url_patterns)),
)
